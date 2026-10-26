import type { Metadata } from "next";
import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import { getServerApi, unwrap } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { UploadResume } from "./upload-resume";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const api = await getServerApi();
  // Both lists in parallel: one round trip of latency, not two.
  const [resumes, analyses] = await Promise.all([
    api.GET("/resumes").then(unwrap),
    api.GET("/analyses").then(unwrap),
  ]);

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      <UploadResume />

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Resumes</h2>
        {resumes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No resumes yet. Upload one to get started.</p>
        ) : (
          <ul className="divide-y rounded-xl border">
            {resumes.map((r) => (
              <li key={r.id}>
                <Link href={`/resumes/${r.id}`} className="flex items-center justify-between gap-4 p-4 hover:bg-muted/50">
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{r.name ?? r.file_name}</span>
                    <span className="block truncate text-sm text-muted-foreground">{r.file_name}</span>
                  </span>
                  <span className="shrink-0 text-sm text-muted-foreground">{formatDate(r.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Job match reports</h2>
        {analyses.length === 0 ? (
          <p className="text-sm text-muted-foreground">Open a resume and paste a job description to get your first report.</p>
        ) : (
          <ul className="divide-y rounded-xl border">
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
    </div>
  );
}
