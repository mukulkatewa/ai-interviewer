"""Phase 10: per-user daily limits (D32) and "delete all my data"."""

from app.config import get_settings
from tests.conftest import RESUME_TEXT, USER_A, USER_B, make_pdf
from tests.interview_fixtures import connect, db_rows, read_reply, start


def upload(client):
    return client.post("/resumes", files={"file": ("r.pdf", make_pdf(RESUME_TEXT), "application/pdf")})


def test_limit_blocks_before_any_llm_spend(client, fake_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "limit_resumes_per_day", 1)
    assert upload(client).status_code == 201

    resp = upload(client)

    assert resp.status_code == 429
    assert "limit of 1 resume uploads" in resp.json()["detail"]
    assert 0 < int(resp.headers["Retry-After"]) <= 86_400  # until the first upload is 24 h old
    assert len(fake_llm.calls) == 1  # the blocked request never reached the model


def test_limits_are_per_user(client, fake_llm, monkeypatch, login):
    monkeypatch.setattr(get_settings(), "limit_resumes_per_day", 1)
    upload(client)

    login(USER_B)

    assert upload(client).status_code == 201


def test_interview_limit_blocks_before_planning(client, fakes, analysis_id, fake_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "limit_interviews_per_day", 1)
    assert client.post("/interviews", json={"analysis_id": analysis_id}).status_code == 201
    calls = len(fake_llm.calls)

    assert client.post("/interviews", json={"analysis_id": analysis_id}).status_code == 429
    assert len(fake_llm.calls) == calls  # no plan generated


def test_delete_my_data_removes_everything_mine_only(client, fakes, interview_id, login):
    with connect(client, interview_id) as ws:  # leaves turns and a queued report job behind
        start(ws)
        ws.send_json({"type": "end"})
        read_reply(ws)
    login(USER_B)
    upload(client)  # someone else's data must survive
    login(USER_A)

    assert client.delete("/me/data").status_code == 204

    for path in ("/resumes", "/analyses", "/interviews"):
        assert client.get(path).json() == []
    for table in ("job_descriptions", "interview_turns", "jobs"):
        assert db_rows(f"select 1 from {table}") == []
    login(USER_B)
    assert len(client.get("/resumes").json()) == 1


def test_keepalive_moves_the_timestamp_and_never_adds_rows(client):
    """The function behind the scheduled keep-alive (D39): one row, updated on every call."""
    first, second = (db_rows("select public.keepalive() as at")[0]["at"] for _ in range(2))
    assert second >= first
    assert db_rows("select count(*) as n from public.keepalive")[0]["n"] == 1
