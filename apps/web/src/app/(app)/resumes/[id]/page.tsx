import type { Metadata } from "next";

import { Badge } from "@/components/ui/badge";
import { getServerApi, unwrap } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { AnalyzeForm } from "./analyze-form";
import { DeleteResume } from "./delete-resume";

export const metadata: Metadata = { title: "Resume" };

export default async function ResumePage({ params }: PageProps<"/resumes/[id]">) {
  const { id } = await params;
  const api = await getServerApi();
  const resume = unwrap(await api.GET("/resumes/{resume_id}", { params: { path: { resume_id: id } } }));
  const { profile } = resume;

  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
      <article className="min-w-0 space-y-8">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">{profile.name ?? resume.file_name}</h1>
          {profile.headline && <p className="mt-1 text-muted-foreground">{profile.headline}</p>}
          <p className="mt-2 text-xs text-muted-foreground">
            {resume.file_name} · uploaded {formatDate(resume.created_at)}
          </p>
        </header>

        {profile.skills.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground">Skills</h2>
            <div className="flex flex-wrap gap-1.5">
              {profile.skills.map((s) => (
                <Badge key={s} variant="secondary">
                  {s}
                </Badge>
              ))}
            </div>
          </section>
        )}

        {profile.experience.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-medium text-muted-foreground">Experience</h2>
            {profile.experience.map((e, i) => (
              <div key={`${e.company}-${i}`}>
                <p className="font-medium">
                  {e.role} · {e.company}
                </p>
                <p className="text-sm text-muted-foreground">{[e.start, e.end].filter(Boolean).join(" – ")}</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {e.highlights.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        )}

        {profile.projects.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">Projects</h2>
            {profile.projects.map((p) => (
              <div key={p.name}>
                <p className="font-medium">{p.name}</p>
                {p.description && <p className="text-sm text-muted-foreground">{p.description}</p>}
              </div>
            ))}
          </section>
        )}

        {profile.education.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground">Education</h2>
            {profile.education.map((ed) => (
              <p key={ed.institution} className="text-sm">
                {[ed.degree, ed.institution, ed.year].filter(Boolean).join(", ")}
              </p>
            ))}
          </section>
        )}

        <DeleteResume resumeId={resume.id} />
      </article>

      <aside className="lg:sticky lg:top-8 lg:self-start">
        <AnalyzeForm resumeId={resume.id} />
      </aside>
    </div>
  );
}
