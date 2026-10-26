"""Resume <-> JD matching and scoring. Pure code, no AI (projectprep.md, D6)."""

from app.analysis.schema import Coverage, MatchResult, RequirementMatch
from app.analysis.skills import keys_in_text, skill_key
from app.jd.schema import JobProfile, SkillRequirement
from app.resume.schema import ResumeProfile

MUST_HAVE_WEIGHT = 0.8
NICE_TO_HAVE_WEIGHT = 0.2


class ResumeSkillIndex:
    """Resume skills in two lookup tables, built once per analysis."""

    def __init__(self, resume: ResumeProfile):
        listed = [
            *resume.skills,
            *(t for e in resume.experience for t in e.technologies),
            *(t for p in resume.projects for t in p.technologies),
        ]
        # key -> first spelling seen, so we can echo the candidate's own wording.
        self.listed: dict[str, str] = {}
        for name in listed:
            self.listed.setdefault(skill_key(name), name)

        self.mentioned = keys_in_text(
            [
                resume.headline or "",
                *(e.role for e in resume.experience),
                *(h for e in resume.experience for h in e.highlights),
                *(f"{p.name} {p.description}" for p in resume.projects),
            ]
        )

    def match(self, req: SkillRequirement) -> RequirementMatch:
        keys = [skill_key(s) for s in (req.skill, *req.alternatives)]
        # Prefer "listed" over "mentioned" across all alternatives.
        for key in keys:
            if key in self.listed:
                return RequirementMatch(requirement=req, status="listed", matched_as=self.listed[key])
        if any(key in self.mentioned for key in keys):
            return RequirementMatch(requirement=req, status="mentioned")
        return RequirementMatch(requirement=req, status="missing")


def _coverage(index: ResumeSkillIndex, reqs: list[SkillRequirement]) -> Coverage:
    matches = [index.match(r) for r in reqs]
    met = sum(m.status != "missing" for m in matches)
    return Coverage(matches=matches, ratio=met / len(matches) if matches else None)


def _score(must: float | None, nice: float | None) -> int | None:
    # Weight only the parts the JD actually has, so a JD with no "nice to have"
    # section isn't capped at 80.
    parts = [(r, w) for r, w in ((must, MUST_HAVE_WEIGHT), (nice, NICE_TO_HAVE_WEIGHT)) if r is not None]
    if not parts:
        return None
    return round(100 * sum(r * w for r, w in parts) / sum(w for _, w in parts))


def match_resume(resume: ResumeProfile, job: JobProfile) -> MatchResult:
    index = ResumeSkillIndex(resume)
    must = _coverage(index, job.must_have)
    nice = _coverage(index, job.nice_to_have)
    return MatchResult(must_have=must, nice_to_have=nice, score=_score(must.ratio, nice.ratio))
