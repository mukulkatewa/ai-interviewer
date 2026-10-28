"""How many interviews can one Kokoro handle at once? (projectprep.md D42)

  uv run python -m bench.tts_concurrency            # 1, 2, 3, 4, 6, 8 simultaneous interviews

Each simulated interview asks Kokoro for six interviewer sentences one after another, like a real
reply. Prints the time to get each sentence's audio (p50 / p95) per concurrency level. A sentence
that takes longer than TTS_TIMEOUT_S makes the browser fall back to its own voice (D26), so the p95
is what decides how many rooms a server can honestly offer. Run it ON THE PRODUCTION VM: results
from a laptop say nothing about an Oracle ARM VM.
"""

import argparse
import asyncio
import statistics
import time

import httpx

from app.config import get_settings
from app.speech.tts import KokoroTTS, TTSError

SENTENCES = [
    "Hi Rahul!",
    "Thanks for that, it sounds like you owned the whole backend.",
    "Walk me through how you decided between Redis channels and a message queue for the chat messages.",
    "That makes sense, and the ordering problem you mentioned is a classic one.",
    "How would you design a rate limiter for a public REST API that other teams depend on?",
    "Great, that's all the time we have, and your feedback report will be ready in about a minute.",
]


async def one_interview(tts: KokoroTTS, timings: list[float], failures: list[int]) -> None:
    for sentence in SENTENCES:
        started = time.perf_counter()
        try:
            await tts.synthesize(sentence)
        except TTSError:
            failures.append(1)
            continue
        timings.append(time.perf_counter() - started)


async def level(tts: KokoroTTS, n: int) -> None:
    timings: list[float] = []
    failures: list[int] = []
    wall = time.perf_counter()
    await asyncio.gather(*(one_interview(tts, timings, failures) for _ in range(n)))
    timings.sort()
    p50 = statistics.median(timings) if timings else float("nan")
    p95 = timings[min(len(timings) - 1, int(0.95 * len(timings)))] if timings else float("nan")
    print(
        f"{n:2d} interviews: sentence p50 {p50:5.2f} s   p95 {p95:5.2f} s   failures {len(failures)}   "
        f"(total {time.perf_counter() - wall:4.1f} s)",
        flush=True,
    )


async def main(levels: list[int]) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.tts_timeout_s) as http:
        tts = KokoroTTS(http, settings.kokoro_url, settings.kokoro_voice)
        await tts.synthesize("Warm up.")  # the first request loads the model
        for n in levels:
            await level(tts, n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 6, 8])
    asyncio.run(main(parser.parse_args().levels))
