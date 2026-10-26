"""GroqClient behavior against a stubbed SDK (no network)."""

from types import SimpleNamespace

import groq
import httpx
import pytest

from app.llm import GroqClient, LLMBusyError, LLMError
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
