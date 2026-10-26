"""Speech pipeline benchmark (projectprep.md, 5.8).

Measures each step of one voice turn on real services:
  TTS  Kokoro-FastAPI (local Docker)   time to first audio byte, total, RTF
  STT  Groq Whisper                    latency per answer length, word error rate
  LLM  Groq (streaming)                time to first token and first full sentence

Usage (from apps/api, with Kokoro running):
  docker compose -f ../../infra/docker-compose.yml --profile speech up -d kokoro
  uv run python -m bench.speech --out ../../docs/benchmarks/speech.md

Small run counts on purpose: Whisper's free tier allows 20 requests/minute.
"""

import argparse
import asyncio
import io
import re
import statistics
import time
import wave
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import groq
import httpx

from app.config import get_settings

KOKORO_URL = "http://localhost:8880"
VOICE = "af_heart"
KOKORO_SAMPLE_RATE = 24_000  # Kokoro's PCM output: 24 kHz, 16-bit, mono
STT_MODEL = "whisper-large-v3-turbo"
LLM_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
VAD_SILENCE_S = 0.6  # how long the browser waits in silence before "user stopped talking"

# What the interviewer says: a short first sentence is what the user hears first (D8).
TTS_SENTENCES = {
    "ack (2 words)": "Got it.",
    "short (8 words)": "Thanks, that makes sense. Let's go deeper.",
    "question (22 words)": (
        "You mentioned reducing API response time by thirty percent. "
        "Walk me through how you found the bottleneck and measured the improvement."
    ),
    "long (45 words)": (
        "That's a good start. In a real payment system, reconciliation jobs often run against millions of rows, "
        "so I'd like to understand how your approach would change at that scale, what you would index, "
        "and how you would make the job safe to retry if it fails halfway through."
    ),
}

# What a candidate says, at increasing lengths. Kokoro speaks them; Whisper transcribes.
ANSWERS = {
    "~5 s": "I used PostgreSQL with a composite index on user id and created at.",
    "~15 s": (
        "At Flipkart I built an internal dashboard in React. The slow part was an API that scanned the "
        "whole orders collection, so I added two MongoDB indexes and the response time dropped by about thirty percent."
    ),
    "~30 s": (
        "My DevChat project is a real time chat application. The frontend is React and the backend is Node with "
        "Socket.io. To scale beyond one server, I used Redis publish and subscribe so that a message sent to one "
        "instance reaches users connected to another instance. The hardest bug was duplicate messages after a "
        "reconnect, which I fixed by giving every message an idempotency key and ignoring repeats on the client."
    ),
    "~60 s": (
        "Let me describe a conflict I handled during my internship. Our team disagreed about whether to rewrite the "
        "reporting service or fix it incrementally. The senior engineer wanted a full rewrite in a new framework, and "
        "I thought that was risky two weeks before a sales event. Instead of arguing in the meeting, I spent an "
        "afternoon measuring where the time actually went. It turned out that ninety percent of the latency came from "
        "two unindexed queries. I wrote a short document with the numbers and proposed fixing those queries first, "
        "with the rewrite as a follow up project. The team agreed, the fix shipped in two days, and the service "
        "handled the sales event without problems. What I learned is that data ends disagreements faster than opinions, "
        "and that proposing a path forward works better than just pointing out risks."
    ),
}

# Whisper's `prompt` biases it toward expected words. In the app this comes from
# the resume + JD skills (D24); here it lists the terms used in ANSWERS.
# Whisper treats the prompt as the transcript so far and copies its style: a bare
# term list made it write "POSGR SQL", while this natural sentence fixed both
# "Redis" and "idempotency" without hurting anything else (measured, see D24).
VOCAB_PROMPT = (
    "In this interview we talked about PostgreSQL, MongoDB, React, Node.js, Socket.io, "
    "Redis pub/sub, idempotency keys, DevChat and Flipkart."
)

