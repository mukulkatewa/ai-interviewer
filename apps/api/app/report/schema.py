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
    score: int | None = Field(None, ge=1, le=5, description="1-5 for this one answer; 4+ needs a verified quote")
    quote: str | None = Field(None, description="Exact short quote from this answer that justifies the score")
    went_well: str = Field(description="What was good, naming the specific thing the candidate said")
    missing: str = Field(description="The concrete detail, number, trade-off or example the answer lacked")
    stronger_answer: str = Field(description="A model answer to say aloud, first person, from the resume only")


class Improvement(ApiModel):
    area: str
    advice: str = Field(description="One concrete thing to do differently next time")
    practice: str | None = Field(None, description="A 5-minute exercise that builds this skill")


class CompetencyEvaluation(ApiModel):
    competencies: list[CompetencyScore]


class QuestionReview(ApiModel):
    questions: list[QuestionFeedback] = Field(default_factory=list)


class Wrapup(ApiModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[Improvement] = Field(default_factory=list)


class Evaluation(CompetencyEvaluation, QuestionReview, Wrapup):
    """Everything the model writes in one call. Scores and quotes are checked by code before use (D14).

    The graph engine asks for the same three parts separately (D38); this is the single-call form.
    """


class SpeakingMetrics(ApiModel):
    answers: int
    words_per_minute: float | None
    avg_answer_seconds: float | None
    short_answers: int = Field(description="Answers under 15 words")
    filler_per_100_words: float
    top_fillers: list[str]


Level = Literal["strong", "solid", "developing", "needs_work"]


class Report(ApiModel):
    overall_score: int | None = Field(description="0-100, computed by code from competency scores")
    level: Level | None = Field(None, description="Plain-words band for the score, computed by code")
    insufficient: bool = Field(description="True when the interview was too short to evaluate")
    summary: str
    competencies: list[CompetencyScore]
    questions: list[QuestionFeedback]
    strengths: list[str]
    improvements: list[Improvement]
    metrics: SpeakingMetrics
