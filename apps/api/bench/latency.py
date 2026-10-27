"""Real per-turn latency from saved interviews (projectprep.md 5.13, section 9).

  uv run python -m bench.latency            # all interviews in DATABASE_URL
  uv run python -m bench.latency --days 7   # last week only

Prints p50/p95 of what each turn waited on: STT, the model's first sentence,
and TTS of that sentence. These are the numbers for the resume.
"""

import argparse
import asyncio

import asyncpg

from app.config import get_settings

QUERY = """
    select
        count(*) filter (where role = 'candidate') as answers,
        count(distinct interview_id) as interviews,
        percentile_cont(0.5) within group (order by stt_ms) as stt_p50,
        percentile_cont(0.95) within group (order by stt_ms) as stt_p95,
        percentile_cont(0.5) within group (order by llm_ms) as llm_p50,
        percentile_cont(0.95) within group (order by llm_ms) as llm_p95,
        percentile_cont(0.5) within group (order by tts_ms) as tts_p50,
        percentile_cont(0.95) within group (order by tts_ms) as tts_p95
    from interview_turns
    where created_at > now() - make_interval(days => $1)
"""


async def main(days: int) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        r = await conn.fetchrow(QUERY, days)
    finally:
        await conn.close()

    def ms(value: float | None) -> str:
        return f"{value:.0f} ms" if value is not None else "n/a"

    print(f"{r['interviews']} interviews, {r['answers']} answers (last {days} days)\n")
    print("| Step | p50 | p95 |\n|---|---|---|")
    print(f"| STT (Groq Whisper) | {ms(r['stt_p50'])} | {ms(r['stt_p95'])} |")
    print(f"| LLM first sentence | {ms(r['llm_p50'])} | {ms(r['llm_p95'])} |")
    print(f"| TTS first sentence | {ms(r['tts_p50'])} | {ms(r['tts_p95'])} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=3650)
    asyncio.run(main(parser.parse_args().days))
