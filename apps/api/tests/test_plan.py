from app.interview.plan import FALLBACKS, PHASES, InterviewPlan, PlannedQuestion, normalize


def q(phase: str, n: int) -> PlannedQuestion:
    return PlannedQuestion(phase=phase, question=f"{phase} question {n}?", focus="f")


def test_normalize_orders_phases_and_caps_counts():
    messy = InterviewPlan(
        questions=[q("behavioral", i) for i in range(5)]
        + [q("role_skills", i) for i in range(4)]
        + [q("resume_deep_dive", i) for i in range(4)]
    )

    plan = normalize(messy)

    assert [x.phase for x in plan.questions] == ["resume_deep_dive"] * 3 + ["role_skills"] * 3 + ["behavioral"] * 2
    assert sum(PHASES.values()) == len(plan.questions)


def test_normalize_fills_missing_phases_with_fallbacks():
    plan = normalize(
        InterviewPlan(questions=[q("role_skills", 0), PlannedQuestion(phase="behavioral", question="  ", focus="f")])
    )

    assert plan.questions == [FALLBACKS["resume_deep_dive"], q("role_skills", 0), FALLBACKS["behavioral"]]
