from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import AuthUser
from app.db import Db
from app.deps import get_analysis_llm
from app.interview import repo
from app.interview.plan import make_plan
from app.llm import LLMClient

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


@router.get("/{interview_id}")
async def get_interview(interview_id: UUID, user: AuthUser, db: Db) -> repo.Interview:
    interview = await repo.get(db, user.id, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found")
    return interview
