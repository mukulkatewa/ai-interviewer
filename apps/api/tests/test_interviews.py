"""Interviews: HTTP routes and the live WebSocket conversation (phases 6-8)."""

import json
from uuid import UUID

import pytest

from app.config import get_settings
from app.interview import script
from app.interview.plan import InterviewPlan
from app.interview.speaker import ACKNOWLEDGEMENTS
from app.llm import LLMError
from app.resume.schema import ResumeProfile
from app.speech.stt import STTBusyError
from tests.conftest import RESUME_TEXT, USER_B, make_pdf
from tests.interview_fixtures import (
    PLAN,
    Q1,
    Q2,
    answer,
    auth,
    closed_with,
    connect,
    db_rows,
    read_reply,
    spoken,
    start,
)
from tests.test_voice_in import make_wav

# --- HTTP -----------------------------------------------------------------------


def test_create_interview_from_own_analysis(client, analysis_id):
    resp = client.post("/interviews", json={"analysis_id": analysis_id})

    assert resp.status_code == 201
    body = resp.json()
    assert (body["status"], body["candidate_name"], body["job_title"], body["company"]) == (
        "created", "Rahul Sharma", "Backend Engineer", "Razorpay",
    )  # fmt: skip
    assert client.get(f"/interviews/{body['id']}").json() == body
    assert "plan" not in body  # candidates must not see the questions in advance


def test_create_interview_plans_from_resume_job_and_gaps(client, analysis_id, fake_llm):
    client.post("/interviews", json={"analysis_id": analysis_id})

    call = fake_llm.calls[-1]
    assert call["schema"] is InterviewPlan
    assert "Rahul Sharma" in call["user"] and "Razorpay" in call["user"]
    assert "<gaps>none</gaps>" in call["user"]  # Python is listed on the resume, so no gap


def test_cannot_use_or_see_other_users_interviews(client, analysis_id, interview_id, login):
    login(USER_B)

    assert client.post("/interviews", json={"analysis_id": analysis_id}).status_code == 404
    assert client.get(f"/interviews/{interview_id}").status_code == 404


# --- no job description (D36) ----------------------------------------------------


@pytest.fixture
def resume_id(client, fake_llm) -> str:
    fake_llm.results[ResumeProfile] = ResumeProfile(name="Rahul Sharma", skills=["Python"])
    fake_llm.results[InterviewPlan] = PLAN
    pdf = make_pdf(RESUME_TEXT)
    return client.post("/resumes", files={"file": ("r.pdf", pdf, "application/pdf")}).json()["id"]


def test_start_an_interview_from_a_resume_alone(client, resume_id, fake_llm):
    resp = client.post("/interviews", json={"resume_id": resume_id, "target_role": "  Data Analyst "})

    assert resp.status_code == 201
    body = resp.json()
    assert (body["analysis_id"], body["resume_id"], body["job_title"], body["company"]) == (
        None, resume_id, "Data Analyst", None,
    )  # fmt: skip
    note = fake_llm.calls[-1]["user"]
    assert "No job description was given" in note and "Data Analyst" in note


def test_resume_only_interview_works_without_a_role(client, resume_id):
    body = client.post("/interviews", json={"resume_id": resume_id}).json()
    assert body["job_title"] is None
    assert script.intro(repo_interview(body)).count("general practice interview") == 1


def repo_interview(body: dict):
    from app.interview.repo import Interview

    return Interview(**body)


def test_resume_only_interview_runs_and_ends_like_any_other(client, fakes, resume_id):
    interview_id = client.post("/interviews", json={"resume_id": resume_id}).json()["id"]
    with connect(client, interview_id) as ws:
        start(ws)
        ws.send_json({"type": "end"})
        read_reply(ws)
    assert db_rows("select status from interviews where id = $1", UUID(interview_id))[0][0] == "evaluating"


def test_request_needs_exactly_one_source(client, analysis_id, resume_id):
    assert client.post("/interviews", json={}).status_code == 422
    assert client.post("/interviews", json={"analysis_id": analysis_id, "resume_id": resume_id}).status_code == 422


def test_cannot_start_from_someone_elses_resume(client, resume_id, login):
    login(USER_B)
    assert client.post("/interviews", json={"resume_id": resume_id}).status_code == 404


def test_deleting_the_resume_deletes_its_resume_only_interviews(client, resume_id):
    interview_id = client.post("/interviews", json={"resume_id": resume_id}).json()["id"]
    assert client.delete(f"/resumes/{resume_id}").status_code == 204
    assert client.get(f"/interviews/{interview_id}").status_code == 404


# --- WebSocket: auth ------------------------------------------------------------


