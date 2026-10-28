import type { Metadata } from "next";
import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import { getServerApi, unwrap } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { DeleteMyData } from "./delete-my-data";
import { StartInterviewNow } from "../start-interview-now";
import { UploadResume } from "./upload-resume";

export const metadata: Metadata = { title: "Dashboard" };

const INTERVIEW_STATUS = {
  created: "Not started",
  in_progress: "In progress",
  evaluating: "Report pending",
  completed: "Done",
  failed: "Report failed",
} as const;

export default async function DashboardPage() {
  const api = await getServerApi();
  // Both lists in parallel: one round trip of latency, not two.
  const [resumes, analyses, interviews] = await Promise.all([
    api.GET("/resumes").then(unwrap),
    api.GET("/analyses").then(unwrap),
    api.GET("/interviews").then(unwrap),
  ]);

  return (
    <div className="space-y-12">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          {resumes.length === 0 ? "Start with your resume" : "Your practice space"}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {resumes.length === 0
            ? "Upload it, then practice right away. A job description is optional."
            : "Pick a resume and practice now, or add a job description first."}
        </p>
      </header>

      <UploadResume />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Resumes</h2>
        {resumes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No resumes yet.</p>
        ) : (
          <ul className="divide-y rounded-2xl border bg-card">
            {resumes.map((r) => (
              <li key={r.id} className="flex items-center gap-2 pr-4">
                <Link href={`/resumes/${r.id}`} className="flex min-w-0 flex-1 items-center justify-between gap-4 p-4 hover:bg-muted/50">
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{r.name ?? r.file_name}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {r.file_name}, {formatDate(r.created_at)}
                    </span>
                  </span>
                </Link>
                <StartInterviewNow resumeId={r.id} compact />
              </li>
            ))}
          </ul>
        )}
      </section>

      {interviews.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground">Mock interviews</h2>
          <ul className="divide-y rounded-2xl border bg-card">
            {interviews.map((i) => {
              const live = i.status === "created" || i.status === "in_progress";
              return (
                <li key={i.id}>
                  <Link
                    href={live ? `/interviews/${i.id}` : `/interviews/${i.id}/report`}
                    className="flex items-center justify-between gap-4 p-4 hover:bg-muted/50"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{i.job_title ?? "General practice interview"}</span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {[i.company, formatDate(i.created_at)].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                    {i.status === "completed" ? (
                      <ScoreBadge score={i.overall_score} />
                    ) : (
                      <span className="shrink-0 text-sm text-muted-foreground">{INTERVIEW_STATUS[i.status]}</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Job match reports (optional)</h2>
        {analyses.length === 0 ? (
          <p className="text-sm text-muted-foreground">Optional: open a resume and paste a job description to see how well you match.</p>
        ) : (
          <ul className="divide-y rounded-2xl border bg-card">
            {analyses.map((a) => (
              <li key={a.id}>
                <Link href={`/analyses/${a.id}`} className="flex items-center justify-between gap-4 p-4 hover:bg-muted/50">
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{a.job_title ?? "Untitled role"}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {[a.company, formatDate(a.created_at)].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  <ScoreBadge score={a.score} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <DeleteMyData />
    </div>
  );
}
