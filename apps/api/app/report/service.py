"""The `evaluate_interview` job: load a finished interview, build its report, save it."""

import logging
from typing import Any
from uuid import UUID

import asyncpg

from app.config import get_settings
from app.interview.repo import EVALUATE_INTERVIEW
from app.jobs.worker import FailureHandler, Handler, PermanentError
from app.llm import LLMClient
from app.report import graph as report_graph
from app.report import repo
from app.report.evaluate import build_report

logger = logging.getLogger(__name__)


def report_handlers(db: asyncpg.Pool, llm: LLMClient) -> tuple[dict[str, Handler], dict[str, FailureHandler]]:
    # Compiled once: the graph keeps no per-interview state.
    graph = report_graph.build_graph(llm) if get_settings().report_engine == "graph" else None

    async def evaluate(payload: dict[str, Any]) -> None:
        user_id, interview_id = UUID(payload["user_id"]), UUID(payload["interview_id"])
        inputs = await repo.load_for_evaluation(db, user_id, interview_id)
        if inputs is None:
            raise PermanentError("Interview no longer exists")  # deleted after it ended
        report = await (report_graph.build_report(graph, inputs) if graph else build_report(inputs, llm))
        await repo.save_report(db, user_id, interview_id, report)
        logger.info("report interview=%s score=%s", interview_id, report.overall_score)

    async def evaluation_failed(payload: dict[str, Any], error: str) -> None:
        await repo.mark_failed(db, UUID(payload["user_id"]), UUID(payload["interview_id"]))

    return {EVALUATE_INTERVIEW: evaluate}, {EVALUATE_INTERVIEW: evaluation_failed}
