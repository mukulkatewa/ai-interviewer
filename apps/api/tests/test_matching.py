import pytest

from app.analysis.matching import match_resume
from app.analysis.skills import keys_in_text, skill_key
from app.jd.schema import JobProfile, SkillRequirement
from app.resume.schema import Experience, Project, ResumeProfile


def req(skill: str, *alternatives: str) -> SkillRequirement:
    return SkillRequirement(skill=skill, alternatives=list(alternatives))


RESUME = ResumeProfile(
    skills=["Python", "React.js", "Postgres"],
    experience=[
        Experience(
            company="Acme",
            role="Backend Intern",
            highlights=["Containerized 3 services with Docker", "Built REST APIs in FastAPI"],
            technologies=["Redis"],
        )
    ],
    projects=[Project(name="Chat", description="Realtime chat on Node.js", technologies=["k8s"])],
)


# --- normalization --------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("React.js", "react"),
        ("ReactJS", "React"),
        ("Node.js", "node"),
        ("PostgreSQL", "postgres"),
        ("k8s", "Kubernetes"),
        ("CI/CD", "ci-cd"),
        ("REST APIs", "RESTful API"),
        ("Google Cloud Platform", "GCP"),
        ("ASP.NET", "asp.net"),
    ],
)
def test_same_skill_same_key(a, b):
    assert skill_key(a) == skill_key(b)


@pytest.mark.parametrize(("a", "b"), [("Java", "JavaScript"), ("C", "C++"), ("C++", "C#"), ("SQL", "MySQL")])
def test_different_skills_different_keys(a, b):
    assert skill_key(a) != skill_key(b)


def test_keys_in_text_finds_multiword_and_dotted_names():
    keys = keys_in_text(["Shipped REST APIs on Node.js and Google Cloud Platform"])
    assert {"restapi", "nodejs", "gcp"} <= keys


def test_keys_in_text_ignores_ambiguous_words():
    assert "go" not in keys_in_text(["Owned the go-to-market launch"])


# --- matching -------------------------------------------------------------------


def statuses(job: JobProfile) -> dict[str, str]:
    result = match_resume(RESUME, job)
    return {m.requirement.skill: m.status for m in result.must_have.matches}


def test_listed_skills_match_via_aliases_and_technologies():
    job = JobProfile(must_have=[req("React"), req("PostgreSQL"), req("Redis"), req("Kubernetes")])
    assert set(statuses(job).values()) == {"listed"}


def test_skill_only_in_bullets_is_mentioned():
    job = JobProfile(must_have=[req("Docker"), req("REST APIs"), req("Node.js")])
    assert set(statuses(job).values()) == {"mentioned"}


def test_alternative_satisfies_requirement():
    job = JobProfile(must_have=[req("Go", "Python")])
    match = match_resume(RESUME, job).must_have.matches[0]
    assert (match.status, match.matched_as) == ("listed", "Python")


def test_missing_skill():
    assert statuses(JobProfile(must_have=[req("Rust")])) == {"Rust": "missing"}


# --- scoring --------------------------------------------------------------------


def test_score_weights_must_have_over_nice_to_have():
    # must: 1/2 met, nice: 1/1 met -> 100 * (0.8*0.5 + 0.2*1.0) = 60
    job = JobProfile(must_have=[req("Python"), req("Rust")], nice_to_have=[req("Docker")])
    assert match_resume(RESUME, job).score == 60


def test_score_without_nice_to_have_is_not_capped():
    job = JobProfile(must_have=[req("Python")])
    assert match_resume(RESUME, job).score == 100


def test_score_is_none_when_jd_lists_no_skills():
    result = match_resume(RESUME, JobProfile())
    assert result.score is None
    assert result.must_have.ratio is None
