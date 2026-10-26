from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.analysis.insights import write_insights
from app.analysis.matching import match_resume
from app.analysis.schema import AnalysisReport
from app.deps import get_analysis_llm, get_extraction_llm
from app.jd.structure import structure_jd
from app.llm import LLMClient, LLMError
from app.resume.schema import ResumeProfile

router = APIRouter(prefix="/analyses", tags=["analyses"])


class AnalyzeRequest(BaseModel):
    # Stateless for now: the client sends back the profile from /resumes/parse.
    # Once Supabase is in (build step 3) this becomes resume_id + jd_id.
    resume: ResumeProfile
    job_description: str = Field(min_length=50, max_length=20_000)


@router.post("")
async def analyze(
    body: AnalyzeRequest,
    extraction_llm: Annotated[LLMClient, Depends(get_extraction_llm)],
    analysis_llm: Annotated[LLMClient, Depends(get_analysis_llm)],
) -> AnalysisReport:
    try:
        # Sequential by necessity: insights need the match, the match needs the JD.
        job = await structure_jd(body.job_description, extraction_llm)
        match = match_resume(body.resume, job)
        insights = await write_insights(body.resume, job, match, analysis_llm)
    except LLMError as e:
        raise HTTPException(502, "Could not analyze the job description. Please try again.") from e

    return AnalysisReport(job=job, match=match, insights=insights)
