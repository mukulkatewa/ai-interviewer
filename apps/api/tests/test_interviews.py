"""Interviews: HTTP routes and the live WebSocket conversation (phases 6-8)."""

import asyncio
import json

import asyncpg
import pytest
from starlette.websockets import WebSocketDisconnect

from app.analysis.schema import Insights
from app.auth import CurrentUser, InvalidToken, get_token_verifier
from app.config import get_settings
from app.deps import get_live_llm, get_stt, get_tts
from app.interview import script
from app.interview.plan import InterviewPlan, PlannedQuestion
from app.interview.speaker import ACKNOWLEDGEMENTS
from app.jd.schema import JobProfile, SkillRequirement
from app.llm import LLMError
from app.main import app
from app.resume.schema import ResumeProfile
from app.speech.stt import STTBusyError, Transcript
from app.speech.tts import TTSError
from tests.conftest import RESUME_TEXT, TEST_DATABASE_URL, USER_A, USER_B, make_pdf
from tests.test_voice_in import make_wav

PLAN = InterviewPlan(
    questions=[
        PlannedQuestion(phase="resume_deep_dive", question="How did you build the Acme service?", focus="ownership"),
        PlannedQuestion(phase="role_skills", question="How would you design a payments API?", focus="API design"),
        PlannedQuestion(phase="behavioral", question="Tell me about a conflict you resolved.", focus="STAR"),
    ]
)
Q1, Q2, Q3 = (q.question for q in PLAN.questions)

# Tokens the fake verifier accepts, and whose user they are.
TOKENS = {"token-a": USER_A, "token-b": USER_B}


# --- fakes ----------------------------------------------------------------------


class FakeTTS:
    """Fake MP3 per sentence; can be told to fail from the Nth call on."""

    def __init__(self):
        self.fail_from: int | None = None
        self.calls: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        if self.fail_from is not None and len(self.calls) > self.fail_from:
            raise TTSError("kokoro down")
        return f"mp3:{text}".encode()


class FakeSTT:
    def __init__(self):
        self.text: str | Exception = "I built a FastAPI service at Acme."
        self.prompts: list[str | None] = []

    async def transcribe(self, wav: bytes, prompt: str | None = None) -> Transcript:
        self.prompts.append(prompt)
        if isinstance(self.text, Exception):
            raise self.text
        return Transcript(text=self.text, segments=[{"start": 0, "end": 2.5, "text": self.text}], stt_ms=300)


class FakeLive:
    """Streams scripted replies in small chunks (so ACTION lines split across chunks, like real streaming)."""

    def __init__(self):
        self.replies: list[str | Exception] = []
        self.prompts: list[tuple[str, str]] = []

    async def stream_text(self, system: str, user: str):
        self.prompts.append((system, user))
        reply = self.replies.pop(0) if self.replies else "ACTION: NEXT\nThat's useful context."
        if isinstance(reply, Exception):
            raise reply
        for i in range(0, len(reply), 7):
            yield reply[i : i + 7]


def fake_verify(token: str) -> CurrentUser:
    if token not in TOKENS:
        raise InvalidToken
    return CurrentUser(id=TOKENS[token])


@pytest.fixture
def fakes(client):
    tts, stt, live = FakeTTS(), FakeSTT(), FakeLive()
    overrides = {get_token_verifier: lambda: fake_verify, get_tts: lambda: tts, get_stt: lambda: stt, get_live_llm: lambda: live}
    app.dependency_overrides.update(overrides)
    yield tts, stt, live
    for dep in overrides:
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def analysis_id(client, fake_llm) -> str:
    """A saved analysis for USER_A: Rahul's resume vs a Razorpay backend JD."""
    fake_llm.results[ResumeProfile] = ResumeProfile(name="Rahul Sharma", skills=["Python"])
    fake_llm.results[JobProfile] = JobProfile(
        title="Backend Engineer", company="Razorpay", must_have=[SkillRequirement(skill="Python")]
    )
    fake_llm.results[Insights] = Insights(summary="Good fit")
    fake_llm.results[InterviewPlan] = PLAN
    resume_id = client.post("/resumes", files={"file": ("r.pdf", make_pdf(RESUME_TEXT), "application/pdf")}).json()["id"]
    jd = "Backend Engineer at Razorpay. Must have Python and REST APIs experience. " * 2
    return client.post("/analyses", json={"resume_id": resume_id, "job_description": jd}).json()["id"]


@pytest.fixture
def interview_id(client, analysis_id) -> str:
    return client.post("/interviews", json={"analysis_id": analysis_id}).json()["id"]


def db_rows(sql: str, *args) -> list[asyncpg.Record]:
    async def fetch():
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(fetch())


# --- socket helpers -------------------------------------------------------------


def connect(client, interview_id: str):
    return client.websocket_connect(f"/interviews/{interview_id}/ws")


def closed_with(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return exc.value.code


def auth(ws, token: str = "token-a") -> dict:
    ws.send_json({"type": "auth", "token": token})
    return ws.receive_json()


def read_reply(ws) -> tuple[list[dict], dict]:
    """Collect one interviewer reply: its sentences (with audio checked), then the message that ends it."""
    sentences: list[dict] = []
    while True:
        message = ws.receive_json()
        if message["type"] == "sentence":
            if message["audio"]:
                assert ws.receive_bytes() == f"mp3:{message['text']}".encode()
            sentences.append(message)
        elif message["type"] != "reply_start":
            return sentences, message


def spoken(sentences: list[dict]) -> str:
    return " ".join(s["text"] for s in sentences)


def start(ws) -> list[dict]:
    assert auth(ws)["type"] == "ready"
    ws.send_json({"type": "start"})
    sentences, end = read_reply(ws)
    assert end == {"type": "turn_end", "question": 0}
    return sentences


def answer(ws) -> tuple[list[dict], dict]:
    ws.send_bytes(make_wav(2))
    assert ws.receive_json()["type"] == "transcript"
    return read_reply(ws)


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


# --- the conversation -----------------------------------------------------------


def test_intro_is_spoken_sentence_by_sentence_and_saved(client, fakes, interview_id):
    with connect(client, interview_id) as ws:
        sentences = start(ws)

    assert sentences[0] == {"type": "sentence", "seq": 0, "text": "Hi Rahul!", "audio": True}  # short opener (D23)
    assert spoken(sentences).startswith("Hi Rahul! I'm your interviewer today for the Backend Engineer role at Razorpay.")
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
        assert auth(ws) == {"type": "ready", "interview_id": interview_id, "resumable": True}
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
