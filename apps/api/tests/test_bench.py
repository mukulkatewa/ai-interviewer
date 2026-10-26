"""The benchmark's accuracy numbers are only as good as its WER function."""

import pytest

from bench.speech import pcm_seconds, wer


@pytest.mark.parametrize(
    ("hypothesis", "expected"),
    [
        ("the cat sat", 0),
        ("the cat", 1 / 3),  # deletion
        ("the bat sat", 1 / 3),  # substitution
        ("the cat sat down", 1 / 3),  # insertion
        ("The CAT, sat!", 0),  # case and punctuation don't count
    ],
)
def test_wer(hypothesis, expected):
    assert wer("the cat sat", hypothesis) == pytest.approx(expected)


def test_pcm_seconds_for_24khz_16bit_mono():
    assert pcm_seconds(b"\x00" * 48_000) == 1.0
