import json

import httpx
import pytest

from app.speech.text import split_sentences
from app.speech.tts import KokoroTTS, TTSError

# --- sentence splitting ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hi Rahul! Let's begin. Ready?", ["Hi Rahul!", "Let's begin.", "Ready?"]),
        ("  One sentence only  ", ["One sentence only"]),
        ("I used Node.js and Socket.io. Then Redis.", ["I used Node.js and Socket.io.", "Then Redis."]),
        ("Use a cache, e.g. Redis. Next question.", ["Use a cache, e.g. Redis.", "Next question."]),
        ("It took 3.5 s. 2 retries later it worked.", ["It took 3.5 s.", "2 retries later it worked."]),
        ("", []),
    ],
)
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected


# --- Kokoro client --------------------------------------------------------------


def kokoro(handler) -> KokoroTTS:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return KokoroTTS(http, "http://kokoro:8880/", voice="af_heart")


async def test_synthesize_posts_sentence_and_returns_mp3():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ID3-mp3-bytes")

    audio = await kokoro(handler).synthesize("Hi Rahul!")

    assert audio == b"ID3-mp3-bytes"
    assert str(seen[0].url) == "http://kokoro:8880/v1/audio/speech"
    assert json.loads(seen[0].content) == {
        "model": "kokoro",
        "input": "Hi Rahul!",
        "voice": "af_heart",
        "response_format": "mp3",
    }


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(lambda r: httpx.Response(500), id="server-error"),
        pytest.param(lambda r: httpx.Response(200, content=b""), id="empty-audio"),
        pytest.param(lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")), id="down"),
    ],
)
async def test_synthesize_failures_raise_tts_error(handler):
    with pytest.raises(TTSError):
        await kokoro(handler).synthesize("Hi")
