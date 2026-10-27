"""Does the candidate want to stop the interview? (projectprep.md 5.11, D33)

Plain code, not another model call: instant, free, and every phrase is testable.
Precision matters more than recall. A technical answer must never end an
interview ("we stop the container before deleting the volume"), while a person
who really wants out can always press End interview.
"""

import re

# A short utterance is a command only when it ends right after the command, so a
# technical sentence that merely starts with "stop" ("stop words are removed...") is left alone.
_MAX_COMMAND_WORDS = 9
_FILLER = r"(?:(?:please|okay|ok|um|uh|so|hey|well|sorry)\s+)*"
_TAIL = r"(?:\s+(?:now|here|please|thanks|thank you|right now|for now|for today|today|the interview|this))*"
_COMMANDS = (
    r"stop",
    r"end",
    r"quit",
    r"finish",
    r"enough",
    r"that'?s all",
    r"that is all",
    r"that will be all",
    r"i'?m done",
    r"i am done",
    r"we'?re done",
    r"we are done",
    r"let'?s (?:stop|end|finish|wrap up)",
    r"wrap up",
    r"(?:can|could|may|shall) (?:we|i)(?: please)? (?:stop|end|finish|quit|wrap up)",
    r"i (?:want|wanna|would like|need) to (?:stop|end|quit|finish|leave)",
    r"i (?:need|have|got) to (?:go|leave)",
    r"i give up",
    r"no more questions",
)
_SHORT_COMMAND = re.compile(rf"^{_FILLER}(?:{'|'.join(_COMMANDS)}){_TAIL}$")

# Naming the interview is unambiguous at any length. Only "interview" and
# "conversation" qualify: "session" and "call" are everyday technical words.
_EXPLICIT = re.compile(
    r"\b(?:end|stop|finish|quit|terminate|conclude)\s+(?:the|this|our|my)?\s*(?:interview|conversation)\b"
    r"(?!\s+(?:process|question|loop|stage|round|panel|stages|rounds|questions))"
)


def _normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return " ".join(text.split())


def wants_to_stop(text: str) -> bool:
    words = _normalize(text)
    if not words:
        return False
    if _EXPLICIT.search(words):
        return True
    return len(words.split()) <= _MAX_COMMAND_WORDS and bool(_SHORT_COMMAND.match(words))
