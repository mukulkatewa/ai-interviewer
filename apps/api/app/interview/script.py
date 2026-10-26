"""Fixed lines the interviewer says. No LLM needed for these (projectprep.md, 5.9)."""

from app.interview.repo import Interview

MAX_NAME_CHARS = 40  # the name comes from a parsed resume: keep it sane before speaking it


def intro(interview: Interview) -> str:
    # The first sentence is deliberately 2 words: Kokoro's first audio grows
    # ~170 ms per word, so "Hi Rahul!" starts playing in ~0.6 s (D23).
    first_name = (interview.candidate_name or "").split(" ")[0][:MAX_NAME_CHARS]
    greeting = f"Hi {first_name}!" if first_name else "Hi there!"
    role = f"the {interview.job_title} role" if interview.job_title else "this role"
    company = f" at {interview.company}" if interview.company else ""
    return (
        f"{greeting} I'm your interviewer today for {role}{company}. "
        "This will take about fifteen minutes, so answer in your own words, the way you would in a real interview. "
        "Let's start with an easy one. Tell me about yourself, and what draws you to this role?"
    )
