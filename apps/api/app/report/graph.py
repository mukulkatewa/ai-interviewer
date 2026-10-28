"""The report pipeline as a LangGraph graph (projectprep.md D38).

    prepare ─┬─► score_competencies ─┬─► verify ─► write_wrapup ─► END
             │                       │
             └─► review_questions ───┘
             └─► END   (too short to evaluate: no model call at all)

Why a graph here and not in the live interview: this work has real structure (two independent model
calls that can run in parallel, a join, a checking step, per-node retries) and it runs in the
background worker, so it cannot slow the conversation. The nodes are the same functions the
single-call engine uses (app/report/evaluate.py): this file only decides the order.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from app.llm import LLMBusyError, LLMClient
from app.report import evaluate
from app.report.metrics import speaking_metrics
from app.report.repo import EvaluationInputs
from app.report.schema import (
    CompetencyEvaluation,
    CompetencyScore,
    QuestionFeedback,
    QuestionReview,
    Report,
    SpeakingMetrics,
    Wrapup,
)

# The free tier allows ~8k tokens a minute per model, and two parallel calls can brush against it.
# Retry only that case, per node: the branch that succeeded is not repeated. Past this the error
# reaches the job worker, which waits as long as the provider asks (D22).
RATE_LIMIT_RETRY = RetryPolicy(initial_interval=15.0, backoff_factor=2.0, max_attempts=3, retry_on=LLMBusyError)


class State(TypedDict, total=False):
    inputs: EvaluationInputs
    metrics: SpeakingMetrics
    scores: CompetencyEvaluation
    review: QuestionReview
    competencies: list[CompetencyScore]
    questions: list[QuestionFeedback]
    report: Report


def build_graph(llm: LLMClient, retry: RetryPolicy = RATE_LIMIT_RETRY) -> CompiledStateGraph:
    """Compile once at startup; the graph holds no per-interview state."""

    async def prepare(state: State) -> State:
        inputs = state["inputs"]
        metrics = speaking_metrics(inputs.answers)
        if evaluate.enough_to_evaluate(inputs):
            return {"metrics": metrics}
        return {"metrics": metrics, "report": evaluate.insufficient_report(metrics)}

    def after_prepare(state: State) -> list[str]:
        return [END] if "report" in state else ["score_competencies", "review_questions"]

    async def score_competencies(state: State) -> State:
        user = evaluate.context(state["inputs"], focus=False)  # scoring needs no planner notes
        return {"scores": await llm.complete_json(evaluate.COMPETENCY_PROMPT, user, CompetencyEvaluation)}

    async def review_questions(state: State) -> State:
        user = evaluate.context(state["inputs"])
        return {"review": await llm.complete_json(evaluate.QUESTION_PROMPT, user, QuestionReview)}

    async def verify(state: State) -> State:
        competencies, questions = evaluate.verify(
            state["inputs"], state["metrics"], state["scores"].competencies, state["review"].questions
        )
        return {"competencies": competencies, "questions": questions}

    async def write_wrapup(state: State) -> State:
        user = evaluate.wrapup_context(state["metrics"], state["competencies"], state["questions"])
        wrapup = await llm.complete_json(evaluate.WRAPUP_PROMPT, user, Wrapup)
        report = evaluate.assemble(state["metrics"], state["competencies"], state["questions"], wrapup)
        return {"report": report}

    graph = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("score_competencies", score_competencies, retry_policy=retry)
    graph.add_node("review_questions", review_questions, retry_policy=retry)
    graph.add_node("verify", verify)
    graph.add_node("write_wrapup", write_wrapup, retry_policy=retry)

    graph.add_edge(START, "prepare")
    graph.add_conditional_edges("prepare", after_prepare, ["score_competencies", "review_questions", END])
    graph.add_edge(["score_competencies", "review_questions"], "verify")  # join: waits for both
    graph.add_edge("verify", "write_wrapup")
    graph.add_edge("write_wrapup", END)
    return graph.compile()


async def build_report(graph: CompiledStateGraph, inputs: EvaluationInputs) -> Report:
    final = await graph.ainvoke({"inputs": inputs})
    return final["report"]
