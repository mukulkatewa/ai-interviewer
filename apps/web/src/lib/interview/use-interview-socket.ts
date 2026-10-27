"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { track } from "@/lib/analytics";
import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";
import { AnswerRecorder } from "./answer-recorder";
import { AudioQueue } from "./audio-queue";

// Protocol: projectprep.md, section 6 (phase 8: interviewer speech arrives sentence by sentence).
type ServerMessage =
  | { type: "ready"; interview_id: string; resumable: boolean }
  | { type: "reply_start" }
  | { type: "sentence"; seq: number; text: string; audio: boolean }
  | { type: "transcript"; role: "candidate"; text: string }
  | { type: "turn_end"; question: number }
  | { type: "ended"; interview_id: string }
  | { type: "error"; code: string; message: string };

export type Status = "connecting" | "ready" | "speaking" | "listening" | "thinking" | "ended" | "failed";
export type Caption = { role: "interviewer" | "candidate"; text: string };

const CLOSE_REASONS: Record<number, string> = {
  4401: "Your session expired. Reload the page to sign in again.",
  4404: "This interview doesn't exist or belongs to another account.",
  4409: "This interview was opened in another tab.",
  1013: "The server is busy. Try again in a minute.",
};

export function useInterviewSocket(interviewId: string) {
  const [status, setStatus] = useState<Status>("connecting");
  const [resumable, setResumable] = useState(false);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [problem, setProblem] = useState<string | null>(null); // fatal: shown instead of status
  const [notice, setNotice] = useState<string | null>(null); // recoverable: "didn't catch that"
  const [userSpeaking, setUserSpeaking] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const audio = useRef<AudioQueue>(new AudioQueue());
  const recorder = useRef<AnswerRecorder | null>(null);
  const ended = useRef(false);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let disposed = false;
    const queue = audio.current;

    async function handle(message: ServerMessage) {
      switch (message.type) {
        case "ready":
          setResumable(message.resumable);
          setStatus("ready");
          break;
        case "reply_start":
          setStatus("speaking");
          setCaptions((c) => [...c, { role: "interviewer", text: "" }]);
          break;
        case "sentence":
          setCaptions((c) => {
            const last = c[c.length - 1];
            return [...c.slice(0, -1), { ...last, text: last.text ? `${last.text} ${message.text}` : message.text }];
          });
          // With audio, the next binary frame is this sentence's MP3; without, the browser speaks it (D26).
          if (!message.audio) queue.enqueueSpeech(message.text);
          break;
        case "transcript":
          setCaptions((c) => [...c, { role: "candidate", text: message.text }]);
          break;
        case "turn_end":
          // Arrives before playback ends: start listening only after, or the mic hears the interviewer (D28).
          await queue.idle();
          if (disposed) return;
          setStatus("listening");
          await recorder.current?.listen();
          break;
        case "ended":
          ended.current = true;
          track("interview_completed");
          await queue.idle(); // let the closing line finish
          if (disposed) return;
          setStatus("ended");
          void recorder.current?.destroy(); // release the microphone
          break;
        case "error":
          setNotice(message.message); // answer errors are followed by turn_end: the candidate just answers again
          break;
      }
    }

    (async () => {
      const { data } = await createClient().auth.getSession();
      const token = data.session?.access_token;
      if (disposed) return;
      if (!token) {
        setStatus("failed");
        setProblem(CLOSE_REASONS[4401]);
        return;
      }

      socket = new WebSocket(`${env.apiUrl.replace(/^http/, "ws")}/interviews/${interviewId}/ws`);
      socket.binaryType = "arraybuffer";
      ws.current = socket;
      // Token in the first message, never the URL: URLs end up in logs (projectprep.md, 6).
      socket.onopen = () => socket?.send(JSON.stringify({ type: "auth", token }));
      // Handlers run in arrival order; the queue keeps audio and browser speech in order too.
      let pending = Promise.resolve();
      socket.onmessage = (event) => {
        pending = pending.then(() =>
          typeof event.data === "string" ? handle(JSON.parse(event.data) as ServerMessage) : queue.enqueue(event.data),
        );
      };
      socket.onclose = (event) => {
        if (disposed || ended.current) return;
        setStatus("failed");
        setProblem(CLOSE_REASONS[event.code] ?? "Connection lost. Reload the page to continue where you left off.");
        void recorder.current?.destroy();
      };
    })();

    return () => {
      disposed = true;
      socket?.close();
      void queue.close();
      void recorder.current?.destroy();
      recorder.current = null;
      audio.current = new AudioQueue(); // a fresh queue if the effect re-runs (React Strict Mode)
    };
  }, [interviewId]);

  /** Start/Resume button: unlock audio and ask for the mic in the same click (browsers require a gesture). */
  const start = useCallback(async () => {
    await audio.current.unlock();
    try {
      recorder.current = await AnswerRecorder.create({
        onSpeaking: setUserSpeaking,
        onAnswer: (wav) => {
          setUserSpeaking(false);
          setNotice(null);
          setStatus("thinking");
          ws.current?.send(wav);
        },
        onNothingHeard: () => {
          setNotice("We didn't hear anything. Answer whenever you're ready.");
          void recorder.current?.listen();
        },
      });
    } catch {
      setNotice("Microphone access is needed to answer. Allow it in your browser, then press Start again.");
      return;
    }
    setNotice(null);
    setStatus("speaking");
    ws.current?.send(JSON.stringify({ type: "start" }));
    track("interview_started");
  }, []);

  /** "Done answering": submit now instead of waiting for silence (D27). */
  const finishAnswer = useCallback(() => void recorder.current?.done(), []);

  /** "End interview": stop early; the server says a closing line and generates the report. */
  const endInterview = useCallback(async () => {
    await recorder.current?.destroy();
    recorder.current = null;
    setStatus("speaking");
    ws.current?.send(JSON.stringify({ type: "end" }));
  }, []);

  return { status, resumable, captions, problem, notice, userSpeaking, start, finishAnswer, endInterview };
}
