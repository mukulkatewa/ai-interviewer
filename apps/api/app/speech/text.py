"""Text helpers for speech: we synthesize and send one sentence at a time (D8, D23)."""

import re

# A sentence ends at . ! or ? followed by whitespace and then something that can
# start a sentence. Requiring the capital/digit/quote keeps "Node.js" and
# "3.5 s" whole; that matters because a bad split is audible as an odd pause.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

# A period after these doesn't end a sentence, even before a capital ("e.g. Redis").
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "Mr.", "Mrs.", "Ms.", "Dr.")


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for part in _BOUNDARY.split(text.strip()):
        part = part.strip()
        if not part:
            continue
        # Re-join pieces wrongly cut after an abbreviation. (Python lookbehinds
        # must be fixed width, so this can't live in the regex.)
        if sentences and sentences[-1].endswith(_ABBREVIATIONS):
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return sentences
