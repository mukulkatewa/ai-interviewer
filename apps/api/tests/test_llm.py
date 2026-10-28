"""GroqClient behavior against a stubbed SDK (no network)."""

from types import SimpleNamespace

import groq
import httpx
import pytest
from pydantic import BaseModel

from app.llm import GroqClient, LLMBusyError, LLMError, PatientLLM
from app.resume.schema import ResumeProfile


class FakeGroq:
    """Mimics AsyncGroq.chat.completions.create: returns `replies` in order
    (raising any that are exceptions) and records every call's kwargs."""

    def __init__(self, replies: list[str | Exception]):
        self.replies = replies
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        reply = self.replies[len(self.calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


def rate_limited(headers: dict[str, str]) -> groq.RateLimitError:
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://api.groq.com"))
    return groq.RateLimitError("rate limited", response=response, body=None)


async def test_valid_json_returns_model():
    client = GroqClient(FakeGroq(['{"name": "Asha", "skills": ["Python"]}']), "model")

    profile = await client.complete_json("sys", "user", ResumeProfile)

    assert profile.name == "Asha"


async def test_invalid_json_retries_with_error_feedback():
    fake = FakeGroq(['{"skills": "not-a-list"}', '{"skills": ["Python"]}'])

    profile = await GroqClient(fake, "model").complete_json("sys", "user", ResumeProfile)

    assert profile.skills == ["Python"]
    assert "Invalid JSON" in fake.calls[1]["messages"][-1]["content"]


async def test_gives_up_after_max_attempts():
    client = GroqClient(FakeGroq(['{"skills": 1}', '{"skills": 2}']), "model", max_attempts=2)

    with pytest.raises(LLMError):
        await client.complete_json("sys", "user", ResumeProfile)


async def test_reasoning_effort_only_sent_when_set():
    fake = FakeGroq(["{}", "{}"])

    await GroqClient(fake, "model", reasoning_effort="low").complete_json("sys", "user", ResumeProfile)
    await GroqClient(fake, "model").complete_json("sys", "user", ResumeProfile)

    assert fake.calls[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in fake.calls[1]


@pytest.mark.parametrize(("headers", "expected"), [({"retry-after": "6.1"}, 6), ({}, 30)])
async def test_rate_limit_becomes_busy_error_with_retry_after(headers, expected):
    client = GroqClient(FakeGroq([rate_limited(headers)]), "model")

    with pytest.raises(LLMBusyError) as exc:
        await client.complete_json("sys", "user", ResumeProfile)

    assert exc.value.retry_after_s == expected


# --- PatientLLM: wait out a short rate limit (D41) -----------------------------------------


class _BusyThenOk:
    def __init__(self, waits: list[int]):
        self.waits, self.calls = list(waits), 0

    async def complete_json(self, system, user, schema):
        self.calls += 1
        if self.waits:
            raise LLMBusyError(self.waits.pop(0))
        return schema(name="ok") if "name" in schema.model_fields else schema()


class _Out(BaseModel):
    name: str = "x"


async def _patient(inner, max_wait_s):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    llm = PatientLLM(inner, max_wait_s, sleep=fake_sleep)
    return llm, slept


async def test_patient_llm_waits_once_and_succeeds():
    inner = _BusyThenOk([7])
    llm, slept = await _patient(inner, 20)
    assert (await llm.complete_json("s", "u", _Out)).name == "ok"
    assert (inner.calls, slept) == (2, [7])


async def test_patient_llm_gives_up_when_the_wait_is_longer_than_it_will_hold_a_request():
    inner = _BusyThenOk([45])
    llm, slept = await _patient(inner, 20)
    with pytest.raises(LLMBusyError) as e:
        await llm.complete_json("s", "u", _Out)
    assert e.value.retry_after_s == 45 and (inner.calls, slept) == (1, [])  # no pointless sleep first


async def test_patient_llm_total_wait_is_bounded():
    inner = _BusyThenOk([8, 8, 8])  # 8 + 8 fits in 20, the third would make 24
    llm, slept = await _patient(inner, 20)
    with pytest.raises(LLMBusyError):
        await llm.complete_json("s", "u", _Out)
    assert (inner.calls, slept) == (3, [8, 8])
