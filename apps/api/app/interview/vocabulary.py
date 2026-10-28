"""Whisper vocabulary prompt for one interview (projectprep.md, D24)."""

from app.jd.schema import JobProfile
from app.resume.schema import ResumeProfile

# Whisper reads at most 224 prompt tokens; ~30 short terms stays well under that.
MAX_TERMS = 30


def vocabulary_prompt(resume: ResumeProfile, job: JobProfile) -> str | None:
    """The candidate's name, school and the terms they are likely to say, written as natural speech.

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

    who = _who(resume)
    if not terms:
        return who or None
    listed = terms[0] if len(terms) == 1 else f"{', '.join(terms[:-1])} and {terms[-1]}"
    return f"{who + ' ' if who else ''}In this interview we talked about {listed}."


def _who(resume: ResumeProfile) -> str:
    """The candidate's name and school, as a sentence. Names are what Whisper gets wrong most (a Hindi
    name came out as "Bilh Ghatayav"), and it spells them correctly when the prompt has seen them."""
    schools = [e.institution.strip() for e in resume.education if e.institution.strip()][:2]
    name = (resume.name or "").strip()
    if name and schools:
        return f"This is an interview with {name}, who studied at {' and '.join(schools)}."
    if name:
        return f"This is an interview with {name}."
    if schools:
        return f"The candidate studied at {' and '.join(schools)}."
    return ""
