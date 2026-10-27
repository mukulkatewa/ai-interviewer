import type { Metadata } from "next";
import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import { getServerApi, unwrap } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { DeleteMyData } from "./delete-my-data";
import { UploadResume } from "./upload-resume";

export const metadata: Metadata = { title: "Dashboard" };

const INTERVIEW_STATUS = {
  created: { label: "Not started", dot: "bg-muted-foreground" },
  in_progress: { label: "In progress", dot: "bg-amber-500" },
  evaluating: { label: "Writing report", dot: "bg-primary animate-pulse" },
  completed: { label: "Done", dot: "bg-emerald-500" },
  failed: { label: "Report failed", dot: "bg-destructive" },
} as const;

/** One list row: a title with a line under it on the left, one fact on the right. */
function Row({ href, title, subtitle, aside }: { href: string; title: string; subtitle?: string; aside: React.ReactNode }) {
  return (
    <li>
      <Link href={href} className="flex items-center justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-muted/60">
        <span className="min-w-0">
          <span className="block truncate font-medium">{title}</span>
          {subtitle && <span className="block truncate text-sm text-muted-foreground">{subtitle}</span>}
        </span>
        <span className="shrink-0 text-sm text-muted-foreground">{aside}</span>
      </Link>
    </li>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default async function DashboardPage() {
  const api = await getServerApi();
  // All three lists in parallel: one round trip of latency, not three.
  const [resumes, analyses, interviews] = await Promise.all([
    api.GET("/resumes").then(unwrap),
    api.GET("/analyses").then(unwrap),
    api.GET("/interviews").then(unwrap),
  ]);

  // First visit: one obvious thing to do.
  if (resumes.length === 0) {
    return (
      <div className="mx-auto max-w-xl space-y-8 pt-6">
        <div className="text-center">
          <h1 className="text-3xl font-semibold sm:text-4xl">Start with your resume</h1>
          <p className="mt-3 text-muted-foreground text-pretty">
            Everything else builds on it: the job match, the interview questions and your report.
          </p>
        </div>
        <UploadResume prominent />
        <DeleteMyData />
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <h1 className="text-3xl font-semibold">Dashboard</h1>

      <div className="grid gap-10 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-10">
          <Section title="Mock interviews">
            {interviews.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                Open a resume, match it against a job, then start your first interview from the report.
              </p>
            ) : (
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {interviews.map((i) => {
                  const live = i.status === "created" || i.status === "in_progress";
                  const status = INTERVIEW_STATUS[i.status];
                  return (
                    <Row
                      key={i.id}
                      href={live ? `/interviews/${i.id}` : `/interviews/${i.id}/report`}
                      title={i.job_title ?? "Untitled role"}
                      subtitle={i.company ?? undefined}
                      aside={
                        i.status === "completed" ? (
                          <ScoreBadge score={i.overall_score} />
                        ) : (
                          <span className="flex items-center gap-2">
                            <span className={cn("size-2 rounded-full", status.dot)} aria-hidden />
                            {status.label}
                          </span>
                        )
                      }
                    />
                  );
                })}
              </ul>
            )}
          </Section>

          <Section title="Job match reports">
            {analyses.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                Open a resume and paste a job description to see how well you match.
              </p>
            ) : (
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {analyses.map((a) => (
                  <Row
                    key={a.id}
                    href={`/analyses/${a.id}`}
                    title={a.job_title ?? "Untitled role"}
                    subtitle={a.company ?? formatDate(a.created_at)}
                    aside={<ScoreBadge score={a.score} />}
                  />
                ))}
              </ul>
            )}
          </Section>
        </div>

        <aside className="space-y-10">
          <Section title="Your resumes">
            <ul className="divide-y overflow-hidden rounded-xl border bg-card">
              {resumes.map((r) => (
                <Row
                  key={r.id}
                  href={`/resumes/${r.id}`}
                  title={r.name ?? r.file_name}
                  subtitle={formatDate(r.created_at)}
                  aside={null}
                />
              ))}
            </ul>
            <UploadResume />
          </Section>
        </aside>
      </div>

      <DeleteMyData />
    </div>
  );
}
