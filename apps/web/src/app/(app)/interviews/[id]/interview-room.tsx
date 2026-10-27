"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { type Status, useInterviewSocket } from "@/lib/interview/use-interview-socket";
import { cn } from "@/lib/utils";

const STATUS_TEXT: Record<Status, string> = {
  connecting: "Connecting…",
  ready: "Ready when you are. Turn your sound on; we'll ask for your microphone.",
  speaking: "Interviewer is speaking…",
  listening: "Your turn. Take your time, or press Done when you've finished.",
  thinking: "One moment…",
  ended: "",
  failed: "",
};

export function InterviewRoom({ interviewId }: { interviewId: string }) {
  const { status, resumable, captions, problem, notice, userSpeaking, start, finishAnswer, endInterview } =
    useInterviewSocket(interviewId);
  const listening = status === "listening";
  const live = status === "speaking" || listening || status === "thinking";
  const transcriptEnd = useRef<HTMLDivElement>(null);

  // Keep the newest caption in view as the conversation grows. Braces matter: newer
  // browsers return a Promise from scrollIntoView, and React would call a returned
  // value as the effect's cleanup ("i is not a function"), crashing the room.
  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [captions]);

  if (status === "ended") {
    return (
      <div className="rounded-2xl border bg-card px-6 py-12 text-center">
        <p className="text-lg font-medium">Interview complete</p>
        <p className="mt-1 text-muted-foreground">Your feedback report is being prepared. It takes about a minute.</p>
        <Button className="mt-6" nativeButton={false} render={<Link href={`/interviews/${interviewId}/report`} />}>
          View report
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-8 rounded-2xl border bg-card px-6 py-12">
      {/* Interviewer pulses while talking; turns green while it's the candidate's turn. */}
      <div className="relative grid size-28 place-items-center" aria-hidden>
        <span
          className={cn(
            "absolute inset-0 rounded-full bg-primary/15",
            status === "speaking" && "animate-ping",
            listening && "bg-emerald-500/20",
            listening && userSpeaking && "animate-pulse",
          )}
        />
        <span className={cn("relative size-20 rounded-full bg-primary transition-colors", listening && "bg-emerald-600")} />
      </div>

      <div className="space-y-1 text-center" role="status" aria-live="polite">
        <p className="text-sm text-muted-foreground">
          {problem ?? (listening && userSpeaking ? "Listening…" : STATUS_TEXT[status])}
        </p>
        {notice && !problem && <p className="text-sm text-amber-700 dark:text-amber-300">{notice}</p>}
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        {status === "ready" && (
          <Button size="lg" className="h-11 px-6" onClick={start}>
            {resumable ? "Resume interview" : "Start interview"}
          </Button>
        )}
        {listening && (
          <Button size="lg" variant="outline" className="h-11 px-6" onClick={finishAnswer}>
            Done answering
          </Button>
        )}
        {live && (
          <Button
            size="lg"
            variant="ghost"
            className="h-11 px-6 text-muted-foreground"
            onClick={() => window.confirm("End the interview now? You'll still get a report.") && void endInterview()}
          >
            End interview
          </Button>
        )}
      </div>

      {captions.length > 0 && (
        <ol className="w-full max-w-2xl space-y-3" aria-label="Transcript">
          {captions.map((c, i) => (
            <li key={i} className={cn("rounded-xl p-4", c.role === "interviewer" ? "bg-muted" : "border")}>
              <p className="text-xs font-medium text-muted-foreground">
                {c.role === "interviewer" ? "Interviewer" : "You"}
              </p>
              <p className="mt-1 text-pretty">{c.text}</p>
            </li>
          ))}
          <div ref={transcriptEnd} />
        </ol>
      )}
    </div>
  );
}
