"""A second provider takes over when the main one is rate limited or failing (D46)."""

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.fallback import FallbackLLM, FallbackSTT, OpenAICompatClient
from app.llm import LLMBusyError, LLMError
from app.speech.stt import STTBusyError, STTError, Transcript


class Out(BaseModel):
    who: str = ""


class Llm:
    """Answers with `who`, or raises `error`; streams `chunks` (raising `error` after `fail_after` of them)."""

    def __init__(self, who: str, error: Exception | None = None, chunks=("a ", "b"), fail_after=0):
        self.who, self.error, self.chunks, self.fail_after, self.calls = who, error, chunks, fail_after, 0

    async def complete_json(self, system, user, schema):
        self.calls += 1
        if self.error:
            raise self.error
        return schema(who=self.who)

    async def stream_text(self, system, user):
        self.calls += 1
        for i, chunk in enumerate(self.chunks):
            if self.error and i == self.fail_after:
                raise self.error
            yield chunk
        if self.error and self.fail_after >= len(self.chunks):
            raise self.error


async def collect(llm) -> str:
    return "".join([c async for c in llm.stream_text("s", "u")])


async def test_the_main_provider_is_used_when_it_works():
    main, spare = Llm("main"), Llm("spare")
    assert (await FallbackLLM(main, spare).complete_json("s", "u", Out)).who == "main"
    assert spare.calls == 0  # the second provider's quota is only spent when needed


@pytest.mark.parametrize("error", [LLMBusyError(30), LLMError("bad json")])
async def test_the_second_provider_answers_when_the_main_one_fails(error):
    assert (await FallbackLLM(Llm("main", error), Llm("spare")).complete_json("s", "u", Out)).who == "spare"


async def test_if_both_fail_the_second_error_is_raised():
    with pytest.raises(LLMBusyError) as e:
        await FallbackLLM(Llm("m", LLMError("x")), Llm("s", LLMBusyError(9))).complete_json("s", "u", Out)
    assert e.value.retry_after_s == 9  # lets PatientLLM / the worker wait on the provider that is actually busy


async def test_streaming_falls_back_only_before_anything_was_said():
    assert await collect(FallbackLLM(Llm("m", LLMBusyError(5), fail_after=0), Llm("s", chunks=("x", "y")))) == "xy"
    # Failed after "a ": the candidate already heard it, so a second answer would be spoken on top. Raise instead.
    with pytest.raises(LLMError):
        await collect(FallbackLLM(Llm("m", LLMError("cut"), fail_after=1), Llm("s")))


class Stt:
    def __init__(self, text: str, error: Exception | None = None):
        self.text, self.error = text, error

    async def transcribe(self, wav, prompt=None):
        if self.error:
            raise self.error
        return Transcript(text=self.text, segments=[], stt_ms=1)


@pytest.mark.parametrize("error", [STTBusyError("limit"), STTError("down")])
async def test_speech_falls_back_too(error):
    assert (await FallbackSTT(Stt("m", error), Stt("spare")).transcribe(b"")).text == "spare"
    assert (await FallbackSTT(Stt("m"), Stt("spare")).transcribe(b"")).text == "m"


class FakeOpenAI:
    """Just enough of the OpenAI SDK's chat.completions.create."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.chat = type("Chat", (), {"completions": self})()

    async def create(self, **kwargs):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        message = type("M", (), {"content": self.outcome})()
        return type("R", (), {"choices": [type("C", (), {"message": message})()]})()


def openai_rate_limit(retry_after: str) -> openai.RateLimitError:
    response = httpx.Response(429, headers={"retry-after": retry_after}, request=httpx.Request("POST", "http://x"))
    return openai.RateLimitError("slow down", response=response, body=None)


async def test_openai_style_rate_limits_become_the_same_busy_error():
    client = OpenAICompatClient(FakeOpenAI(openai_rate_limit("7")), "model")
    with pytest.raises(LLMBusyError) as e:
        await client.complete_json("s", "u", Out)
    assert e.value.retry_after_s == 7


async def test_openai_style_answers_are_parsed_like_groq_ones():
    client = OpenAICompatClient(FakeOpenAI('{"who": "cerebras"}'), "model")
    assert (await client.complete_json("s", "u", Out)).who == "cerebras"
