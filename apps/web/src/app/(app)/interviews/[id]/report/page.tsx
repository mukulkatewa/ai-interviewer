import type { Metadata } from "next";

import { ButtonLink } from "@/components/button-link";
import { TrackOnMount } from "@/components/analytics";
import { ScoreRing } from "@/components/score-ring";
import type { Schemas } from "@/lib/api/client";
import { getServerApi, unwrap } from "@/lib/api/server";
import { cn } from "@/lib/utils";
import { ReportFailed, ReportPending } from "./report-status";

export const metadata: Metadata = { title: "Interview report" };

const COMPETENCY_LABELS: Record<Schemas["CompetencyScore"]["competency"], string> = {
  technical_depth: "Technical depth",
  problem_solving: "Problem solving",
  communication: "Communication",
  role_fit: "Role fit",
  behavioral: "Behavioral (STAR)",
};

function Competency({ c }: { c: Schemas["CompetencyScore"] }) {
  return (
    <li className="rounded-2xl border p-4">
      <div className="flex items-baseline justify-between gap-4">
        <p className="font-medium">{COMPETENCY_LABELS[c.competency]}</p>
        <p className="font-mono text-sm tabular-nums text-muted-foreground">{c.score == null ? "n/a" : `${c.score}/5`}</p>
      </div>
      {c.score != null && (
        <div className="mt-2 flex gap-1" aria-hidden>
          {[1, 2, 3, 4, 5].map((n) => (
            <span key={n} className={cn("h-1.5 flex-1 rounded-full", n <= c.score! ? "bg-primary" : "bg-muted")} />
          ))}
        </div>
      )}
      <p className="mt-3 text-sm text-pretty">{c.rationale}</p>
      {c.evidence.map((quote) => (
        // Every quote was checked against the transcript by the server (D14).
        <blockquote key={quote} className="mt-2 border-l-2 pl-3 text-sm italic text-muted-foreground">
          &ldquo;{quote}&rdquo;
        </blockquote>
      ))}
    </li>
  );
}

const LEVEL: Record<NonNullable<Schemas["Report"]["level"]>, { label: string; className: string }> = {
  strong: { label: "Strong", className: "bg-emerald-600/10 text-emerald-700 border-emerald-600/25" },
  solid: { label: "Solid", className: "bg-sky-600/10 text-sky-700 border-sky-600/25" },
  developing: { label: "Developing", className: "bg-amber-500/10 text-amber-700 border-amber-600/25" },
  needs_work: { label: "Needs work", className: "bg-rose-600/10 text-rose-700 border-rose-600/25" },
};

function QuestionScore({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  return (
    <span className="shrink-0 rounded-full border bg-muted px-2.5 py-0.5 font-mono text-xs tabular-nums">{score}/5</span>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default async function InterviewReportPage({ params }: PageProps<"/interviews/[id]/report">) {
  const { id } = await params;
  const api = await getServerApi();
  const path = { params: { path: { interview_id: id } } };
  const [interview, { status, report }] = await Promise.all([
    api.GET("/interviews/{interview_id}", path).then(unwrap),
    api.GET("/interviews/{interview_id}/report", path).then(unwrap),
  ]);

  const title = [interview.job_title ?? "General practice interview", interview.company].filter(Boolean).join(" · ");
  const header = (
    <header>
      <h1 className="text-3xl font-bold tracking-tight">Interview report</h1>
      <p className="text-muted-foreground">{title}</p>
    </header>
  );

  if (status === "created" || status === "in_progress") {
    return (
      <div className="space-y-6">
        {header}
        <div className="rounded-2xl border p-8 text-center">
          <p className="font-medium">This interview isn&apos;t finished yet.</p>
          <ButtonLink className="mt-4" href={`/interviews/${id}`}>
            Continue interview
          </ButtonLink>
        </div>
      </div>
    );
  }
  if (status === "evaluating" || !report) {
    return (
      <div className="space-y-6">
        {header}
        {status === "failed" ? <ReportFailed interviewId={id} /> : <ReportPending />}
      </div>
    );
  }

  const m = report.metrics;
  return (
    <div className="space-y-10">
      <TrackOnMount event="report_viewed" />
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <ScoreRing score={report.overall_score} label="overall" />
        <div className="min-w-0">
          {header}
          {report.level && (
            <span className={cn("mt-3 inline-block rounded-full border px-3 py-0.5 text-sm font-medium", LEVEL[report.level].className)}>
              {LEVEL[report.level].label}
            </span>
          )}
          <p className="mt-3 max-w-2xl text-pretty">{report.summary}</p>
        </div>
      </div>

      {!report.insufficient && (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground">Competencies</h2>
            <ul className="grid gap-3 md:grid-cols-2">
              {report.competencies.map((c) => (
                <Competency key={c.competency} c={c} />
              ))}
            </ul>
          </section>

          <div className="grid gap-8 md:grid-cols-2">
            {report.strengths.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-sm font-semibold text-muted-foreground">What went well</h2>
                <ul className="list-disc space-y-1.5 pl-5">
                  {report.strengths.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </section>
            )}
            {report.improvements.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-sm font-semibold text-muted-foreground">What to improve</h2>
                <ul className="space-y-3">
                  {report.improvements.map((i) => (
                    <li key={i.area}>
                      <p className="font-medium">{i.area}</p>
                      <p className="text-sm text-muted-foreground">{i.advice}</p>
                      {i.practice && (
                        <p className="mt-1 text-sm">
                          <span className="font-medium">Try this: </span>
                          {i.practice}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          {report.questions.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground">Question by question</h2>
              <ol className="space-y-3">
                {report.questions.map((q, i) => (
                  <li key={i} className="rounded-2xl border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-medium text-pretty">{q.question}</p>
                      <QuestionScore score={q.score} />
                    </div>
                    {q.quote && (
                      <blockquote className="mt-2 border-l-2 pl-3 text-sm italic text-muted-foreground">
                        You said: &ldquo;{q.quote}&rdquo;
                      </blockquote>
                    )}
                    <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                      <div>
                        <dt className="text-xs font-medium text-emerald-700 dark:text-emerald-300">Went well</dt>
                        <dd className="mt-1">{q.went_well}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-amber-700 dark:text-amber-300">Missing</dt>
                        <dd className="mt-1">{q.missing}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-primary">A stronger answer</dt>
                        <dd className="mt-1">{q.stronger_answer}</dd>
                      </div>
                    </dl>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">How you spoke</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="Pace" value={m.words_per_minute ? `${m.words_per_minute} wpm` : "n/a"} hint="Conversational: ~120–160" />
          <Metric label="Average answer" value={m.avg_answer_seconds ? `${m.avg_answer_seconds} s` : "n/a"} />
          <Metric label="Very short answers" value={`${m.short_answers} of ${m.answers}`} hint="Under 15 words" />
          <Metric
            label="Filler phrases"
            value={`${m.filler_per_100_words} / 100 words`}
            hint={m.top_fillers.length ? m.top_fillers.map((f) => `"${f}"`).join(", ") : undefined}
          />
        </div>
      </section>
    </div>
  );
}
