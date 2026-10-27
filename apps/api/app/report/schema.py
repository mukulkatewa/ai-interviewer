from typing import Literal

from pydantic import Field

from app.models import ApiModel

Competency = Literal["communication", "technical_depth", "problem_solving", "role_fit", "behavioral"]


class CompetencyScore(ApiModel):
    competency: Competency
    score: int | None = Field(None, ge=1, le=5, description="1-5, or null if the interview gave no evidence")
    rationale: str = Field(description="One or two sentences explaining the score")
    evidence: list[str] = Field(default_factory=list, description="Exact short quotes from the candidate")


class QuestionFeedback(ApiModel):
    question: str
    went_well: str
    missing: str
    stronger_answer: str = Field(description="Outline of a stronger answer, using the candidate's own experience")


class Improvement(ApiModel):
    area: str
    advice: str = Field(description="One concrete thing to do differently next time")


class Evaluation(ApiModel):
    """What the model writes. Scores and quotes are checked by code before use (D14)."""

    summary: str
    competencies: list[CompetencyScore]
    questions: list[QuestionFeedback] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[Improvement] = Field(default_factory=list)


class SpeakingMetrics(ApiModel):
    answers: int
    words_per_minute: float | None
    avg_answer_seconds: float | None
    short_answers: int = Field(description="Answers under 15 words")
    filler_per_100_words: float
    top_fillers: list[str]


class Report(ApiModel):
    overall_score: int | None = Field(description="0-100, computed by code from competency scores")
    insufficient: bool = Field(description="True when the interview was too short to evaluate")
    summary: str
    competencies: list[CompetencyScore]
    questions: list[QuestionFeedback]
    strengths: list[str]
    improvements: list[Improvement]
    metrics: SpeakingMetrics
