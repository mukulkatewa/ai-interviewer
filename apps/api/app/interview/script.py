"""Fixed lines the interviewer says. No LLM needed for these (projectprep.md, 5.9, 5.11)."""

from app.interview.repo import Interview

MAX_NAME_CHARS = 40  # the name comes from a parsed resume: keep it sane before speaking it

WRAP_UP = (
    "That's all the questions I have. Before we finish, "
    "is there anything you'd like to ask me, or anything you want to add?"
)


def _first_name(interview: Interview) -> str:
    return (interview.candidate_name or "").split(" ")[0][:MAX_NAME_CHARS]


def intro(interview: Interview) -> str:
    # The first sentence is deliberately 2 words: Kokoro's first audio grows
    # ~170 ms per word, so "Hi Rahul!" starts playing in ~0.6 s (D23).
    name = _first_name(interview)
    greeting = f"Hi {name}!" if name else "Hi there!"
    role = f"the {interview.job_title} role" if interview.job_title else "this role"
    company = f" at {interview.company}" if interview.company else ""
    return (
        f"{greeting} I'm your interviewer today for {role}{company}. "
        "This will take about fifteen minutes, so answer in your own words, the way you would in a real interview. "
        "Let's start with an easy one. Tell me about yourself, and what draws you to this role?"
    )


def closing(interview: Interview) -> str:
    name = _first_name(interview)
    return (
        f"That's the end of our interview{', ' + name if name else ''}. Thank you! "
        "Your feedback report will be ready in about a minute."
    )


def ended_early(interview: Interview) -> str:
    return f"No problem, let's stop here. {closing(interview)}"


def welcome_back(last_question: str) -> str:
    return f"Welcome back. Let's pick up where we left off. {last_question}"
