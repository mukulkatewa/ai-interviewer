import pytest
from starlette.websockets import WebSocketDisconnect

from app.analysis.schema import Insights
from app.auth import CurrentUser, InvalidToken, get_token_verifier
from app.config import get_settings
from app.deps import get_tts
from app.jd.schema import JobProfile, SkillRequirement
from app.main import app
from app.resume.schema import ResumeProfile
from app.speech.tts import TTSError
from tests.conftest import RESUME_TEXT, USER_A, USER_B, make_pdf

# Tokens the fake verifier accepts, and whose user they are.
TOKENS = {"token-a": USER_A, "token-b": USER_B}


class FakeTTS:
    """Returns fake MP3 bytes per sentence; can be told to fail from sentence N on."""

    def __init__(self, fail_from: int | None = None):
        self.fail_from = fail_from
        self.sentences: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        if self.fail_from is not None and len(self.sentences) >= self.fail_from:
            raise TTSError("kokoro down")
        self.sentences.append(text)
        return f"mp3:{text}".encode()


def fake_verify(token: str) -> CurrentUser:
    if token not in TOKENS:
        raise InvalidToken
    return CurrentUser(id=TOKENS[token])


@pytest.fixture
def tts(client):
    fake = FakeTTS()
    app.dependency_overrides[get_token_verifier] = lambda: fake_verify
    app.dependency_overrides[get_tts] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_token_verifier, None)
    app.dependency_overrides.pop(get_tts, None)


@pytest.fixture
def analysis_id(client, fake_llm) -> str:
    """A saved analysis for USER_A: Rahul's resume vs a Razorpay backend JD."""
    fake_llm.results[ResumeProfile] = ResumeProfile(name="Rahul Sharma", skills=["Python"])
    fake_llm.results[JobProfile] = JobProfile(
        title="Backend Engineer", company="Razorpay", must_have=[SkillRequirement(skill="Python")]
    )
    fake_llm.results[Insights] = Insights(summary="Good fit")
    resume_id = client.post("/resumes", files={"file": ("r.pdf", make_pdf(RESUME_TEXT), "application/pdf")}).json()["id"]
    jd = "Backend Engineer at Razorpay. Must have Python and REST APIs experience. " * 2
    return client.post("/analyses", json={"resume_id": resume_id, "job_description": jd}).json()["id"]


@pytest.fixture
def interview_id(client, analysis_id) -> str:
    return client.post("/interviews", json={"analysis_id": analysis_id}).json()["id"]


# --- HTTP -----------------------------------------------------------------------


def test_create_interview_from_own_analysis(client, analysis_id):
    resp = client.post("/interviews", json={"analysis_id": analysis_id})

    assert resp.status_code == 201
    body = resp.json()
    assert (body["status"], body["candidate_name"], body["job_title"], body["company"]) == (
        "created",
        "Rahul Sharma",
        "Backend Engineer",
        "Razorpay",
    )
    assert client.get(f"/interviews/{body['id']}").json() == body


def test_cannot_use_or_see_other_users_interviews(client, analysis_id, interview_id, login):
    login(USER_B)

    assert client.post("/interviews", json={"analysis_id": analysis_id}).status_code == 404
    assert client.get(f"/interviews/{interview_id}").status_code == 404


# --- WebSocket: auth ------------------------------------------------------------


def connect(client, interview_id: str):
    return client.websocket_connect(f"/interviews/{interview_id}/ws")


def closed_with(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return exc.value.code


@pytest.mark.parametrize(
    "first_message",
    [
        pytest.param({"type": "start"}, id="not-auth"),
        pytest.param({"type": "auth", "token": "forged"}, id="bad-token"),
        pytest.param({"type": "auth"}, id="no-token"),
    ],
)
def test_socket_rejects_unauthenticated(client, tts, interview_id, first_message):
    with connect(client, interview_id) as ws:
        ws.send_json(first_message)
        assert closed_with(ws) == 4401


def test_socket_closes_if_auth_never_arrives(client, tts, interview_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "ws_auth_timeout_s", 0.05)
    with connect(client, interview_id) as ws:
        assert closed_with(ws) == 4401


def test_socket_hides_other_users_interview(client, tts, interview_id):
    with connect(client, interview_id) as ws:
        ws.send_json({"type": "auth", "token": "token-b"})
        assert closed_with(ws) == 4404


# --- WebSocket: speaking --------------------------------------------------------


def start(ws) -> None:
    ws.send_json({"type": "auth", "token": "token-a"})
    assert ws.receive_json()["type"] == "ready"
    ws.send_json({"type": "start"})


def test_start_speaks_intro_sentence_by_sentence(client, tts, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)

        caption = ws.receive_json()
        assert caption["type"] == "transcript" and caption["role"] == "interviewer"
        assert caption["text"].startswith("Hi Rahul! I'm your interviewer today for the Backend Engineer role at Razorpay.")

        # audio_meta then its binary frame, in order, for every sentence.
        for seq, sentence in enumerate(tts.sentences):
            assert ws.receive_json() == {"type": "audio_meta", "seq": seq, "text": sentence}
            assert ws.receive_bytes() == f"mp3:{sentence}".encode()
        assert ws.receive_json() == {"type": "turn_end", "phase": "intro"}

    assert tts.sentences[0] == "Hi Rahul!"  # short opener -> fast first audio (D23)
    assert " ".join(tts.sentences) == caption["text"]
    assert client.get(f"/interviews/{interview_id}").json()["status"] == "in_progress"


def test_tts_failure_hands_remaining_text_to_browser(client, tts, interview_id):
    tts.fail_from = 1  # first sentence works, then Kokoro goes down

    with connect(client, interview_id) as ws:
        start(ws)
        caption = ws.receive_json()["text"]
        assert ws.receive_json()["type"] == "audio_meta"
        ws.receive_bytes()

        error = ws.receive_json()
        assert error["code"] == "tts_unavailable"
        assert caption == f"Hi Rahul! {error['text']}"  # exactly the unspoken rest
        assert ws.receive_json()["type"] == "turn_end"  # the interview carries on


def drain_until_turn_end(ws) -> None:
    while True:
        message = ws.receive()
        if "text" in message and '"turn_end"' in message["text"]:
            return


def test_start_twice_is_refused(client, tts, interview_id):
    with connect(client, interview_id) as ws:
        start(ws)
        drain_until_turn_end(ws)
    # e.g. a second tab, or a reload after the interview began
    with connect(client, interview_id) as ws:
        start(ws)
        assert ws.receive_json()["code"] == "already_started"


def test_unknown_message_gets_error_not_disconnect(client, tts, interview_id):
    with connect(client, interview_id) as ws:
        ws.send_json({"type": "auth", "token": "token-a"})
        ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["code"] == "bad_message"
        ws.send_json({"type": "end"})
