import pytest

from app.llm import LLMError
from app.resume.extract import ResumeExtractionError, extract_text
from app.resume.schema import ResumeProfile
from tests.conftest import RESUME_TEXT, USER_B, make_pdf


def upload(client, data: bytes, name: str = "resume.pdf"):
    return client.post("/resumes", files={"file": (name, data, "application/pdf")})


# --- Stage 1: text extraction -------------------------------------------------


def test_extract_text_reads_pdf_text():
    text = extract_text(make_pdf(RESUME_TEXT))
    assert "Asha Verma" in text
    assert "Cut p95 latency by 40%" in text
    assert "\n\n" not in text  # blank lines stripped


def test_extract_text_rejects_non_pdf():
    with pytest.raises(ResumeExtractionError, match="not a readable PDF"):
        extract_text(b"%PDF-garbage")


def test_extract_text_rejects_scanned_pdf():
    with pytest.raises(ResumeExtractionError, match="scanned"):
        extract_text(make_pdf("tiny"))


def test_extract_text_rejects_too_many_pages():
    with pytest.raises(ResumeExtractionError, match="longer than"):
        extract_text(make_pdf(RESUME_TEXT, pages=6))


# --- Upload -----------------------------------------------------------------------


def test_upload_parses_and_saves(client, fake_llm):
    resp = upload(client, make_pdf(RESUME_TEXT), name="asha.pdf")

    assert resp.status_code == 201
    body = resp.json()
    assert (body["file_name"], body["name"]) == ("asha.pdf", "Asha Verma")
    # Resume reaches the model wrapped as untrusted data.
    assert fake_llm.calls[0]["user"].startswith("<resume>\nAsha Verma")
    # And it was really persisted.
    assert client.get(f"/resumes/{body['id']}").json()["profile"]["skills"] == ["Python", "FastAPI"]


def test_upload_checks_magic_bytes_not_header(client, fake_llm):
    resp = upload(client, b"MZ this is an exe", name="evil.pdf")
    assert resp.status_code == 415
    assert fake_llm.calls == []


def test_upload_rejects_large_file(client, fake_llm):
    assert upload(client, b"%PDF-" + b"0" * (5 * 1024 * 1024)).status_code == 413


def test_upload_maps_llm_failure_to_502_and_saves_nothing(client, fake_llm):
    fake_llm.results[ResumeProfile] = LLMError("bad json")
    assert upload(client, make_pdf(RESUME_TEXT)).status_code == 502
    assert client.get("/resumes").json() == []


# --- Read / delete, and ownership ----------------------------------------------


def test_list_is_newest_first_and_summary_only(client, fake_llm):
    first = upload(client, make_pdf(RESUME_TEXT), name="a.pdf").json()
    second = upload(client, make_pdf(RESUME_TEXT), name="b.pdf").json()

    listed = client.get("/resumes").json()

    assert [r["id"] for r in listed] == [second["id"], first["id"]]
    assert "profile" not in listed[0]


def test_other_users_resume_is_invisible(client, fake_llm, login):
    resume_id = upload(client, make_pdf(RESUME_TEXT)).json()["id"]

    login(USER_B)

    assert client.get("/resumes").json() == []
    assert client.get(f"/resumes/{resume_id}").status_code == 404
    assert client.delete(f"/resumes/{resume_id}").status_code == 404


def test_delete_resume(client, fake_llm):
    resume_id = upload(client, make_pdf(RESUME_TEXT)).json()["id"]

    assert client.delete(f"/resumes/{resume_id}").status_code == 204
    assert client.get(f"/resumes/{resume_id}").status_code == 404


def test_requires_login(client, fake_llm):
    from app.auth import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user)
    assert client.get("/resumes").status_code == 401
