"use client";

import { Button } from "@/components/ui/button";
import { type Status, useInterviewSocket } from "@/lib/interview/use-interview-socket";
import { cn } from "@/lib/utils";

const STATUS_TEXT: Record<Status, string> = {
  connecting: "Connecting…",
  ready: "Ready when you are. Turn your sound on; we'll ask for your microphone.",
  speaking: "Interviewer is speaking…",
  listening: "Your turn. Take your time.",
  thinking: "Got it, one moment…",
  failed: "",
};

export function InterviewRoom({ interviewId }: { interviewId: string }) {
  const { status, captions, problem, notice, userSpeaking, start, finishAnswer } = useInterviewSocket(interviewId);
  const listening = status === "listening";

  return (
    <div className="flex flex-col items-center gap-8 rounded-2xl border bg-card px-6 py-12">
      {/* Interviewer pulses while talking; ring turns green while the candidate talks. */}
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

      {status === "ready" && (
        <Button size="lg" className="h-11 px-6" onClick={start}>
          Start interview
        </Button>
      )}
      {listening && (
        <Button size="lg" variant="outline" className="h-11 px-6" onClick={finishAnswer}>
          Done answering
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