LLM_SYSTEM = (
    "You are a friendly technical interviewer. Reply in 2-3 short spoken sentences: "
    "acknowledge the answer, then ask one follow-up question. No markdown."
)
SENTENCE_END = re.compile(r"[.!?](\s|$)")


@dataclass
class Samples:
    values: list[float] = field(default_factory=list)

    @property
    def median(self) -> float:
        return statistics.median(self.values)

    @property
    def worst(self) -> float:
        return max(self.values)

    def ms(self) -> str:
        return f"{self.median * 1000:.0f} ms (worst {self.worst * 1000:.0f})"


# --- TTS ------------------------------------------------------------------------


async def synthesize(http: httpx.AsyncClient, text: str) -> tuple[float, float, bytes]:
    """Stream raw PCM from Kokoro. Returns (time to first byte, total time, audio)."""
    body = {"model": "kokoro", "input": text, "voice": VOICE, "response_format": "pcm", "stream": True}
    start = time.perf_counter()
    first: float | None = None
    audio = bytearray()
    async with http.stream("POST", f"{KOKORO_URL}/v1/audio/speech", json=body) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes():
            if first is None and chunk:
                first = time.perf_counter() - start
            audio += chunk
    return first or 0.0, time.perf_counter() - start, bytes(audio)


def pcm_seconds(pcm: bytes) -> float:
    return len(pcm) / (KOKORO_SAMPLE_RATE * 2)  # 2 bytes per 16-bit sample


