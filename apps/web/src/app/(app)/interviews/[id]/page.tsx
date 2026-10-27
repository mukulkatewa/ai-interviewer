import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ButtonLink } from "@/components/button-link";
import { getServerApi, unwrap } from "@/lib/api/server";
import { InterviewRoom } from "./interview-room";

export const metadata: Metadata = { title: "Mock interview" };

export default async function InterviewPage({ params }: PageProps<"/interviews/[id]">) {
  const { id } = await params;
  const api = await getServerApi();
  const interview = unwrap(await api.GET("/interviews/{interview_id}", { params: { path: { interview_id: id } } }));

  return (
    <div className="space-y-4">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" aria-hidden />
        Dashboard
      </Link>

      {interview.status === "created" || interview.status === "in_progress" ? (
        // in_progress: the room offers "Resume" and the interviewer repeats the last question.
        <InterviewRoom
          interviewId={interview.id}
          jobTitle={interview.job_title ?? "Mock interview"}
          company={interview.company}
        />
      ) : (
        <div className="rounded-2xl border bg-card p-10 text-center">
          <h1 className="text-xl font-semibold">This interview is finished</h1>
          <p className="mt-1 text-sm text-muted-foreground">Your report has everything we heard and how it went.</p>
          <ButtonLink className="mt-5" href={`/interviews/${interview.id}/report`}>
            View report
          </ButtonLink>
        </div>
      )}
    </div>
  );
}
