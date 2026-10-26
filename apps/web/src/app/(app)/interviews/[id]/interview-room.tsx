"use client";

import { Button } from "@/components/ui/button";
import { type Status, useInterviewSocket } from "@/lib/interview/use-interview-socket";
import { cn } from "@/lib/utils";

const STATUS_TEXT: Record<Status, string> = {
  connecting: "Connecting…",
  ready: "Ready when you are. Turn your sound on.",
  speaking: "Interviewer is speaking…",
  your_turn: "Your turn. Answering by voice arrives in the next update.",
  failed: "",
};

export function InterviewRoom({ interviewId }: { interviewId: string }) {
  const { status, captions, problem, start } = useInterviewSocket(interviewId);
  const speaking = status === "speaking";

  return (
    <div className="flex flex-col items-center gap-8 rounded-2xl border bg-card px-6 py-12">
      {/* The "interviewer": pulses while audio is playing. */}
      <div className="relative grid size-28 place-items-center" aria-hidden>
        <span className={cn("absolute inset-0 rounded-full bg-primary/15", speaking && "animate-ping")} />
        <span className="relative size-20 rounded-full bg-primary" />
      </div>

      <p className="text-sm text-muted-foreground" role="status" aria-live="polite">
        {problem ?? STATUS_TEXT[status]}
      </p>

      {status === "ready" && (
        <Button size="lg" className="h-11 px-6" onClick={start}>
          Start interview
        </Button>
      )}

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
        </ol>
      )}
    </div>
  );
}
