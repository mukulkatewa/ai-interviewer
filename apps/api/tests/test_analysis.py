from app.analysis.insights import drop_invented_bullets
from app.analysis.schema import BulletRewrite, Insights
from app.jd.schema import JobProfile, SkillRequirement
from app.llm import LLMError
from app.resume.schema import Experience, ResumeProfile

RESUME = ResumeProfile(
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


def test_analyze_returns_report(client, fake_llm):
    fake_llm.results[JobProfile] = JobProfile(
        must_have=[SkillRequirement(skill="Python"), SkillRequirement(skill="Kubernetes")],
    )
    fake_llm.results[Insights] = Insights(summary="Decent fit", bullet_rewrites=[rewrite("Invented bullet")])

    resp = client.post("/analyses", json={"resume": RESUME.model_dump(), "job_description": JD_TEXT})

    assert resp.status_code == 200
    body = resp.json()
    assert body["match"]["score"] == 50  # 1 of 2 must-haves, computed by code
    assert body["insights"]["summary"] == "Decent fit"
    assert body["insights"]["bullet_rewrites"] == []  # invented original dropped
    # The insights prompt sees the code-computed match, not just raw text.
    assert "Kubernetes -> missing" in fake_llm.calls[-1]["user"]


def test_analyze_rejects_tiny_job_description(client, fake_llm):
    resp = client.post("/analyses", json={"resume": RESUME.model_dump(), "job_description": "python"})
    assert resp.status_code == 422
    assert fake_llm.calls == []


def test_analyze_maps_llm_failure_to_502(client, fake_llm):
    fake_llm.results[JobProfile] = LLMError("down")
    resp = client.post("/analyses", json={"resume": RESUME.model_dump(), "job_description": JD_TEXT})
    assert resp.status_code == 502
