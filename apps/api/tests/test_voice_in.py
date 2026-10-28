"""Phase 7 building blocks: WAV validation, Whisper client, vocabulary prompt."""

import io
import wave
from types import SimpleNamespace

import groq
import httpx
import pytest

from app.interview.vocabulary import MAX_TERMS, vocabulary_prompt
from app.jd.schema import JobProfile, SkillRequirement
from app.resume.schema import Education, Experience, Project, ResumeProfile
from app.speech.stt import GroqWhisper, STTBusyError, STTError
from app.speech.wav import AnswerTooLong, BadAudio, max_answer_bytes, wav_duration


def make_wav(seconds: float, rate: int = 16_000, channels: int = 1, width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return buf.getvalue()


# --- WAV ------------------------------------------------------------------------


def test_wav_duration_of_valid_answer():
    assert wav_duration(make_wav(3.5)) == pytest.approx(3.5)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"not a wav at all", id="garbage"),
        pytest.param(make_wav(2, rate=44_100), id="wrong-rate"),
        pytest.param(make_wav(2, channels=2), id="stereo"),
        pytest.param(make_wav(2, width=1), id="8-bit"),
        pytest.param(make_wav(0.1), id="too-short"),
    ],
)
def test_wav_rejects_bad_audio(data):
    with pytest.raises(BadAudio):
        wav_duration(data)


def test_wav_rejects_long_answer_before_parsing():
    with pytest.raises(AnswerTooLong):
        wav_duration(b"\x00" * (max_answer_bytes() + 1))


# --- Whisper client -------------------------------------------------------------


class FakeTranscriptions:
    def __init__(self, result):
        self.result = result
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def whisper(result) -> tuple[GroqWhisper, FakeTranscriptions]:
    fake = FakeTranscriptions(result)
    return GroqWhisper(SimpleNamespace(audio=SimpleNamespace(transcriptions=fake)), "whisper-large-v3-turbo"), fake


async def test_transcribe_returns_text_segments_and_sends_prompt():
    result = SimpleNamespace(text=" I used Redis. ", segments=[{"start": 0.0, "end": 1.2, "text": " I used Redis. "}])
    client, fake = whisper(result)

    transcript = await client.transcribe(b"wav", prompt="In this interview we talked about Redis.")

    assert transcript.text == "I used Redis."
    assert [(s.start, s.end, s.text) for s in transcript.segments] == [(0.0, 1.2, "I used Redis.")]
    assert fake.kwargs["prompt"] == "In this interview we talked about Redis."
    assert (fake.kwargs["language"], fake.kwargs["response_format"]) == ("en", "verbose_json")


async def test_transcribe_omits_prompt_when_none():
    client, fake = whisper(SimpleNamespace(text="hi", segments=[]))
    await client.transcribe(b"wav")
    assert "prompt" not in fake.kwargs


def _groq_error(cls, status: int):
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com"))
    return cls("err", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [(_groq_error(groq.RateLimitError, 429), STTBusyError), (_groq_error(groq.InternalServerError, 500), STTError)],
)
async def test_transcribe_maps_errors(error, expected):
    client, _ = whisper(error)
    with pytest.raises(expected):
        await client.transcribe(b"wav")


# --- vocabulary prompt (D24) ----------------------------------------------------


def test_vocabulary_is_a_natural_sentence_with_must_haves_first():
    resume = ResumeProfile(
        skills=["React", "redis"],
        experience=[Experience(company="Flipkart", role="Intern", technologies=["MongoDB"])],
        projects=[Project(name="DevChat")],
    )
    job = JobProfile(
        company="Razorpay",
        must_have=[SkillRequirement(skill="Python", alternatives=["Go"]), SkillRequirement(skill="Redis")],
    )

    prompt = vocabulary_prompt(resume, job)

    assert prompt == (
        "In this interview we talked about Python, Redis, Go, React, MongoDB, DevChat, Flipkart and Razorpay."
    )  # "redis" deduplicated case-insensitively


def test_vocabulary_starts_with_the_candidates_name_and_school():
    resume = ResumeProfile(
        name="Mukul Katewa",
        skills=["React"],
        education=[Education(institution="NIT Trichy", degree="B.Tech")],
    )
    assert vocabulary_prompt(resume, JobProfile()) == (
        "This is an interview with Mukul Katewa, who studied at NIT Trichy. In this interview we talked about React."
    )
    # Name alone, school alone, and neither:
    assert (
        vocabulary_prompt(ResumeProfile(name="Mukul Katewa"), JobProfile()) == "This is an interview with Mukul Katewa."
    )
    assert vocabulary_prompt(ResumeProfile(education=[Education(institution="NIT Trichy")]), JobProfile()) == (
        "The candidate studied at NIT Trichy."
    )


def test_vocabulary_is_capped_and_none_when_empty():
    many = ResumeProfile(skills=[f"Skill{i}" for i in range(100)])
    assert vocabulary_prompt(many, JobProfile()).count(",") == MAX_TERMS - 2  # N terms -> N-2 commas + "and"
    assert vocabulary_prompt(ResumeProfile(), JobProfile()) is None