@pytest.mark.parametrize(
    "first_message",
    [
        pytest.param({"type": "start"}, id="not-auth"),
        pytest.param({"type": "auth", "token": "forged"}, id="bad-token"),
        pytest.param({"type": "auth"}, id="no-token"),
    ],
)
def test_socket_rejects_unauthenticated(client, fakes, interview_id, first_message):
    with connect(client, interview_id) as ws:
        ws.send_json(first_message)
        assert closed_with(ws) == 4401


def test_socket_closes_if_auth_never_arrives(client, fakes, interview_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "ws_auth_timeout_s", 0.05)
    with connect(client, interview_id) as ws:
        assert closed_with(ws) == 4401


def test_socket_hides_other_users_interview(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        ws.send_json({"type": "auth", "token": "token-b"})
        assert closed_with(ws) == 4404


# --- limits (D42) ------------------------------------------------------------------


def test_a_full_server_refuses_new_interviews_but_lets_a_live_one_reconnect(client, fakes, interview_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_live_interviews", 1)
    other = client.post("/interviews", json={"analysis_id": client.get("/analyses").json()[0]["id"]}).json()["id"]

    with connect(client, interview_id) as first:
        assert auth(first)["type"] == "ready"  # takes the only slot
        with connect(client, other) as second:
            second.send_json({"type": "auth", "token": "token-a"})
            assert second.receive_json()["code"] == "busy"
            assert closed_with(second) == 1013
        with connect(client, interview_id) as same_tab:  # same interview: takes over, doesn't need a new slot
            assert auth(same_tab)["type"] == "ready"


def test_one_address_cannot_hold_unlimited_sockets(client, fakes, interview_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "ws_max_per_ip", 1)
    with connect(client, interview_id) as first:
        assert auth(first)["type"] == "ready"
        with connect(client, interview_id) as second:
            assert second.receive_json()["code"] == "busy"
            assert closed_with(second) == 1013
    with connect(client, interview_id) as after:  # the slot is released when the first one leaves
        assert auth(after)["type"] == "ready"


# --- the conversation -----------------------------------------------------------


def test_intro_is_spoken_sentence_by_sentence_and_saved(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        sentences = start(ws)

    assert sentences[0] == {"type": "sentence", "seq": 0, "text": "Hi Rahul!", "audio": True}  # short opener (D23)
    assert spoken(sentences).startswith(
        "Hi Rahul! I'm your interviewer today for the Backend Engineer role at Razorpay."
    )
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "in_progress"
    [turn] = db_rows("select role, question_index, text from interview_turns where interview_id = $1", interview_id)
    assert (turn["role"], turn["question_index"]) == ("interviewer", 0)


def test_intro_answer_acknowledges_then_asks_first_planned_question_verbatim(client, fakes, interview_id):
    _, _, live = fakes
    live.replies = ["ACTION: FOLLOW_UP\nWhat was your favourite part?"]  # not allowed after the intro

    with connect(client, interview_id) as ws:
        start(ws)
        sentences, end = answer(ws)

    assert sentences[0]["text"] in ACKNOWLEDGEMENTS and sentences[0]["audio"]  # instant, cached (D23)
    assert spoken(sentences[1:]) == Q1  # FOLLOW_UP overridden to NEXT; code asks Q1 word for word (D29)
    assert end == {"type": "turn_end", "question": 1}
    assert "Allowed actions: NEXT" in live.prompts[0][1]


def test_one_follow_up_per_question_then_code_moves_on(client, fakes, interview_id):
    _, _, live = fakes
    live.replies = [
        "ACTION: NEXT\nThanks for the overview.",
        "ACTION: FOLLOW_UP\nWhat was your own part in it?",
        "ACTION: FOLLOW_UP\nAnd what would you change?",  # budget used: becomes NEXT
    ]
    with connect(client, interview_id) as ws:
        start(ws)
        answer(ws)  # intro -> Q1
        follow_up, end1 = answer(ws)
        moved_on, end2 = answer(ws)

    assert spoken(follow_up[1:]) == "What was your own part in it?" and end1["question"] == 1
    assert moved_on[-1]["text"] == Q2 and end2["question"] == 2
    assert "And what would you change?" not in spoken(moved_on)


def test_next_reaction_never_asks_its_own_question(client, fakes, interview_id):
    _, _, live = fakes
    live.replies = ["ACTION: NEXT\nInteresting work on the dashboard. What about testing?"]
    with connect(client, interview_id) as ws:
        start(ws)
        sentences, _ = answer(ws)

    assert spoken(sentences[1:]) == f"Interesting work on the dashboard. {Q1}"  # one question per turn (D29)


def test_latency_recorded_even_when_the_models_reaction_is_dropped(client, fakes, interview_id):
    _, _, live = fakes
    live.replies = ["ACTION: NEXT\nWhat about testing?"]  # only a question: nothing from the model is spoken
    with connect(client, interview_id) as ws:
        start(ws)
        sentences, _ = answer(ws)

    assert spoken(sentences[1:]) == Q1  # just the planned question after the acknowledgement
    reply = db_rows("select llm_ms from interview_turns where role = 'interviewer' order by seq")[1]
    assert reply["llm_ms"] is not None


def test_llm_failure_uses_scripted_transition(client, fakes, interview_id):
    _, _, live = fakes
    live.replies = [LLMError("groq down")]
    with connect(client, interview_id) as ws:
        start(ws)
        sentences, end = answer(ws)

    assert spoken(sentences[1:]) == f"Let's move on. {Q1}"
    assert end["question"] == 1


def test_full_interview_runs_to_wrap_up_and_ends(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)
        for expected_question in (1, 2, 3, 4):  # intro answer -> Q1..Q3 -> wrap-up (4)
            sentences, end = answer(ws)
            assert end["question"] == expected_question
        assert spoken(sentences[1:]).endswith(script.WRAP_UP)

        sentences, end = answer(ws)  # answers the wrap-up
        assert spoken(sentences).endswith("Your feedback report will be ready in about a minute.")
        assert end == {"type": "ended", "interview_id": interview_id}

    assert client.get(f"/interviews/{interview_id}").json()["status"] == "evaluating"
    turns = db_rows(
        "select role, stt_ms, llm_ms, segments from interview_turns where interview_id = $1 order by seq", interview_id
    )
    assert [t["role"] for t in turns] == ["interviewer", "candidate"] * 5 + ["interviewer"]
    candidate = turns[1]
    assert candidate["stt_ms"] == 300 and json.loads(candidate["segments"])[0]["end"] == 2.5  # for phase 9 metrics
    assert all(t["llm_ms"] is not None for t in turns[2::2])  # latency recorded per reply


def test_time_limit_skips_to_wrap_up(client, fakes, interview_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "interview_max_minutes", 0)
    with connect(client, interview_id) as ws:
        start(ws)
        sentences, end = answer(ws)

    assert spoken(sentences).endswith(script.WRAP_UP)
    assert end["question"] == len(PLAN.questions) + 1


def test_end_early_closes_and_marks_for_report(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)
        ws.send_json({"type": "end"})
        sentences, end = read_reply(ws)

    assert spoken(sentences).startswith("No problem, let's stop here.")
    assert end["type"] == "ended"
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "evaluating"


def test_reconnect_resumes_with_last_question(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)
        answer(ws)  # now on Q1
    with connect(client, interview_id) as ws:  # e.g. network drop, page reload
        assert auth(ws) == {
            "type": "ready",
            "interview_id": interview_id,
            "resumable": True,
            "total": len(PLAN.questions),
        }
        ws.send_json({"type": "start"})
        sentences, end = read_reply(ws)

    assert spoken(sentences).startswith("Welcome back. Let's pick up where we left off.")
    assert spoken(sentences).endswith(Q1)
    assert end["question"] == 1


def test_second_tab_takes_over(client, fakes, interview_id):
    with connect(client, interview_id) as first:
        auth(first)
        with connect(client, interview_id) as second:
            assert auth(second)["type"] == "ready"
            assert closed_with(first) == 4409  # D30


def test_finished_interview_socket_just_says_ended(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)
        ws.send_json({"type": "end"})
        read_reply(ws)
    with connect(client, interview_id) as ws:
        assert auth(ws) == {"type": "ended", "interview_id": interview_id}


# --- resilience -----------------------------------------------------------------


def test_tts_failure_opens_breaker_and_browser_speaks(client, fakes, interview_id):
    tts, _, _ = fakes
    tts.fail_from = 1  # first sentence synthesizes, then Kokoro is down

    with connect(client, interview_id) as ws:
        sentences = start(ws)

    assert [s["audio"] for s in sentences] == [True] + [False] * (len(sentences) - 1)
    assert len(tts.calls) == 2  # breaker open after the failure: no timeout per sentence


def test_answer_before_turn_is_refused(client, fakes, interview_id):
    _, stt, _ = fakes
    with connect(client, interview_id) as ws:
        auth(ws)
        ws.send_bytes(make_wav(3))
        assert ws.receive_json()["code"] == "not_your_turn"
    assert stt.prompts == []  # no quota spent


def test_answer_uses_vocabulary_prompt(client, fakes, interview_id):
    _, stt, _ = fakes
    with connect(client, interview_id) as ws:
        start(ws)
        answer(ws)
    assert stt.prompts[0].startswith("In this interview we talked about Python")  # D24


@pytest.mark.parametrize(
    ("audio", "stt_text", "code"),
    [
        pytest.param(b"garbage", "x", "bad_audio", id="bad-audio"),
        pytest.param(make_wav(0.1), "x", "bad_audio", id="too-short"),
        pytest.param(b"\x00" * 5_000_000, "x", "answer_too_long", id="too-long"),
        pytest.param(make_wav(2), "", "no_speech", id="silence"),
        pytest.param(make_wav(2), STTBusyError("429"), "stt_busy", id="rate-limited"),
    ],
)
def test_unusable_answer_gives_turn_back(client, fakes, interview_id, audio, stt_text, code):
    _, stt, _ = fakes
    stt.text = stt_text
    with connect(client, interview_id) as ws:
        start(ws)
        ws.send_bytes(audio)
        assert ws.receive_json()["code"] == code
        assert ws.receive_json() == {"type": "turn_end", "question": 0}  # same question, answer again
    turns = db_rows("select role from interview_turns where interview_id = $1", interview_id)
    assert [t["role"] for t in turns] == ["interviewer"]  # nothing saved for the failed answer


def test_unknown_message_gets_error_not_disconnect(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        auth(ws)
        ws.send_text("not json")
        assert ws.receive_json()["code"] == "bad_message"


def test_resume_after_dropping_during_intro_replays_intro(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        auth(ws)
        ws.send_json({"type": "start"})
        ws.receive_json()  # reply_start, then the tab dies mid-intro
    db_rows("delete from interview_turns where interview_id = $1", interview_id)  # intro never got saved

    with connect(client, interview_id) as ws:
        assert auth(ws)["resumable"] is True
        ws.send_json({"type": "start"})
        sentences, end = read_reply(ws)

    assert spoken(sentences).startswith("Hi Rahul!")  # the intro, not the wrap-up
    assert end == {"type": "turn_end", "question": 0}


# --- ending the interview (D33) -------------------------------------------------


def test_end_while_the_interviewer_is_speaking_takes_effect_at_once(client, fakes, interview_id):
    tts, _, _ = fakes
    tts.delay = 0.15  # each sentence takes a moment, like real speech synthesis
    with connect(client, interview_id) as ws:
        auth(ws)
        ws.send_json({"type": "start"})
        assert ws.receive_json()["type"] == "reply_start"
        assert ws.receive_json()["type"] == "sentence"  # the intro is mid-way...
        ws.receive_bytes()
        ws.send_json({"type": "end"})  # ...and the candidate clicks End interview

        intro_sentences_after_end, kinds = 0, []
        while True:
            message = ws.receive_json()
            kinds.append(message["type"])
            if message["type"] == "sentence":
                if message["audio"]:
                    ws.receive_bytes()
                if not message["text"].startswith(("No problem", "That's the end", "Your feedback")):
                    intro_sentences_after_end += 1
            if message["type"] == "ended":
                break

    # The rest of the intro was cancelled, the closing was spoken, and no stale "your turn" followed.
    assert intro_sentences_after_end <= 1
    assert "turn_end" not in kinds
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "evaluating"
    assert len(db_rows("select 1 from jobs where kind = 'evaluate_interview'")) == 1


def test_candidate_asking_to_stop_ends_the_interview_without_another_question(client, fakes, interview_id):
    _, stt, live = fakes
    with connect(client, interview_id) as ws:
        start(ws)
        stt.text = "I want to stop the interview."
        ws.send_bytes(make_wav(2))
        assert ws.receive_json() == {"type": "transcript", "role": "candidate", "text": "I want to stop the interview."}
        sentences, end = read_reply(ws)

    assert spoken(sentences).startswith("No problem, let's stop here.")
    assert end["type"] == "ended"
    assert live.prompts == []  # the model was never asked for a next question
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "evaluating"
    assert len(db_rows("select 1 from jobs where kind = 'evaluate_interview'")) == 1


def test_a_technical_answer_mentioning_stop_does_not_end_the_interview(client, fakes, interview_id):
    _, stt, _ = fakes
    with connect(client, interview_id) as ws:
        start(ws)
        stt.text = "We stop the container before deleting the volume."
        _, end = answer(ws)
    assert end["type"] == "turn_end"


def test_end_before_the_interview_started_just_closes(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        auth(ws)
        ws.send_json({"type": "end"})
        assert closed_with(ws) == 1000
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "created"
