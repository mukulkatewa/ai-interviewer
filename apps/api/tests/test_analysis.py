import pytest

from app.analysis.insights import drop_invented_bullets
from app.analysis.schema import BulletRewrite, Insights
from app.jd.schema import JobProfile, SkillRequirement
from app.llm import LLMError
from app.resume.schema import Experience, ResumeProfile
from tests.conftest import RESUME_TEXT, USER_B, make_pdf

RESUME = ResumeProfile(
    name="Asha Verma",
    skills=["Python"],
    experience=[Experience(company="Acme", role="Intern", highlights=["Built a FastAPI service"])],
)
JD_TEXT = "Backend engineer. Must have Python and Kubernetes. Docker is a plus. " * 2


def rewrite(original: str) -> BulletRewrite:
    return BulletRewrite(original=original, improved="Shipped [X] ...", reason="impact")


def test_drop_invented_bullets_keeps_real_ones_ignoring_case_and_spacing():
    insights = Insights(
        summary="ok",
        bullet_rewrites=[rewrite("built a  FastAPI service"), rewrite("Led a team of 10 at Google")],
    )
    kept = drop_invented_bullets(insights, RESUME).bullet_rewrites
    assert [r.original for r in kept] == ["built a  FastAPI service"]


# --- API ------------------------------------------------------------------------


@pytest.fixture
def resume_id(client, fake_llm) -> str:
    fake_llm.results[ResumeProfile] = RESUME
    resp = client.post("/resumes", files={"file": ("r.pdf", make_pdf(RESUME_TEXT), "application/pdf")})
    return resp.json()["id"]


@pytest.fixture
def llm_answers(fake_llm):
    fake_llm.results[JobProfile] = JobProfile(
        title="Backend Engineer",
        must_have=[SkillRequirement(skill="Python"), SkillRequirement(skill="Kubernetes")],
    )
    fake_llm.results[Insights] = Insights(summary="Decent fit", bullet_rewrites=[rewrite("Invented bullet")])
    return fake_llm


def analyze(client, resume_id):
    return client.post("/analyses", json={"resume_id": resume_id, "job_description": JD_TEXT})


def test_create_analysis_returns_and_saves_report(client, resume_id, llm_answers):
    resp = analyze(client, resume_id)

    assert resp.status_code == 201
    body = resp.json()
    assert body["match"]["score"] == 50  # 1 of 2 must-haves, computed by code
    assert body["insights"]["summary"] == "Decent fit"
    assert body["insights"]["bullet_rewrites"] == []  # invented original dropped
    # The insights prompt sees the code-computed match, not just raw text.
    assert "Kubernetes -> missing" in llm_answers.calls[-1]["user"]

    # Persisted: full report by id, and a summary in the list.
    assert client.get(f"/analyses/{body['id']}").json() == body
    [summary] = client.get("/analyses").json()
    assert (summary["job_title"], summary["score"]) == ("Backend Engineer", 50)


def test_cannot_analyze_someone_elses_resume(client, resume_id, llm_answers, login):
    login(USER_B)

    assert analyze(client, resume_id).status_code == 404
    assert llm_answers.calls[-1]["schema"] is ResumeProfile  # no LLM spend on the attempt


def test_other_users_analysis_is_invisible(client, resume_id, llm_answers, login):
    analysis_id = analyze(client, resume_id).json()["id"]

    login(USER_B)

    assert client.get(f"/analyses/{analysis_id}").status_code == 404
    assert client.get("/analyses").json() == []


def test_deleting_resume_deletes_its_analyses(client, resume_id, llm_answers):
    analysis_id = analyze(client, resume_id).json()["id"]

    client.delete(f"/resumes/{resume_id}")

    assert client.get(f"/analyses/{analysis_id}").status_code == 404


def test_rejects_tiny_job_description(client, resume_id, llm_answers):
    resp = client.post("/analyses", json={"resume_id": resume_id, "job_description": "python"})
    assert resp.status_code == 422


def test_llm_failure_is_502_and_saves_nothing(client, resume_id, llm_answers):
    llm_answers.results[JobProfile] = LLMError("down")

    assert analyze(client, resume_id).status_code == 502
    assert client.get("/analyses").json() == []
