"""SQL for resumes. Every query is scoped by user_id (projectprep.md, section 8)."""

from datetime import datetime
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.resume.schema import ResumeProfile


class ResumeSummary(BaseModel):
    id: UUID
    file_name: str
    name: str | None
    created_at: datetime


class StoredResume(ResumeSummary):
    profile: ResumeProfile


def _stored(row: asyncpg.Record) -> StoredResume:
    profile = ResumeProfile.model_validate_json(row["profile"])
    return StoredResume(
        id=row["id"], file_name=row["file_name"], name=profile.name, created_at=row["created_at"], profile=profile
    )


async def insert(
    db: asyncpg.Pool, user_id: UUID, file_name: str, raw_text: str, profile: ResumeProfile
) -> StoredResume:
    row = await db.fetchrow(
        """
        insert into resumes (user_id, file_name, raw_text, profile)
        values ($1, $2, $3, $4)
        returning id, file_name, profile, created_at
        """,
        user_id, file_name, raw_text, profile.model_dump_json(),
    )  # fmt: skip
    return _stored(row)


async def list_for_user(db: asyncpg.Pool, user_id: UUID, limit: int = 50) -> list[ResumeSummary]:
    # Only the name comes out of the jsonb, so the list never ships full profiles.
    rows = await db.fetch(
        """
        select id, file_name, profile->>'name' as name, created_at
        from resumes
        where user_id = $1
        order by created_at desc
        limit $2
        """,
        user_id, limit,
    )  # fmt: skip
    return [ResumeSummary(**dict(r)) for r in rows]


async def get(db: asyncpg.Pool, user_id: UUID, resume_id: UUID) -> StoredResume | None:
    row = await db.fetchrow(
        "select id, file_name, profile, created_at from resumes where id = $1 and user_id = $2",
        resume_id, user_id,
    )  # fmt: skip
    return _stored(row) if row else None


async def delete(db: asyncpg.Pool, user_id: UUID, resume_id: UUID) -> bool:
    status = await db.execute("delete from resumes where id = $1 and user_id = $2", resume_id, user_id)
    return status == "DELETE 1"
