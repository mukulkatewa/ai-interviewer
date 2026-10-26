"""Whisper vocabulary prompt for one interview (projectprep.md, D24)."""

from app.jd.schema import JobProfile
from app.resume.schema import ResumeProfile

# Whisper reads at most 224 prompt tokens; ~30 short terms stays well under that.
MAX_TERMS = 30


def vocabulary_prompt(resume: ResumeProfile, job: JobProfile) -> str | None:
    """Terms this candidate is likely to say, written as natural speech.

    Must be a sentence, not a list: Whisper treats the prompt as the transcript
    so far and copies its style. A bare list ("Terms: PostgreSQL, ...") made it
    write "POSGR SQL" in our benchmark (D24).
    """
    candidates = [
        *(r.skill for r in job.must_have),
        *(alt for r in job.must_have for alt in r.alternatives),
        *resume.skills,
        *(t for e in resume.experience for t in e.technologies),
        *(p.name for p in resume.projects),
        *(r.skill for r in job.nice_to_have),
        *(e.company for e in resume.experience),
        job.company or "",
    ]
    terms: list[str] = []
    seen: set[str] = set()
    for term in (t.strip() for t in candidates):
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            terms.append(term)
    terms = terms[:MAX_TERMS]  # must-haves come first, so they survive the cut

    if not terms:
        return None
    listed = terms[0] if len(terms) == 1 else f"{', '.join(terms[:-1])} and {terms[-1]}"
    return f"In this interview we talked about {listed}."
