import pymupdf
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.deps import get_analysis_llm, get_extraction_llm
from app.main import app
from app.resume.schema import ResumeProfile

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
    """One fake serves both LLM roles; tests register results per schema."""
    llm = FakeLLM({ResumeProfile: ResumeProfile(name="Asha Verma", skills=["Python", "FastAPI"])})
    app.dependency_overrides[get_extraction_llm] = lambda: llm
    app.dependency_overrides[get_analysis_llm] = lambda: llm
    yield llm
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)
