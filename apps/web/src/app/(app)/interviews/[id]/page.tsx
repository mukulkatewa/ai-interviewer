import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { getServerApi, unwrap } from "@/lib/api/server";
import { InterviewRoom } from "./interview-room";

export const metadata: Metadata = { title: "Mock interview" };

export default async function InterviewPage({ params }: PageProps<"/interviews/[id]">) {
  const { id } = await params;
  const api = await getServerApi();
  const interview = unwrap(await api.GET("/interviews/{interview_id}", { params: { path: { interview_id: id } } }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Mock interview</h1>
        <p className="text-muted-foreground">
          {[interview.job_title ?? "Untitled role", interview.company].filter(Boolean).join(" · ")}
        </p>
      </header>

      {interview.status === "created" || interview.status === "in_progress" ? (
        // in_progress: the room offers "Resume" and the interviewer repeats the last question.
        <InterviewRoom interviewId={interview.id} />
      ) : (
        <div className="rounded-xl border p-8 text-center">
          <p className="font-medium">This interview is finished.</p>
          <Button className="mt-4" nativeButton={false} render={<Link href={`/interviews/${interview.id}/report`} />}>
            View report
          </Button>
        </div>
      )}
    </div>
  );
}
