"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { track } from "@/lib/analytics";
import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";
import { AnswerRecorder } from "./answer-recorder";
import { reconnectDelay } from "./reconnect";
import { AudioQueue } from "./audio-queue";

// Protocol: projectprep.md, section 6 (phase 8: interviewer speech arrives sentence by sentence).
type ServerMessage =
  | { type: "ready"; interview_id: string; resumable: boolean; total: number }
  | { type: "reply_start" }
  | { type: "sentence"; seq: number; text: string; audio: boolean }
  | { type: "transcript"; role: "candidate"; text: string }
  | { type: "turn_end"; question: number }
  | { type: "ended"; interview_id: string }
  | { type: "error"; code: string; message: string };

export type Status = "connecting" | "ready" | "speaking" | "listening" | "thinking" | "ending" | "ended" | "failed";
export type Caption = { role: "interviewer" | "candidate"; text: string };

const CLOSE_REASONS: Record<number, string> = {
  4401: "Your session expired. Reload the page to sign in again.",
  4404: "This interview doesn't exist or belongs to another account.",
  4409: "This interview is open in another tab. Close that one to continue here.",
  1013: "The server is busy. Try again in a minute.",
};

export function useInterviewSocket(interviewId: string) {
  const [status, setStatus] = useState<Status>("connecting");
  const [resumable, setResumable] = useState(false);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [problem, setProblem] = useState<string | null>(null); // fatal: shown instead of status
  const [notice, setNotice] = useState<string | null>(null); // recoverable: "didn't catch that"
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [question, setQuestion] = useState(0); // 0 warm-up, 1..total planned, total + 1 wrap-up
  const [total, setTotal] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const audio = useRef<AudioQueue>(new AudioQueue());
  const recorder = useRef<AnswerRecorder | null>(null);
  const micLevel = useRef(0);
  const ended = useRef(false);
  const ending = useRef(false); // the candidate asked to stop: ignore anything that belongs to the old turn
  const started = useRef(false); // Start was clicked: a reconnect resumes by itself, no second click

  useEffect(() => {
    let socket: WebSocket | null = null;
    let disposed = false;
    let attempt = 0; // reconnect attempts since the last successful connection
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const queue = audio.current;

    async function handle(message: ServerMessage) {
      switch (message.type) {
        case "ready":
          attempt = 0; // connected: the next drop starts the backoff over
          setResumable(message.resumable);
          setTotal(message.total);
          if (started.current && recorder.current) {
            // A reconnect in the middle of an interview (a deploy, a dropped connection): the microphone
            // and audio are still ours, so pick up where we left off. The interviewer repeats the last question.
            setNotice(null);
            setStatus("speaking");
            ws.current?.send(JSON.stringify({ type: "start" }));
          } else {
            setStatus("ready");
          }
          break;
        case "reply_start":
          if (!ending.current) setStatus("speaking");
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
          // The candidate already asked to stop: this belongs to the turn we cancelled.
          if (ending.current) return;
          setQuestion(message.question);
          // Arrives before playback ends: start listening only after, or the mic hears the interviewer (D28).
          await queue.idle();
          if (disposed || ending.current) return;
          setStatus("listening");
          await recorder.current?.listen();
          break;
        case "ended":
          ended.current = true;
          track("interview_completed");
          // A natural ending lets the closing line finish. After "End interview" the candidate has
          // already chosen to leave: show the result straight away.
          if (!ending.current) await queue.idle();
          if (disposed) return;
          setStatus("ended");
          void recorder.current?.destroy(); // release the microphone
          break;
        case "error":
          // "busy" is final (the server is full): show it as the problem. Answer errors are followed by
          // turn_end, so the candidate just answers again.
          if (message.code === "busy") setProblem(message.message);
          else setNotice(message.message);
          break;
      }
    }

    async function connect() {
      const { data } = await createClient().auth.getSession();
      const token = data.session?.access_token;
      if (disposed) return;
      if (!token) {
        setStatus("failed");
        setProblem(CLOSE_REASONS[4401]);
        return;
      }

      const mine = new WebSocket(`${env.apiUrl.replace(/^http/, "ws")}/interviews/${interviewId}/ws`);
      socket = mine;
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
        // A late close from a connection we already replaced must not start a second reconnect loop.
        if (disposed || ended.current || socket !== mine) return;
        void recorder.current?.abandon(); // never submit an answer to a dead socket
        const delay = reconnectDelay(event.code, attempt, ending.current);
        if (delay !== undefined) {
          attempt += 1;
          void queue.stop(); // half a sentence from the old connection must not play over the repeat
          setStatus("connecting");
          setNotice("Connection lost. Reconnecting…");
          retryTimer = setTimeout(() => void connect(), delay);
          return;
        }
        setStatus("failed");
        // A specific reason (e.g. "all rooms are full") was already shown from the server's message.
        setProblem((p) => p ?? CLOSE_REASONS[event.code] ?? "Connection lost. Reload the page to continue where you left off.");
        void recorder.current?.destroy();
      };
    }
    void connect();

    return () => {
      disposed = true;
      clearTimeout(retryTimer);
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
        onLevel: (level) => {
          micLevel.current = level;
        },
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
    started.current = true;
    setStatus("speaking");
    setStartedAt((t) => t ?? Date.now());
    ws.current?.send(JSON.stringify({ type: "start" }));
    track("interview_started");
  }, []);

  /** "Done answering": submit now instead of waiting for silence (D27). */
  const finishAnswer = useCallback(() => void recorder.current?.done(), []);

  /** "End interview": cut the sound, stop listening, and ask the server to wrap up (D33). */
  const endInterview = useCallback(async () => {
    ending.current = true;
    setStatus("ending");
    setNotice(null);
    ws.current?.send(JSON.stringify({ type: "end" })); // first: the server cancels what it's saying
    await audio.current.stop(); // silence at once, not after the sentence finishes
    await audio.current.unlock(); // a fresh context for the closing line (this click is the user gesture)
    await recorder.current?.destroy();
    recorder.current = null;
  }, []);

  /** Loudness for the voice orb: the interviewer's audio while it speaks, the microphone while you do. */
  const getLevel = useCallback(
    () => {
      const voice = audio.current.level();
      return voice > 0.02 ? voice : micLevel.current;
    },
    [],
  );

  return {
    status,
    resumable,
    captions,
    problem,
    notice,
    userSpeaking,
    question,
    total,
    startedAt,
    start,
    finishAnswer,
    endInterview,
    getLevel,
  };
}
