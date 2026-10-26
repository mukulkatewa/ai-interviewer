"""SQL for interviews. Scoped by user_id (projectprep.md, section 8)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

import asyncpg
from pydantic import BaseModel

InterviewStatus = Literal["created", "in_progress", "evaluating", "completed", "failed"]


class Interview(BaseModel):
    id: UUID
    analysis_id: UUID
    status: InterviewStatus
    created_at: datetime
    # From the linked analysis/resume: what the interviewer needs to greet and focus.
    candidate_name: str | None
    job_title: str | None
    company: str | None


_SELECT = """
    select i.id, i.analysis_id, i.status, i.created_at,
           r.profile->>'name' as candidate_name,
           j.profile->>'title' as job_title,
           j.profile->>'company' as company
    from interviews i
    join analyses a on a.id = i.analysis_id
    join resumes r on r.id = a.resume_id
    join job_descriptions j on j.id = a.job_description_id
"""


async def create(db: asyncpg.Pool, user_id: UUID, analysis_id: UUID) -> Interview | None:
    """None if the analysis doesn't exist or isn't this user's."""
    # INSERT ... SELECT: the ownership check and the insert are one statement,
    # so there's no gap between "checked" and "inserted".
    interview_id = await db.fetchval(
        """
        insert into interviews (user_id, analysis_id)
        select $1, id from analyses where id = $2 and user_id = $1
        returning id
        """,
        user_id, analysis_id,
    )  # fmt: skip
    return await get(db, user_id, interview_id) if interview_id else None


async def get(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> Interview | None:
    row = await db.fetchrow(f"{_SELECT} where i.id = $1 and i.user_id = $2", interview_id, user_id)
    return Interview(**dict(row)) if row else None


async def mark_started(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> bool:
    """created -> in_progress. False if it already started (e.g. a second tab)."""
    status = await db.execute(
        """
        update interviews set status = 'in_progress', started_at = now()
        where id = $1 and user_id = $2 and status = 'created'
        """,
        interview_id, user_id,
    )  # fmt: skip
    return status == "UPDATE 1"
