import pytest

from app.llm import LLMError
from app.resume.extract import ResumeExtractionError, extract_text
from tests.conftest import RESUME_TEXT, make_pdf


def upload(client, data: bytes, name: str = "resume.pdf"):
    return client.post("/resumes/parse", files={"file": (name, data, "application/pdf")})


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


# --- Endpoint -------------------------------------------------------------------


def test_parse_resume_returns_profile(client, fake_llm):
    resp = upload(client, make_pdf(RESUME_TEXT))

    assert resp.status_code == 200
    assert resp.json()["name"] == "Asha Verma"
    # Resume reaches the model wrapped as untrusted data.
    assert fake_llm.calls[0]["user"].startswith("<resume>\nAsha Verma")


def test_parse_resume_checks_magic_bytes_not_header(client, fake_llm):
    resp = upload(client, b"MZ this is an exe", name="evil.pdf")
    assert resp.status_code == 415
    assert fake_llm.calls == []


def test_parse_resume_rejects_large_file(client, fake_llm):
    resp = upload(client, b"%PDF-" + b"0" * (5 * 1024 * 1024))
    assert resp.status_code == 413


def test_parse_resume_maps_llm_failure_to_502(client, fake_llm):
    fake_llm.result = LLMError("bad json")
    resp = upload(client, make_pdf(RESUME_TEXT))
    assert resp.status_code == 502
