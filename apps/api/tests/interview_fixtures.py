"""Shared fakes, fixtures and socket helpers for interview tests.

Registered as a pytest plugin in conftest.py, so any test module can use the
fixtures (`fakes`, `analysis_id`, `interview_id`) without importing them.
"""

import asyncio

import asyncpg
import pytest
from starlette.websockets import WebSocketDisconnect

from app.analysis.schema import Insights
from app.auth import CurrentUser, InvalidToken, get_token_verifier
from app.deps import get_live_llm, get_stt, get_tts
from app.interview.plan import InterviewPlan, PlannedQuestion
from app.jd.schema import JobProfile, SkillRequirement
from app.main import app
from app.resume.schema import ResumeProfile
from app.speech.stt import Transcript
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
        self.delay = 0.0  # seconds per sentence: lets a test act while the interviewer is "speaking"
        self.calls: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        await asyncio.sleep(self.delay)
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
    overrides = {
        get_token_verifier: lambda: fake_verify,
        get_tts: lambda: tts,
        get_stt: lambda: stt,
        get_live_llm: lambda: live,
    }
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
    resume_id = client.post("/resumes", files={"file": ("r.pdf", make_pdf(RESUME_TEXT), "application/pdf")}).json()[
        "id"
    ]
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
