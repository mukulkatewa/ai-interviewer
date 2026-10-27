from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import limits
from app.auth import AuthUser
from app.config import get_settings
from app.db import Db
from app.deps import get_analysis_llm
from app.interview import repo
from app.interview.plan import make_plan
from app.llm import LLMClient
from app.report import repo as report_repo

router = APIRouter(prefix="/interviews", tags=["interviews"])


class CreateInterviewRequest(BaseModel):
    analysis_id: UUID


@router.post("", status_code=201)
async def create_interview(
    body: CreateInterviewRequest,
    user: AuthUser,
    db: Db,
    llm: Annotated[LLMClient, Depends(get_analysis_llm)],
) -> repo.Interview:
    await limits.enforce(db, user.id, "interviews", get_settings().limit_interviews_per_day)
    inputs = await repo.get_analysis_inputs(db, user.id, body.analysis_id)
    if inputs is None:
        raise HTTPException(404, "Analysis not found")
    # Plan first, then insert: no DB connection held during the LLM call (D18).
    # The plan is stored but never returned: candidates shouldn't see questions in advance.
    plan = await make_plan(inputs.resume, inputs.job, inputs.match, llm)
    interview = await repo.create(db, user.id, body.analysis_id, plan)
    if interview is None:  # analysis deleted while we were planning
        raise HTTPException(404, "Analysis not found")
    return interview


@router.get("")
async def list_interviews(user: AuthUser, db: Db) -> list[report_repo.InterviewSummary]:
    return await report_repo.list_interviews(db, user.id)


@router.get("/{interview_id}/report")
async def get_report(interview_id: UUID, user: AuthUser, db: Db) -> report_repo.ReportResponse:
    """Polled by the report page: status is "evaluating" until the job finishes (5.12)."""
    result = await report_repo.get_report(db, user.id, interview_id)
    if result is None:
        raise HTTPException(404, "Interview not found")
    return result


@router.post("/{interview_id}/report/retry", status_code=202)
async def retry_report(interview_id: UUID, user: AuthUser, db: Db) -> None:
    if await report_repo.get_report(db, user.id, interview_id) is None:
        raise HTTPException(404, "Interview not found")  # same as "doesn't exist" (section 8)
    if not await report_repo.retry(db, user.id, interview_id):
        raise HTTPException(409, "Only a failed report can be retried")


@router.get("/{interview_id}")
async def get_interview(interview_id: UUID, user: AuthUser, db: Db) -> repo.Interview:
    interview = await repo.get(db, user.id, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found")
    return interview
