from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import AuthUser
from app.db import Db
from app.interview import repo

router = APIRouter(prefix="/interviews", tags=["interviews"])


class CreateInterviewRequest(BaseModel):
    analysis_id: UUID


@router.post("", status_code=201)
async def create_interview(body: CreateInterviewRequest, user: AuthUser, db: Db) -> repo.Interview:
    interview = await repo.create(db, user.id, body.analysis_id)
    if interview is None:
        raise HTTPException(404, "Analysis not found")
    return interview


@router.get("/{interview_id}")
async def get_interview(interview_id: UUID, user: AuthUser, db: Db) -> repo.Interview:
    interview = await repo.get(db, user.id, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found")
    return interview
