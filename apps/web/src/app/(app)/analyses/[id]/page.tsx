import type { Metadata } from "next";
import Link from "next/link";

import { CopyButton } from "@/components/copy-button";
import { ScoreRing } from "@/components/score-ring";
import { getServerApi, unwrap } from "@/lib/api/server";
import type { Schemas } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { StartInterview } from "./start-interview";

export const metadata: Metadata = { title: "Job match report" };

const STATUS = {
  listed: { label: "On resume", className: "border-emerald-600/30 bg-emerald-600/10 text-emerald-700 dark:text-emerald-300" },
  mentioned: { label: "Add to skills", className: "border-amber-600/30 bg-amber-600/10 text-amber-700 dark:text-amber-300" },
  missing: { label: "Missing", className: "border-rose-600/30 bg-rose-600/10 text-rose-700 dark:text-rose-300" },
} as const;

function Coverage({ title, coverage }: { title: string; coverage: Schemas["Coverage"] }) {
  if (coverage.matches.length === 0) return null;
  const met = coverage.matches.filter((m) => m.status !== "missing").length;

  return (
    <section className="space-y-3">
      <h2 className="flex items-baseline justify-between text-sm font-medium text-muted-foreground">
        {title}
        <span className="font-mono tabular-nums">
          {met}/{coverage.matches.length}
        </span>
      </h2>
      <ul className="flex flex-wrap gap-2">
        {coverage.matches.map((m) => {
          const s = STATUS[m.status];
          const names = [m.requirement.skill, ...m.requirement.alternatives].join(" / ");
          return (
            <li key={names} className={cn("rounded-lg border px-2.5 py-1 text-sm", s.className)}>
              {names}
              <span className="ml-2 text-xs opacity-80">{s.label}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default async function AnalysisPage({ params }: PageProps<"/analyses/[id]">) {
  const { id } = await params;
  const api = await getServerApi();
  const report = unwrap(await api.GET("/analyses/{analysis_id}", { params: { path: { analysis_id: id } } }));
  const { job, match, insights } = report;

  return (
    <div className="space-y-10">
      <header className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <ScoreRing score={match.score} />
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{job.title ?? "Job match report"}</h1>
          <p className="text-muted-foreground">
            {[job.company, job.seniority, formatDate(report.created_at)].filter(Boolean).join(", ")}
          </p>
          <p className="mt-3 max-w-2xl text-pretty">{insights.summary}</p>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <StartInterview analysisId={report.id} />
            <Link href={`/resumes/${report.resume_id}`} className="text-sm text-primary hover:underline">
              View resume
            </Link>
          </div>
        </div>
      </header>

      <div className="grid gap-8 md:grid-cols-2">
        <Coverage title="Must-have skills" coverage={match.must_have} />
        <Coverage title="Nice-to-have skills" coverage={match.nice_to_have} />
      </div>

      {insights.strengths.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Strengths</h2>
          <ul className="list-disc space-y-1.5 pl-5">
            {insights.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      {insights.gaps.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">What to work on</h2>
          <ul className="divide-y rounded-xl border">
            {insights.gaps.map((g) => (
              <li key={g.skill} className="p-4">
                <p className="font-medium">{g.skill}</p>
                <p className="text-sm text-muted-foreground">{g.advice}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {insights.bullet_rewrites.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Stronger resume bullets</h2>
          <p className="text-sm text-muted-foreground">
            Replace any <span className="font-mono">[placeholder]</span> with your real numbers before using these.
          </p>
          <ul className="space-y-3">
            {insights.bullet_rewrites.map((b) => (
              <li key={b.original} className="rounded-xl border p-4">
                <p className="text-sm text-muted-foreground line-through decoration-muted-foreground/40">{b.original}</p>
                <div className="mt-2 flex items-start justify-between gap-3">
                  <p className="font-medium">{b.improved}</p>
                  <CopyButton text={b.improved} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{b.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
