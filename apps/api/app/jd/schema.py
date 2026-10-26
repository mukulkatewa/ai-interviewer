from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal["intern", "junior", "mid", "senior", "lead"]


class SkillRequirement(BaseModel):
    """One requirement from the JD. Met if the candidate has `skill` or any alternative.

    "React or Vue" is a single requirement, not two: otherwise a React developer
    would be marked as missing Vue.
    """

    skill: str = Field(description="Short canonical name, 1-3 words, e.g. 'PostgreSQL'")
    alternatives: list[str] = Field(default_factory=list, description="Skills that satisfy this equally")


class JobProfile(BaseModel):
    title: str | None = None
    company: str | None = None
    seniority: Seniority | None = None
    min_years_experience: float | None = None
    must_have: list[SkillRequirement] = Field(default_factory=list)
    nice_to_have: list[SkillRequirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list, description="Short phrases, max ~8")
