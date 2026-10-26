"""Validate a candidate's answer before spending STT quota on it."""

import io
import wave

SAMPLE_RATE = 16_000  # what the browser sends and what Whisper uses internally
MIN_SECONDS = 0.3
MAX_SECONDS = 125.0  # 2-minute answer cap (D12) plus slack for the trailing silence


class BadAudio(ValueError):
    """Not 16 kHz mono 16-bit PCM WAV, or too short."""


class AnswerTooLong(ValueError):
    pass


def max_answer_bytes() -> int:
    """Largest valid upload: lets the socket reject oversize frames without parsing them."""
    return int(MAX_SECONDS * SAMPLE_RATE * 2) + 44  # 2 bytes/sample + WAV header


def wav_duration(data: bytes) -> float:
    """Seconds of audio in `data`. Raises if the format isn't exactly what we expect."""
    if len(data) > max_answer_bytes():
        raise AnswerTooLong
    try:
        with wave.open(io.BytesIO(data)) as w:
            fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            frames = w.getnframes()
    except (wave.Error, EOFError) as e:
        raise BadAudio("Not a WAV file") from e
    if fmt != (1, 2, SAMPLE_RATE):
        raise BadAudio(f"Expected 16 kHz mono 16-bit WAV, got channels/width/rate={fmt}")
    seconds = frames / SAMPLE_RATE
    if seconds < MIN_SECONDS:
        raise BadAudio("Answer too short")
    if seconds > MAX_SECONDS:
        raise AnswerTooLong
    return seconds
