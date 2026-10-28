"""Single-call vs LangGraph report engine on one realistic interview (projectprep.md D38).

  uv run python -m bench.report_engines          # 2 rounds each, alternating

Calls the real model, so it pauses between runs to stay under the free-tier tokens-per-minute limit.
Prints wall time and the scores each engine produced, so you can see both speed and agreement.
"""

import argparse
import asyncio
import time

from app.deps import get_analysis_llm
from app.interview.plan import InterviewPlan, PlannedQuestion
from app.interview.repo import Turn
from app.jd.schema import JobProfile, SkillRequirement
from app.report import graph as report_graph
from app.report.evaluate import build_report
from app.report.repo import EvaluationInputs
from app.resume.schema import ResumeProfile

QA = [
    (
        "Tell me about yourself and what draws you to this role.",
        "I'm a final year student at NIT Trichy. I interned at Flipkart where I built an internal dashboard in React and "
        "reduced API response time by thirty percent by adding MongoDB indexes. I want backend work because I like "
        "making systems faster and more reliable.",
    ),
    (
        "You cut API latency by thirty percent at Flipkart. How did you find the bottleneck?",
        "I looked at the slow endpoint, it was slow. Then I added an index and it got faster.",
    ),
    (
        "Walk me through your DevChat project. What was your part?",
        "DevChat is a real-time chat app with Socket.io and Redis pub/sub. I built the whole backend alone. Messages go "
        "through Redis channels so that multiple server instances can broadcast to every connected client. The hard part "
        "was ordering: two users could send at the same millisecond, so I stamped messages with a per-room sequence "
        "number from a Redis counter and the client sorts by it.",
    ),
    (
        "How would you design a rate limiter for a public REST API?",
        "I would use a token bucket per API key stored in Redis. Each request takes a token, and tokens refill at a fixed "
        "rate. I would do it in a Lua script so check and decrement are atomic. For bursts I allow a bucket size above the "
        "refill rate. I would return 429 with a Retry-After header.",
    ),
    (
        "Tell me about a time you disagreed with a teammate.",
        "Yeah we had a disagreement about the database. It was fine in the end, we talked and decided.",
    ),
]


def sample() -> EvaluationInputs:
    turns, answers = [], []
    for i, (question, answer) in enumerate(QA):
        turns.append(Turn(seq=2 * i, role="interviewer", question_index=i, text=question))
        turns.append(Turn(seq=2 * i + 1, role="candidate", question_index=i, text=answer))
        answers.append((answer, len(answer.split()) / 2.4))  # ~144 words a minute
    return EvaluationInputs(
        plan=InterviewPlan(
            questions=[
                PlannedQuestion(phase="resume_deep_dive", question=q, focus="Specific decisions and results")
                for q, _ in QA
            ]
        ),
        resume=ResumeProfile(name="Rahul Sharma", skills=["React", "Node.js", "MongoDB", "Redis", "Docker"]),
        job=JobProfile(
            title="Backend Engineer", must_have=[SkillRequirement(skill="Python"), SkillRequirement(skill="REST")]
        ),
        has_job_description=True,
        turns=turns,
        answers=answers,
    )


async def main(rounds: int, pause_s: int) -> None:
    llm = get_analysis_llm()
    graph = report_graph.build_graph(llm)
    data = sample()
    runs = [("single", lambda: build_report(data, llm)), ("graph", lambda: report_graph.build_report(graph, data))]
    results: dict[str, list[tuple[float, int | None, int]]] = {"single": [], "graph": []}
    for r in range(rounds):
        for name, run in runs:
            started = time.perf_counter()
            report = await run()
            took = time.perf_counter() - started
            results[name].append((took, report.overall_score, len(report.questions)))
            print(
                f"round {r + 1} {name:6} {took:5.1f} s  score={report.overall_score}  questions={len(report.questions)}",
                flush=True,
            )
            await asyncio.sleep(pause_s)  # let the tokens-per-minute window reset
    for name, rows in results.items():
        times = sorted(t for t, _, _ in rows)
        print(f"{name:6} median {times[len(times) // 2]:.1f} s over {len(rows)} runs; scores {[s for _, s, _ in rows]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--pause", type=int, default=65)
    args = parser.parse_args()
    asyncio.run(main(args.rounds, args.pause))
