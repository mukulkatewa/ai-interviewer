"""SQL for reports. Scoped by user_id (projectprep.md, section 8)."""

from datetime import datetime
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.interview.plan import InterviewPlan, normalize
from app.interview.repo import EVALUATE_INTERVIEW, InterviewStatus, Turn
from app.jd.schema import JobProfile
from app.jobs import queue
from app.models import ApiModel
from app.report.schema import Report


class EvaluationInputs(BaseModel):
    plan: InterviewPlan
    job: JobProfile
    turns: list[Turn]
    answers: list[tuple[str, float | None]]  # (text, audio seconds) per candidate turn


class ReportResponse(ApiModel):
    status: InterviewStatus
    report: Report | None


class InterviewSummary(ApiModel):
    id: UUID
    status: InterviewStatus
    job_title: str | None
    company: str | None
    overall_score: int | None
    created_at: datetime


async def load_for_evaluation(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> EvaluationInputs | None:
    head = await db.fetchrow(
        """
        select i.plan, j.profile as job from interviews i
        join analyses a on a.id = i.analysis_id
        join job_descriptions j on j.id = a.job_description_id
        where i.id = $1 and i.user_id = $2
        """,
        interview_id, user_id,
    )  # fmt: skip
    if head is None:
        return None
    rows = await db.fetch(
        """
        select seq, role, question_index, text, audio_seconds from interview_turns
        where interview_id = $1 and user_id = $2 order by seq
        """,
        interview_id, user_id,
    )  # fmt: skip
    return EvaluationInputs(
        plan=InterviewPlan.model_validate_json(head["plan"])
        if head["plan"]
        else normalize(InterviewPlan(questions=[])),
        job=JobProfile.model_validate_json(head["job"]),
        turns=[Turn(**{k: r[k] for k in Turn.model_fields}) for r in rows],
        answers=[(r["text"], r["audio_seconds"]) for r in rows if r["role"] == "candidate"],
    )


async def save_report(db: asyncpg.Pool, user_id: UUID, interview_id: UUID, report: Report) -> None:
    """Upsert, so a job retried after a crash between "saved" and "job done" stays correct."""
    async with db.acquire() as conn, conn.transaction():
        await conn.execute(
            """
            insert into evaluations (user_id, interview_id, overall_score, report) values ($1, $2, $3, $4)
            on conflict (interview_id) do update set overall_score = excluded.overall_score, report = excluded.report
            """,
            user_id, interview_id, report.overall_score, report.model_dump_json(),
        )  # fmt: skip
        await conn.execute(
            "update interviews set status = 'completed' where id = $1 and user_id = $2", interview_id, user_id
        )


async def mark_failed(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> None:
    await db.execute(
        "update interviews set status = 'failed' where id = $1 and user_id = $2 and status = 'evaluating'",
        interview_id, user_id,
    )  # fmt: skip


async def retry(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> bool:
    """failed -> evaluating, with a fresh job, atomically. False if it wasn't failed."""
    async with db.acquire() as conn, conn.transaction():
        status = await conn.execute(
            "update interviews set status = 'evaluating' where id = $1 and user_id = $2 and status = 'failed'",
            interview_id, user_id,
        )  # fmt: skip
        if status != "UPDATE 1":
            return False
        await queue.enqueue(conn, EVALUATE_INTERVIEW, {"user_id": str(user_id), "interview_id": str(interview_id)})
    return True


async def get_report(db: asyncpg.Pool, user_id: UUID, interview_id: UUID) -> ReportResponse | None:
    row = await db.fetchrow(
        """
        select i.status, e.report from interviews i
        left join evaluations e on e.interview_id = i.id
        where i.id = $1 and i.user_id = $2
        """,
        interview_id, user_id,
    )  # fmt: skip
    if row is None:
        return None
    report = Report.model_validate_json(row["report"]) if row["report"] else None
    return ReportResponse(status=row["status"], report=report)


async def list_interviews(db: asyncpg.Pool, user_id: UUID, limit: int = 50) -> list[InterviewSummary]:
    rows = await db.fetch(
        """
        select i.id, i.status, i.created_at, e.overall_score,
               j.profile->>'title' as job_title, j.profile->>'company' as company
        from interviews i
        join analyses a on a.id = i.analysis_id
        join job_descriptions j on j.id = a.job_description_id
        left join evaluations e on e.interview_id = i.id
        where i.user_id = $1
        order by i.created_at desc
        limit $2
        """,
        user_id, limit,
    )  # fmt: skip
    return [InterviewSummary(**dict(r)) for r in rows]
