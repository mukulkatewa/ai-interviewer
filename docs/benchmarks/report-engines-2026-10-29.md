# Report engines: single call vs LangGraph (2026-10-29)

`uv run python -m bench.report_engines` runs both engines on one fixed 5-question interview with the real
model (`openai/gpt-oss-120b`, Groq free tier), alternating, 65 s apart so the tokens-per-minute window resets.

| Engine | Run 1 | Run 2 | Median | Overall scores | Feedback entries |
|---|---|---|---|---|---|
| single call | 7.0 s | 7.1 s | 7.1 s | 50, 50 | 5, 5 |
| LangGraph | 10.0 s | 13.9 s | 13.9 s | 51, 45 | 5, 4 |

**Reading it honestly** (2 runs each: a direction, not statistics):
- The graph is about 1.4 to 2x slower. The two parallel calls each carry the transcript and each pay the
  model's reasoning time, and the wrap-up is a third call that must wait for them.
- The single call was steadier on this input (same score twice). Splitting the work did not make grading
  more consistent; the 6-point gap came from the model, not from the graph.
- So the graph is **not** an efficiency gain. `REPORT_ENGINE` stays `single` by default (D38).

**What would change this:** a model with cheaper reasoning, a much longer transcript (where one call
gets slow and rate limited), or per-node retries that matter more than latency. The planned grading
evaluation harness would settle consistency with more than two runs.
