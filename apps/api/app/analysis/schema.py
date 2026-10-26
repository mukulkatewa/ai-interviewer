from typing import Literal

from pydantic import BaseModel, Field

from app.jd.schema import JobProfile, SkillRequirement

# listed:    in the resume's skills or a role/project's technologies
# mentioned: not listed, but appears in a bullet or description (advice: list it)
# missing:   nowhere in the resume
MatchStatus = Literal["listed", "mentioned", "missing"]


class RequirementMatch(BaseModel):
    requirement: SkillRequirement
    status: MatchStatus
    matched_as: str | None = Field(None, description="Resume spelling that satisfied it, if listed")


class Coverage(BaseModel):
    matches: list[RequirementMatch]
    ratio: float | None = Field(description="Share of requirements met; None if the JD lists none")


class MatchResult(BaseModel):
    """Deterministic part of the analysis: same resume + JD always gives the same result."""

    must_have: Coverage
    nice_to_have: Coverage
    score: int | None = Field(description="0-100, or None if the JD lists no skills")


class Gap(BaseModel):
    skill: str
    advice: str = Field(description="One concrete, actionable step")


class BulletRewrite(BaseModel):
    original: str = Field(description="Exact bullet text copied from the resume")
    improved: str
    reason: str


class Insights(BaseModel):
    """Written by the model; facts it claims are checked by code (projectprep.md, D14)."""

    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    bullet_rewrites: list[BulletRewrite] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    job: JobProfile
    match: MatchResult
    insights: Insights
