"""Phase 9: report building (unit) and the job pipeline end to end (outbox -> worker -> report)."""

import pytest

from app.interview.plan import InterviewPlan
from app.jobs import queue
from app.jobs.worker import Worker
from app.llm import LLMBusyError
from app.main import app
from app.report.evaluate import build_report, overall_score, verified_evidence
from app.report.metrics import speaking_metrics
from app.report.schema import CompetencyScore, Evaluation, QuestionFeedback
from app.report.service import report_handlers
from tests.conftest import USER_B
from tests.test_interviews import analysis_id, answer, connect, db_rows, fakes, interview_id, read_reply, start  # noqa: F401 (fixtures)

# --- unit: code-owned parts of the report ---------------------------------------


def test_verified_evidence_keeps_only_real_quotes():
    said = "I added a compound index on seller id, status and created at. It cut p95 by 30%."
    quotes = [
        "added a COMPOUND index on seller id status",  # real: case and punctuation ignored
        "I led a team of ten engineers",  # invented
        "p95",  # too short to prove anything
    ]
    assert verified_evidence(quotes, said) == ["added a COMPOUND index on seller id status"]


def c(name: str, score: int | None) -> CompetencyScore:
    return CompetencyScore(competency=name, score=score, rationale="r")


def test_overall_score_is_weighted_and_skips_missing():
    all_names = ["communication", "technical_depth", "problem_solving", "role_fit", "behavioral"]
    assert overall_score([c(n, 5) for n in all_names]) == 100
    assert overall_score([c(n, 1) for n in all_names]) == 0
    assert overall_score([c(n, 3) for n in all_names]) == 50
    # technical_depth (0.30) at 5, communication (0.20) at 1, behavioral not assessed:
    # (0.30*5 + 0.20*1) / 0.50 = 3.4 -> (3.4-1)/4 = 60
    assert overall_score([c("technical_depth", 5), c("communication", 1), c("behavioral", None)]) == 60
    assert overall_score([c("behavioral", None)]) is None


def test_speaking_metrics():
    metrics = speaking_metrics(
        [
            ("Basically I built it, you know, with FastAPI and I'd like to add tests later on to it.", 6.0),
            ("Yes.", 1.0),
        ]
    )
    assert metrics.answers == 2
    assert metrics.words_per_minute == round(19 / (7 / 60))
    assert metrics.short_answers == 1
    assert sorted(metrics.top_fillers) == ["basically", "you know"]  # "like" isn't counted
    assert metrics.filler_per_100_words == round(100 * 2 / 19, 1)


async def test_too_short_interview_skips_the_model(fake_llm):
    report = await build_report(InterviewPlan(questions=[]), None, [], [("Hi.", 1.0)], fake_llm)
    assert report.insufficient and report.overall_score is None
    assert fake_llm.calls == []


# --- the pipeline: interview ends -> job -> worker -> report ----------------------

EVALUATION = Evaluation(
    summary="Clear and specific.",
    competencies=[
        CompetencyScore(competency="technical_depth", score=4, rationale="Specific.", evidence=["built a FastAPI service at Acme", "I invented this"]),
        CompetencyScore(competency="communication", score=3, rationale="Clear."),
        CompetencyScore(competency="behavioral", score=None, rationale="Not enough evidence."),
    ],
    questions=[QuestionFeedback(question="Q", went_well="w", missing="m", stronger_answer="s")],
    strengths=["Specific examples"],
    improvements=[],
)


def finish_interview(client, interview_id: str) -> None:
    with connect(client, interview_id) as ws:
        start(ws)
        answer(ws)
        answer(ws)
        ws.send_json({"type": "end"})
        read_reply(ws)


@pytest.fixture
def worker(client, fake_llm):
    """Run jobs inside the app's own event loop (the pool belongs to it)."""
    handlers, on_failed = report_handlers(app.state.pool, fake_llm)
    w = Worker(app.state.pool, handlers, on_failed)
    return lambda: client.portal.call(w.run_once)


def test_ending_an_interview_queues_exactly_one_report_job(client, fakes, interview_id):
    finish_interview(client, interview_id)

    [job] = db_rows("select kind, status, payload from jobs")
    assert (job["kind"], job["status"]) == ("evaluate_interview", "queued")
    assert interview_id in job["payload"]
    assert client.get(f"/interviews/{interview_id}/report").json() == {"status": "evaluating", "report": None}


def test_worker_builds_report_with_code_scored_and_verified_parts(client, fakes, interview_id, fake_llm, worker):
    fake_llm.results[Evaluation] = EVALUATION
    finish_interview(client, interview_id)

    assert worker() is True

    body = client.get(f"/interviews/{interview_id}/report").json()
    assert body["status"] == "completed"
    report = body["report"]
    # (0.30*4 + 0.20*3) / 0.50 = 3.6 -> (3.6-1)/4 = 65, computed by code
    assert report["overall_score"] == 65
    tech = next(x for x in report["competencies"] if x["competency"] == "technical_depth")
    assert tech["evidence"] == ["built a FastAPI service at Acme"]  # invented quote dropped (D14)
    assert report["metrics"]["answers"] == 2
    assert "<transcript>" in fake_llm.calls[-1]["user"] and "FastAPI service at Acme" in fake_llm.calls[-1]["user"]
    [summary] = client.get("/interviews").json()
    assert (summary["status"], summary["overall_score"]) == ("completed", 65)
    assert worker() is False  # queue empty


def test_rate_limited_job_waits_without_using_an_attempt(client, fakes, interview_id, fake_llm, worker):
    fake_llm.results[Evaluation] = LLMBusyError(retry_after_s=20)
    finish_interview(client, interview_id)

    worker()

    [job] = db_rows("select status, attempts, run_after > now() + interval '10 seconds' as later from jobs")
    assert (job["status"], job["attempts"], job["later"]) == ("queued", 0, True)


def test_failing_job_retries_then_fails_and_can_be_retried_by_user(client, fakes, interview_id, fake_llm, worker):
    fake_llm.results[Evaluation] = RuntimeError("model returned garbage")
    finish_interview(client, interview_id)

    for attempt in range(1, queue.MAX_ATTEMPTS + 1):
        db_rows("update jobs set run_after = now() where status = 'queued'")  # skip the backoff wait
        worker()
        [job] = db_rows("select status, attempts from jobs")
        assert job["attempts"] == attempt
    assert job["status"] == "failed"
    assert client.get(f"/interviews/{interview_id}/report").json()["status"] == "failed"

    assert client.post(f"/interviews/{interview_id}/report/retry").status_code == 202
    assert client.get(f"/interviews/{interview_id}/report").json()["status"] == "evaluating"
    assert len(db_rows("select 1 from jobs where status = 'queued'")) == 1
    assert client.post(f"/interviews/{interview_id}/report/retry").status_code == 409  # not failed anymore


def test_stale_running_job_is_requeued(client, fakes, interview_id):
    finish_interview(client, interview_id)
    db_rows("update jobs set status = 'running', updated_at = now() - interval '10 minutes'")

    assert client.portal.call(queue.requeue_stale, app.state.pool) == 1
    assert db_rows("select status from jobs")[0]["status"] == "queued"


def test_reports_are_private(client, fakes, interview_id, login):
    finish_interview(client, interview_id)
    login(USER_B)

    assert client.get(f"/interviews/{interview_id}/report").status_code == 404
    assert client.post(f"/interviews/{interview_id}/report/retry").status_code == 404
    assert client.get("/interviews").json() == []
