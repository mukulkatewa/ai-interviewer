"use client";

import { CheckIcon, HeadphonesIcon, MicIcon, TimerIcon, Volume2Icon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ButtonLink } from "@/components/button-link";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { type OrbState, VoiceOrb } from "@/components/voice-orb";
import { type Caption, type Status, useInterviewSocket } from "@/lib/interview/use-interview-socket";
import { cn } from "@/lib/utils";

const ORB: Record<Status, OrbState> = {
  connecting: "idle",
  ready: "idle",
  speaking: "interviewer",
  listening: "you",
  thinking: "thinking",
  ending: "thinking",
  ended: "done",
  failed: "idle",
};

function elapsed(startedAt: number | null, now: number): string {
  if (!startedAt) return "0:00";
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Re-renders once a second while the interview is running (and never during server rendering). */
function useNow(running: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  return now;
}

function progressLabel(question: number, total: number): string {
  if (question === 0) return "Warm-up";
  if (question > total) return "Wrap-up";
  return `Question ${question} of ${total}`;
}

function Transcript({ captions }: { captions: Caption[] }) {
  const end = useRef<HTMLDivElement>(null);
  // Keep the newest line in view. Braces matter: newer browsers return a Promise from
  // scrollIntoView, and React would call a returned value as the effect's cleanup.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [captions]);

  if (captions.length === 0) {
    return <p className="text-sm text-muted-foreground">The conversation appears here as you talk.</p>;
  }
  return (
    <ol className="space-y-4" aria-label="Transcript">
      {captions.map((c, i) => (
        <li key={i} className={cn("text-sm leading-relaxed", c.role === "candidate" && "pl-4")}>
          <p className={cn("mb-0.5 text-xs font-medium", c.role === "interviewer" ? "text-primary" : "text-amber-300")}>
            {c.role === "interviewer" ? "Interviewer" : "You"}
          </p>
          <p className="text-pretty text-foreground/90">{c.text}</p>
        </li>
      ))}
      <div ref={end} />
    </ol>
  );
}

const CHECKS = [
  { icon: Volume2Icon, text: "Sound on, in a quiet room" },
  { icon: HeadphonesIcon, text: "Headphones help: the microphone won't hear the interviewer" },
  { icon: MicIcon, text: "Allow the microphone when your browser asks" },
  { icon: TimerIcon, text: "About 15 minutes. You can stop any time" },
];

export function InterviewRoom({
  interviewId,
  jobTitle,
  company,
}: {
  interviewId: string;
  jobTitle: string;
  company: string | null;
}) {
  const room = useInterviewSocket(interviewId);
  const { status, captions, problem, notice, userSpeaking, question, total, startedAt } = room;
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false); // mobile only: desktop always shows it
  const live = status === "speaking" || status === "listening" || status === "thinking";
  const now = useNow(live || status === "ending");

  const lastInterviewer = [...captions].reverse().find((c) => c.role === "interviewer")?.text ?? "";
  const progress = total > 0 ? Math.min(100, Math.round((question / (total + 1)) * 100)) : 0;

  const statusText =
    problem ??
    {
      connecting: "Connecting…",
      ready: "",
      speaking: "The interviewer is speaking",
      listening: userSpeaking ? "Listening to you" : "Your turn. Take your time",
      thinking: "Thinking about your answer",
      ending: "Wrapping up",
      ended: "Interview complete",
      failed: "",
    }[status];

  return (
    // `dark` makes this one panel a dark stage in both themes.
    <div className="dark overflow-hidden rounded-[1.75rem] border border-white/10 bg-[oklch(0.15_0.035_268)] text-foreground shadow-2xl shadow-black/20">
      <div className="grid lg:grid-cols-[1fr_21rem]">
        <section className="relative flex min-h-[34rem] flex-col lg:min-h-[40rem]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_38%,oklch(0.27_0.09_268/0.55),transparent_62%)]" />

          <header className="relative flex items-center justify-between gap-4 px-5 pt-5 sm:px-7">
            <div className="min-w-0">
              <p className="truncate font-medium">{jobTitle}</p>
              {company && <p className="truncate text-sm text-muted-foreground">{company}</p>}
            </div>
            <p className="flex shrink-0 items-center gap-1.5 text-sm tabular-nums text-muted-foreground" aria-label="Time elapsed">
              <TimerIcon className="size-4" aria-hidden />
              {elapsed(startedAt, now)}
            </p>
          </header>

          {(live || status === "ending") && (
            <div className="relative mx-5 mt-4 sm:mx-7">
              <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
                <span>{progressLabel(question, total)}</span>
              </div>
              <Progress value={progress} aria-label="Interview progress" />
            </div>
          )}

          <div className="relative flex flex-1 flex-col items-center justify-center gap-6 px-6 py-8 text-center">
            {status === "ended" ? (
              <>
                <VoiceOrb state="done" getLevel={room.getLevel} className="w-36" />
                <div>
                  <h2 className="text-2xl font-semibold">Interview complete</h2>
                  <p className="mt-1 text-muted-foreground">We&apos;re writing your report now. It takes about a minute.</p>
                </div>
                <ButtonLink href={`/interviews/${interviewId}/report`} size="lg" className="h-11 px-6">
                  View your report
                </ButtonLink>
              </>
            ) : status === "ready" ? (
              <>
                <VoiceOrb state="idle" getLevel={room.getLevel} className="mb-2 w-32" />
                <div className="max-w-md">
                  <h2 className="text-2xl font-semibold">{room.resumable ? "Welcome back" : "Ready when you are"}</h2>
                  <ul className="mt-5 space-y-2.5 text-left text-sm text-muted-foreground">
                    {CHECKS.map(({ icon: Icon, text }) => (
                      <li key={text} className="flex items-start gap-3">
                        <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button size="lg" className="h-11 px-7" onClick={room.start}>
                  {room.resumable ? "Resume interview" : "Start interview"}
                </Button>
                {notice && <p className="text-sm text-amber-300">{notice}</p>}
              </>
            ) : (
              <>
                <VoiceOrb state={ORB[status]} getLevel={room.getLevel} className="mb-4 w-44 sm:w-56" />
                <div className="min-h-24 max-w-xl space-y-3" role="status" aria-live="polite">
                  <p className={cn("text-sm font-medium", status === "listening" ? "text-amber-300" : "text-muted-foreground")}>
                    {statusText}
                  </p>
                  {lastInterviewer && status !== "failed" && (
                    <p className="text-balance text-lg leading-snug text-foreground/95 sm:text-xl">{lastInterviewer}</p>
                  )}
                  {notice && !problem && <p className="text-sm text-amber-300">{notice}</p>}
                  {status === "failed" && (
                    <Button variant="outline" onClick={() => window.location.reload()}>
                      Reload
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>

          {(live || status === "ending") && (
            <footer className="relative flex flex-wrap items-center justify-center gap-3 px-5 pb-6 sm:px-7">
              <Button
                size="lg"
                className={cn(
                  "h-11 rounded-full px-6",
                  status === "listening" && "bg-amber-300 text-amber-950 hover:bg-amber-200",
                )}
                disabled={status !== "listening"}
                onClick={room.finishAnswer}
              >
                <CheckIcon aria-hidden /> Done answering
              </Button>
              <Button
                size="lg"
                variant="ghost"
                className="h-11 rounded-full px-5 text-muted-foreground hover:text-foreground"
                disabled={status === "ending"}
                onClick={() => setConfirmEnd(true)}
              >
                End interview
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="rounded-full text-muted-foreground lg:hidden"
                onClick={() => setShowTranscript((v) => !v)}
                aria-expanded={showTranscript}
              >
                {showTranscript ? "Hide transcript" : "Show transcript"}
              </Button>
            </footer>
          )}
        </section>

        <aside
          className={cn(
            "border-t border-white/10 lg:border-t-0 lg:border-l",
            showTranscript ? "block" : "hidden lg:block",
          )}
        >
          <div className="max-h-80 overflow-y-auto p-5 lg:max-h-none lg:h-full lg:max-h-[40rem]">
            <h2 className="mb-4 text-sm font-medium text-muted-foreground">Transcript</h2>
            <Transcript captions={captions} />
          </div>
        </aside>
      </div>

      <AlertDialog open={confirmEnd} onOpenChange={setConfirmEnd}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>End the interview now?</AlertDialogTitle>
            <AlertDialogDescription>
              We&apos;ll wrap up and write your report from the answers so far.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep going</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirmEnd(false);
                void room.endInterview();
              }}
            >
              End and get report
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
