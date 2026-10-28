# Speech capacity: simultaneous interviews on one Kokoro (2026-10-29)

`uv run python -m bench.tts_concurrency`: N simulated interviews each ask Kokoro for six interviewer
sentences in a row (the same kind of requests a real interview makes). Kokoro-FastAPI CPU, limited to 4 CPUs,
run on a 12-core development machine. **Re-run on the production VM before trusting these numbers.**

| Simultaneous interviews | Time to a sentence's audio, p50 | p95 |
|---|---|---|
| 1 | 2.8 s | 3.7 s |
| 2 | 5.3 s | 6.6 s |
| 3 | 6.5 s | 8.5 s |
| 4 | 9.0 s | 12.6 s |
| 6 | 12.4 s | 13.8 s |
| 8 | 14.7 s | 21.4 s |

No request failed, but time per sentence grows almost in direct proportion to the number of interviews: the 4 CPUs
are the whole budget. A real conversation needs the first sentence in a few seconds, so:

- **2 simultaneous interviews** is the honest capacity of this setup (`MAX_LIVE_INTERVIEWS=2`, D42). A third
  user is told the rooms are full and to try in a few minutes.
- The daily limits (D32) spread usage over the day, so 2 at a time still serves well over 100 interviews a day
  if they don't all arrive at once.
- To go beyond: more CPUs for Kokoro, a GPU, or a hosted text-to-speech provider as a second option behind
  `TTSProvider` (D9). Lowering `TTS_TIMEOUT_S` makes slow sentences fall back to the browser's own voice sooner.
