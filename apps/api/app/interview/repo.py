"""SQL for interviews. Scoped by user_id (projectprep.md, section 8)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.analysis.schema import MatchResult
from app.jd.schema import JobProfile
from app.resume.schema import ResumeProfile

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


class InterviewContext(BaseModel):
    """Everything the interviewer needs to know, loaded once per session."""

    interview: Interview
    resume: ResumeProfile
    job: JobProfile
    match: MatchResult


async def get_context(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> InterviewContext | None:
    row = await db.fetchrow(
        f"""
        select q.*, r.profile as resume_profile, j.profile as job_profile, a.match
        from ({_SELECT} where i.id = $1 and i.user_id = $2) q
        join analyses a on a.id = q.analysis_id
        join resumes r on r.id = a.resume_id
        join job_descriptions j on j.id = a.job_description_id
        """,
        interview_id, user_id,
    )  # fmt: skip
    if row is None:
        return None
    return InterviewContext(
        interview=Interview(**{k: row[k] for k in Interview.model_fields}),
        resume=ResumeProfile.model_validate_json(row["resume_profile"]),
        job=JobProfile.model_validate_json(row["job_profile"]),
        match=MatchResult.model_validate_json(row["match"]),
    )
