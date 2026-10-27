"""Pure conversation rules (D29) and stream parsing, without sockets."""

import pytest

from app.interview.conversation import _read_action, _sentences, advance, allowed_actions
from app.interview.plan import Position

N = 8  # planned questions


@pytest.mark.parametrize(
    ("question", "followups", "time_up", "expected"),
    [
        (0, 0, False, ("NEXT",)),  # intro: straight to the first planned question
        (1, 0, False, ("FOLLOW_UP", "NEXT")),
        (1, 1, False, ("NEXT",)),  # follow-up budget used
        (5, 0, True, ("NEXT",)),  # out of time: no more probing
        (N, 0, False, ("FOLLOW_UP", "NEXT")),
        (N + 1, 0, False, ("END",)),  # wrap-up answered
    ],
)
def test_allowed_actions(question, followups, time_up, expected):
    assert allowed_actions(Position(question=question, followups=followups), N, time_up) == expected


def test_advance():
    assert advance(Position(question=3), "FOLLOW_UP", N, False) == Position(question=3, followups=1)
    assert advance(Position(question=3, followups=1), "NEXT", N, False) == Position(question=4)
    assert advance(Position(question=3), "NEXT", N, True) == Position(question=N + 1)  # time up: to wrap-up
    assert advance(Position(question=N + 1), "END", N, False) == Position(question=N + 2)


async def chunks(*parts: str):
    for part in parts:
        yield part


async def collect(stream) -> list[str]:
    return [item async for item in stream]


async def test_read_action_split_across_chunks():
    action, rest = await _read_action(chunks("ACT", "ION: FOLL", "OW_UP\nWhat was ", "your role?"))
    assert action == "FOLLOW_UP"
    assert "".join(await collect(rest)) == "What was your role?"


async def test_read_action_on_same_line_keeps_spoken_text():
    # Seen from gpt-oss-20b: no newline after the action.
    action, rest = await _read_action(chunks("ACTION: NEXT So the index", " removed the full scan."))
    assert action == "NEXT"
    assert "".join(await collect(rest)) == "So the index removed the full scan."


async def test_read_action_missing_keeps_all_text():
    action, rest = await _read_action(chunks("Sure, that's a great point about caching. ", "Next."))
    assert action is None
    assert "".join(await collect(rest)) == "Sure, that's a great point about caching. Next."


async def test_sentences_emitted_as_soon_as_complete():
    out = await collect(_sentences(chunks("Nice use of Node.js. You", " scaled it with Redis. And", " then?")))
    assert out == ["Nice use of Node.js.", "You scaled it with Redis.", "And then?"]


async def test_sentences_keep_spaces_at_chunk_boundaries():
    # Real streams split tokens anywhere, including right after a space.
    out = await collect(_sentences(chunks("It dropped from ", "900 to ", "620 ms. Then ", "we shipped it.")))
    assert out == ["It dropped from 900 to 620 ms.", "Then we shipped it."]
