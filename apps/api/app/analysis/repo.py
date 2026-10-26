"""SQL for analyses (and the job descriptions they own). Scoped by user_id."""

from datetime import datetime
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.analysis.schema import AnalysisReport, Insights, MatchResult
from app.jd.schema import JobProfile


class AnalysisSummary(BaseModel):
    id: UUID
    resume_id: UUID
    job_title: str | None
    company: str | None
    score: int | None
    created_at: datetime


class StoredAnalysis(AnalysisReport):
    id: UUID
    resume_id: UUID
    job_description_id: UUID
    created_at: datetime


_SELECT_FULL = """
    select a.id, a.resume_id, a.job_description_id, a.match, a.insights, a.created_at,
           j.profile as job
    from analyses a
    join job_descriptions j on j.id = a.job_description_id
"""


def _stored(row: asyncpg.Record) -> StoredAnalysis:
    return StoredAnalysis(
        id=row["id"],
        resume_id=row["resume_id"],
        job_description_id=row["job_description_id"],
        created_at=row["created_at"],
        job=JobProfile.model_validate_json(row["job"]),
        match=MatchResult.model_validate_json(row["match"]),
        insights=Insights.model_validate_json(row["insights"]),
    )


async def insert(
    db: asyncpg.Pool, user_id: UUID, resume_id: UUID, jd_text: str, report: AnalysisReport
) -> StoredAnalysis:
    # One transaction: never leave a job description without its analysis.
    async with db.acquire() as conn, conn.transaction():
        jd_id = await conn.fetchval(
            "insert into job_descriptions (user_id, raw_text, profile) values ($1, $2, $3) returning id",
            user_id, jd_text, report.job.model_dump_json(),
        )  # fmt: skip
        row = await conn.fetchrow(
            """
            insert into analyses (user_id, resume_id, job_description_id, score, match, insights)
            values ($1, $2, $3, $4, $5, $6)
            returning id, created_at
            """,
            user_id, resume_id, jd_id, report.match.score,
            report.match.model_dump_json(), report.insights.model_dump_json(),
        )  # fmt: skip
    return StoredAnalysis(
        **report.model_dump(), id=row["id"], resume_id=resume_id, job_description_id=jd_id, created_at=row["created_at"]
    )


async def list_for_user(db: asyncpg.Pool, user_id: UUID, limit: int = 50) -> list[AnalysisSummary]:
    rows = await db.fetch(
        """
        select a.id, a.resume_id, a.score, a.created_at,
               j.profile->>'title' as job_title, j.profile->>'company' as company
        from analyses a
        join job_descriptions j on j.id = a.job_description_id
        where a.user_id = $1
        order by a.created_at desc
        limit $2
        """,
        user_id, limit,
    )  # fmt: skip
    return [AnalysisSummary(**dict(r)) for r in rows]


async def get(db: asyncpg.Pool, user_id: UUID, analysis_id: UUID) -> StoredAnalysis | None:
    row = await db.fetchrow(f"{_SELECT_FULL} where a.id = $1 and a.user_id = $2", analysis_id, user_id)
    return _stored(row) if row else None
