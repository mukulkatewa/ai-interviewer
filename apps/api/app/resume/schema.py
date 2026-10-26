from pydantic import Field

from app.models import ApiModel


class Experience(ApiModel):
    company: str
    role: str
    start: str | None = Field(None, description="As written on the resume, e.g. 'Jan 2023'")
    end: str | None = Field(None, description="As written, or 'Present'")
    highlights: list[str] = Field(default_factory=list, description="Bullet points, verbatim")
    technologies: list[str] = Field(default_factory=list)


class Project(ApiModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class Education(ApiModel):
    institution: str
    degree: str | None = None
    year: str | None = None


class ResumeProfile(ApiModel):
    """Structured view of a resume. Every field must come from the resume text;
    the interviewer plans questions from this, so invented facts are a bug."""

    name: str | None = None
    headline: str | None = Field(None, description="One-line professional summary")
    total_experience_years: float | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
