from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

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
    """From a job match report, or straight from a resume (the job description is optional, D36)."""

    analysis_id: UUID | None = None
    resume_id: UUID | None = None
    target_role: str | None = Field(None, max_length=120, description="Optional role to practice for; resume-only")

    @model_validator(mode="after")
    def exactly_one_source(self) -> "CreateInterviewRequest":
        if (self.analysis_id is None) == (self.resume_id is None):
            raise ValueError("Send either analysis_id or resume_id")
        if self.analysis_id is not None:
            self.target_role = None
        else:
            self.target_role = (self.target_role or "").strip() or None
        return self


@router.post("", status_code=201)
async def create_interview(
    body: CreateInterviewRequest,
    user: AuthUser,
    db: Db,
    llm: Annotated[LLMClient, Depends(get_analysis_llm)],
) -> repo.Interview:
    await limits.enforce(db, user.id, "interviews", get_settings().limit_interviews_per_day)
    if body.analysis_id is not None:
        inputs = await repo.get_analysis_inputs(db, user.id, body.analysis_id)
    else:
        assert body.resume_id is not None  # guaranteed by the request model
        inputs = await repo.get_resume_inputs(db, user.id, body.resume_id, body.target_role)
    if inputs is None:
        raise HTTPException(404, "Analysis not found" if body.analysis_id else "Resume not found")
    # Plan first, then insert: no DB connection held during the LLM call (D18).
    # The plan is stored but never returned: candidates shouldn't see questions in advance.
    plan = await make_plan(inputs.resume, inputs.job, inputs.match, llm)
    interview = await repo.create(
        db, user.id, plan, analysis_id=body.analysis_id, resume_id=body.resume_id, target_role=body.target_role
    )
    if interview is None:  # deleted while we were planning
        raise HTTPException(404, "Analysis not found" if body.analysis_id else "Resume not found")
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
