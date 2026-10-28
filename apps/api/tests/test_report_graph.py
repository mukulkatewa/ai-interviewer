"""The LangGraph report engine (D38): same results as the single call, plus parallelism and retries."""

import asyncio

import pytest
from langgraph.types import RetryPolicy

from app.interview.plan import InterviewPlan, PlannedQuestion
from app.jd.schema import JobProfile
from app.llm import LLMBusyError
from app.report import graph as report_graph
from app.report.evaluate import build_report, verify
from app.report.metrics import speaking_metrics
from app.report.repo import EvaluationInputs
from app.report.schema import (
    CompetencyEvaluation,
    CompetencyScore,
    Evaluation,
    Improvement,
    QuestionFeedback,
    QuestionReview,
    Wrapup,
)
from app.resume.schema import ResumeProfile
from tests.conftest import FakeLLM

SAID = "I added a compound index on seller id and p95 dropped by thirty percent"
FAST = RetryPolicy(initial_interval=0.001, max_attempts=3, retry_on=LLMBusyError)


def q(text: str, score: int = 4, quote: str | None = "added a compound index on seller id") -> QuestionFeedback:
    return QuestionFeedback(question=text, score=score, quote=quote, went_well="w", missing="m", stronger_answer="s")


def comp(name: str, score: int, evidence: list[str] | None = None) -> CompetencyScore:
    return CompetencyScore(competency=name, score=score, rationale="r", evidence=evidence or [])


COMPETENCIES = [
    comp("technical_depth", 4, ["added a compound index on seller id", "I invented this"]),
    comp("communication", 3),
]
QUESTIONS = [q("How did you speed up checkout?")]
WRAPUP = Wrapup(
    summary="Solid.", strengths=["Specific"], improvements=[Improvement(area="Numbers", advice="Give before and after")]
)


def inputs(answers=None, questions=1) -> EvaluationInputs:
    return EvaluationInputs(
        plan=InterviewPlan(
            questions=[
                PlannedQuestion(phase="resume_deep_dive", question=f"Q{i}?", focus="f") for i in range(questions)
            ]
        ),
        resume=ResumeProfile(name="Rahul", skills=["Python"]),
        job=JobProfile(title="Backend Engineer"),
        has_job_description=True,
        turns=[],
        answers=answers if answers is not None else [(SAID, 10.0), (SAID, 12.0)],
    )


def canned() -> FakeLLM:
    return FakeLLM(
        {
            CompetencyEvaluation: CompetencyEvaluation(competencies=COMPETENCIES),
            QuestionReview: QuestionReview(questions=QUESTIONS),
            Wrapup: WRAPUP,
            Evaluation: Evaluation(competencies=COMPETENCIES, questions=QUESTIONS, **WRAPUP.model_dump()),
        }
    )


async def run_graph(llm, data, retry=FAST):
    return await report_graph.build_report(report_graph.build_graph(llm, retry), data)


async def test_graph_and_single_call_give_the_same_report():
    data = inputs()
    assert await run_graph(canned(), data) == await build_report(data, canned())


async def test_graph_has_the_documented_shape():
    nodes = set(report_graph.build_graph(canned()).get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"prepare", "score_competencies", "review_questions", "verify", "write_wrapup"}


async def test_too_short_makes_no_model_call():
    llm = canned()
    report = await run_graph(llm, inputs(answers=[("Hi.", 1.0)]))
    assert report.insufficient and report.overall_score is None
    assert llm.calls == []


async def test_the_two_model_calls_really_run_in_parallel():
    """Each call waits for the other to start: a sequential pipeline would hang until the timeout."""
    started = {CompetencyEvaluation: asyncio.Event(), QuestionReview: asyncio.Event()}

    class Barrier(FakeLLM):
        async def complete_json(self, system, user, schema):
            if schema in started:
                started[schema].set()
                other = QuestionReview if schema is CompetencyEvaluation else CompetencyEvaluation
                await asyncio.wait_for(started[other].wait(), timeout=2)
            return await super().complete_json(system, user, schema)

    llm = Barrier(canned().results)
    assert (await run_graph(llm, inputs())).overall_score is not None


async def test_wrapup_reads_verified_results_not_the_transcript():
    llm = canned()
    await run_graph(llm, inputs())
    [wrapup_call] = [c for c in llm.calls if c["schema"] is Wrapup]
    assert "<transcript>" not in wrapup_call["user"]
    assert "added a compound index on seller id" in wrapup_call["user"]
    assert "I invented this" not in wrapup_call["user"]  # the unverifiable quote was dropped before it got here


class Flaky(FakeLLM):
    """Rate-limited `times` times for one schema, then fine."""

    def __init__(self, results, schema, times):
        super().__init__(results)
        self.schema, self.left = schema, times

    async def complete_json(self, system, user, schema):
        if schema is self.schema and self.left > 0:
            self.left -= 1
            self.calls.append({"schema": schema})
            raise LLMBusyError(1)
        return await super().complete_json(system, user, schema)


async def test_a_rate_limit_retries_only_the_failed_node():
    llm = Flaky(canned().results, CompetencyEvaluation, times=2)
    assert (await run_graph(llm, inputs())).overall_score is not None
    schemas = [c["schema"] for c in llm.calls]
    assert schemas.count(CompetencyEvaluation) == 3  # two rate limits, then success
    assert schemas.count(QuestionReview) == 1  # the other branch was not repeated
    assert schemas.count(Wrapup) == 1


async def test_a_persistent_rate_limit_reaches_the_job_worker():
    with pytest.raises(LLMBusyError):
        await run_graph(Flaky(canned().results, QuestionReview, times=99), inputs())


async def test_a_malformed_model_answer_fails_loudly():
    llm = canned()
    llm.results[Wrapup] = RuntimeError("bad json")
    with pytest.raises(RuntimeError):
        await run_graph(llm, inputs())


def test_verify_caps_questions_at_the_plan_and_drops_repeats():
    data = inputs(questions=2)
    metrics = speaking_metrics(data.answers)
    spam = [
        q("How did you speed up checkout?"),
        q("how did you SPEED up checkout"),
        q("Second?"),
        q("Third?"),
        q("Fourth?"),
    ]
    _, questions = verify(data, metrics, [], spam)
    assert [x.question for x in questions] == ["How did you speed up checkout?", "Second?"]
