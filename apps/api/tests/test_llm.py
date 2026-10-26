"""GroqClient retry logic, tested against a stubbed SDK (no network)."""

from types import SimpleNamespace

import pytest

from app.llm import GroqClient, LLMError
from app.resume.schema import ResumeProfile


def stub_groq(client: GroqClient, replies: list[str]) -> list[list[dict]]:
    """Make the SDK return `replies` in order; return the captured message lists."""
    seen: list[list[dict]] = []

    async def create(*, messages, **_):
        seen.append(list(messages))
        content = replies[len(seen) - 1]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return seen


async def test_valid_json_returns_model():
    client = GroqClient("key", "model")
    stub_groq(client, ['{"name": "Asha", "skills": ["Python"]}'])

    profile = await client.complete_json("sys", "user", ResumeProfile)

    assert profile.name == "Asha"


async def test_invalid_json_retries_with_error_feedback():
    client = GroqClient("key", "model")
    seen = stub_groq(client, ['{"skills": "not-a-list"}', '{"skills": ["Python"]}'])

    profile = await client.complete_json("sys", "user", ResumeProfile)

    assert profile.skills == ["Python"]
    assert "Invalid JSON" in seen[1][-1]["content"]


async def test_gives_up_after_max_attempts():
    client = GroqClient("key", "model", max_attempts=2)
    stub_groq(client, ['{"skills": 1}', '{"skills": 2}'])

    with pytest.raises(LLMError):
        await client.complete_json("sys", "user", ResumeProfile)