def to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(KOKORO_SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


async def bench_tts(http: httpx.AsyncClient, runs: int) -> tuple[float, list[str], dict[str, float]]:
    """Returns (cold-start first byte, table rows, median first byte per sentence)."""
    cold, _, _ = await synthesize(http, "Warming up.")  # first call loads the model
    rows, first_byte = [], {}
    for label, text in TTS_SENTENCES.items():
        ttfb, total, rtf = Samples(), Samples(), Samples()
        for _ in range(runs):
            first, elapsed, pcm = await synthesize(http, text)
            ttfb.values.append(first)
            total.values.append(elapsed)
            rtf.values.append(elapsed / pcm_seconds(pcm))
        first_byte[label] = ttfb.median
        rows.append(f"| {label} | {pcm_seconds(pcm):.1f} s | {ttfb.ms()} | {total.ms()} | {rtf.median:.2f} |")
    return cold, rows, first_byte


# --- STT ------------------------------------------------------------------------


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: word-level edit distance / reference length."""
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " ")).split()  # noqa: E731
    ref, hyp = norm(reference), norm(hypothesis)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)


async def transcribe(client: groq.AsyncGroq, wav: bytes, prompt: str | None = None) -> tuple[float, str]:
    extra = {"prompt": prompt} if prompt else {}
    start = time.perf_counter()
    result = await client.audio.transcriptions.create(
        file=("answer.wav", wav), model=STT_MODEL, language="en", temperature=0, **extra
    )
    return time.perf_counter() - start, result.text


async def bench_stt(http: httpx.AsyncClient, client: groq.AsyncGroq, runs: int) -> tuple[list[str], dict[str, float]]:
    rows, medians = [], {}
    for label, text in ANSWERS.items():
        _, _, pcm = await synthesize(http, text)
        wav = to_wav(pcm)
        latency, errors = Samples(), []
        for _ in range(runs):
            elapsed, hypothesis = await transcribe(client, wav)
            latency.values.append(elapsed)
            errors.append(wer(text, hypothesis))
        # One prompted run per answer: enough to see the accuracy effect while
        # staying under Whisper's 20 requests/minute.
        _, prompted = await transcribe(client, wav, VOCAB_PROMPT)
        medians[label] = latency.median
        rows.append(
            f"| {label} ({pcm_seconds(pcm):.0f} s, {len(wav) // 1024} KB) | {latency.ms()} "
            f"| {statistics.mean(errors):.1%} | {wer(text, prompted):.1%} |"
        )
    return rows, medians


# --- LLM ------------------------------------------------------------------------


async def first_sentence(client: groq.AsyncGroq, model: str) -> tuple[float, float]:
    """Stream a reply; return (time to first content token, time to first full sentence)."""
    start = time.perf_counter()
    first_token: float | None = None
    text = ""
    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": LLM_SYSTEM}, {"role": "user", "content": ANSWERS["~15 s"]}],
        stream=True,
        reasoning_effort="low",
        temperature=0.6,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue  # reasoning tokens arrive in a separate field; only spoken text counts
        if first_token is None:
            first_token = time.perf_counter() - start
        text += delta
        if SENTENCE_END.search(text):
            sentence_at = time.perf_counter() - start
            await stream.response.aclose()  # stop paying for tokens we don't need here
            return first_token, sentence_at
    end = time.perf_counter() - start
    return first_token or end, end


async def bench_llm(client: groq.AsyncGroq, runs: int) -> tuple[list[str], dict[str, float]]:
    rows, medians = [], {}
    for model in LLM_MODELS:
        ttft, sentence = Samples(), Samples()
        for _ in range(runs):
            t, s = await first_sentence(client, model)
            ttft.values.append(t)
            sentence.values.append(s)
        medians[model] = sentence.median
        rows.append(f"| {model} | {ttft.ms()} | {sentence.ms()} |")
    return rows, medians


# --- report ---------------------------------------------------------------------


async def main(runs: int, out: Path | None) -> None:
    client = groq.AsyncGroq(api_key=get_settings().groq_api_key, max_retries=0)
    async with httpx.AsyncClient(timeout=120) as http:
        cold, tts_rows, tts_first_byte = await bench_tts(http, runs)
        stt_rows, stt = await bench_stt(http, client, runs)
        llm_rows, llm = await bench_llm(client, runs)

    # The user hears the first sentence first, so its length sets TTS wait (D23).
    turn_lines = []
    for model, sentence_s in llm.items():
        for opener in ("ack (2 words)", "short (8 words)"):
            tts_s = tts_first_byte[opener]
            total = VAD_SILENCE_S + stt["~15 s"] + sentence_s + tts_s
            turn_lines.append(
                f"| {model} | {opener} | {VAD_SILENCE_S:.1f} s | {stt['~15 s']:.2f} s | {sentence_s:.2f} s "
                f"| {tts_s:.2f} s | **{total:.2f} s** |"
            )

    report = "\n".join(
        [
            f"# Speech benchmark — {date.today().isoformat()}",
            "",
            f"Kokoro-FastAPI v0.9.0 (CPU, Docker, 4 CPUs, 4 threads), voice `{VOICE}` · "
            f"Groq `{STT_MODEL}` · {runs} runs per row · host: Intel i5-12450H.",
            "Method: projectprep.md §5.8. Times are median (worst).",
            "",
            "## TTS (Kokoro)",
            "",
            f"Cold start (first request after container start): {cold * 1000:.0f} ms to first byte.",
            "",
            "| Sentence | Audio | First byte | Total | RTF |",
            "|---|---|---|---|---|",
            *tts_rows,
            "",
            "## STT (Groq Whisper)",
            "",
            "| Answer | Latency | WER | WER with vocab prompt |",
            "|---|---|---|---|",
            *stt_rows,
            "",
            "## LLM first sentence (Groq, streaming, reasoning low)",
            "",
            "| Model | First token | First sentence |",
            "|---|---|---|",
            *llm_rows,
            "",
            "## Estimated turn latency (user stops → AI starts speaking)",
            "",
            "| Live model | First sentence | VAD wait | STT (15 s answer) | LLM 1st sentence | TTS 1st audio | Total |",
            "|---|---|---|---|---|---|---|",
            *turn_lines,
            "",
            "Target: under 2.5 s (projectprep.md §9).",
        ]
    )
    print(report)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.runs, args.out))
