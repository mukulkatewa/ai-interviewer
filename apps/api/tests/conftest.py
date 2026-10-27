import asyncio
import os
import uuid
from pathlib import Path

import asyncpg
import pymupdf
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.deps import get_analysis_llm, get_jd_llm, get_resume_llm
from app.main import app
from app.resume.schema import ResumeProfile

# Local Postgres from infra/docker-compose.yml. Never point this at Supabase:
# the suite drops and recreates schemas.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/postgres")
MIGRATIONS = sorted((Path(__file__).parents[3] / "supabase" / "migrations").glob("*.sql"))

# Supabase provides the auth schema; locally we stub the one table we reference.
AUTH_STUB = "create schema auth; create table auth.users (id uuid primary key);"

USER_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")

RESUME_TEXT = """Asha Verma
Backend Engineer | Python, FastAPI, PostgreSQL, Docker
Experience
Software Engineer, Acme Corp, Jan 2023 - Present
- Built a FastAPI service handling 2M requests/day
- Cut p95 latency by 40% with Redis caching
Education
B.Tech Computer Science, IIT Delhi, 2022
"""


def make_pdf(text: str, pages: int = 1) -> bytes:
    """Build a real text-layer PDF in memory, so tests exercise PyMuPDF for real."""
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((50, 72), text, fontsize=10)
    return doc.tobytes()


class FakeLLM:
    """Stands in for Groq. Returns the canned result registered for the requested
    schema (or raises it, if it's an exception) and records every call."""

    def __init__(self, results: dict[type[BaseModel], BaseModel | Exception] | None = None):
        self.results = results or {}
        self.calls: list[dict] = []

    async def complete_json(self, system, user, schema):
        self.calls.append({"system": system, "user": user, "schema": schema})
        result = self.results[schema]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def fake_llm():
    """One fake serves every LLM job; tests register results per schema."""
    llm = FakeLLM({ResumeProfile: ResumeProfile(name="Asha Verma", skills=["Python", "FastAPI"])})
    providers = (get_resume_llm, get_jd_llm, get_analysis_llm)
    for provider in providers:
        app.dependency_overrides[provider] = lambda: llm
    yield llm
    for provider in providers:
        app.dependency_overrides.pop(provider, None)


# --- database -------------------------------------------------------------------


async def _run_sql(*statements: str) -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        for sql in statements:
            await conn.execute(sql)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database() -> str:
    """Fresh schema built from the real migration files, once per test session."""
    try:
        asyncio.run(
            _run_sql(
                "drop schema if exists public cascade; drop schema if exists auth cascade; create schema public;",
                AUTH_STUB,
                *(m.read_text() for m in MIGRATIONS),
            )
        )
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres unavailable ({e}). Run: docker compose -f infra/docker-compose.yml up -d")
    return TEST_DATABASE_URL


@pytest.fixture
def login():
    """Call login(user_id) to make the API see that user as the caller."""

    def _login(user_id: uuid.UUID) -> None:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)

    yield _login
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client(database, login, monkeypatch):
    """API client on an empty database, logged in as USER_A.

    Entering TestClient runs the real lifespan, so pool startup is tested too.
    """
    # Truncating auth.users cascades to every user-owned table; jobs has no user_id (D31), so it's listed too.
    asyncio.run(
        _run_sql("truncate auth.users, public.jobs cascade", f"insert into auth.users values ('{USER_A}'), ('{USER_B}')")
    )
    monkeypatch.setattr(get_settings(), "database_url", database)
    monkeypatch.setattr(get_settings(), "run_jobs", False)  # tests run the worker explicitly
    login(USER_A)
    with TestClient(app) as c:
        yield c
