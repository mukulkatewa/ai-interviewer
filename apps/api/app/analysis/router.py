from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.analysis import repo
from app.analysis.insights import write_insights
from app.analysis.matching import match_resume
from app.analysis.schema import AnalysisReport
from app.auth import AuthUser
from app.db import Db
from app.deps import get_analysis_llm, get_jd_llm
from app.jd.structure import structure_jd
from app.llm import LLMClient
from app.resume import repo as resume_repo

router = APIRouter(prefix="/analyses", tags=["analyses"])


class AnalyzeRequest(BaseModel):
    resume_id: UUID
    job_description: str = Field(min_length=50, max_length=20_000)


@router.post("", status_code=201)
async def create_analysis(
    body: AnalyzeRequest,
    user: AuthUser,
    db: Db,
    jd_llm: Annotated[LLMClient, Depends(get_jd_llm)],
    analysis_llm: Annotated[LLMClient, Depends(get_analysis_llm)],
) -> repo.StoredAnalysis:
    # Ownership check before any LLM spend: someone else's resume is a 404.
    resume = await resume_repo.get(db, user.id, body.resume_id)
    if resume is None:
        raise HTTPException(404, "Resume not found")

    # No DB connection is held during these calls (D18); LLM failures become
    # 502/503 in app/main.py. Sequential by necessity: insights need the match,
    # the match needs the JD.
    job = await structure_jd(body.job_description, jd_llm)
    match = match_resume(resume.profile, job)
    insights = await write_insights(resume.profile, job, match, analysis_llm)
    report = AnalysisReport(job=job, match=match, insights=insights)
    return await repo.insert(db, user.id, resume.id, body.job_description, report)


@router.get("")
async def list_analyses(user: AuthUser, db: Db) -> list[repo.AnalysisSummary]:
    return await repo.list_for_user(db, user.id)


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: UUID, user: AuthUser, db: Db) -> repo.StoredAnalysis:
    analysis = await repo.get(db, user.id, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found")
    return analysis
