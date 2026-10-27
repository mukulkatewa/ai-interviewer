"""Speaking metrics computed by code: facts, not opinions (projectprep.md 5.12)."""

import re
from collections import Counter

from app.report.schema import SpeakingMetrics

SHORT_ANSWER_WORDS = 15
# Whisper drops most "um"/"uh", so phrases it keeps matter more. "like" is excluded:
# too often a real word ("I'd like to") to count without context.
_FILLERS = re.compile(r"\b(um+|uh+|erm|basically|actually|literally|you know|kind of|sort of|i mean)\b", re.IGNORECASE)


def speaking_metrics(answers: list[tuple[str, float | None]]) -> SpeakingMetrics:
    """`answers`: (transcript, seconds of speech) per candidate answer."""
    words = [len(text.split()) for text, _ in answers]
    total_words = sum(words)
    timed = [(w, s) for w, (_, s) in zip(words, answers, strict=True) if s]
    total_seconds = sum(s for _, s in timed)
    fillers = Counter(m.group(0).lower() for text, _ in answers for m in _FILLERS.finditer(text))

    return SpeakingMetrics(
        answers=len(answers),
        words_per_minute=round(sum(w for w, _ in timed) / (total_seconds / 60)) if total_seconds else None,
        avg_answer_seconds=round(total_seconds / len(timed), 1) if timed else None,
        short_answers=sum(w < SHORT_ANSWER_WORDS for w in words),
        filler_per_100_words=round(100 * sum(fillers.values()) / total_words, 1) if total_words else 0.0,
        top_fillers=[phrase for phrase, _ in fillers.most_common(3)],
    )
