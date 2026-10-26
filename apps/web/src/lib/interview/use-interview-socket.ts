"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";
import { AnswerRecorder } from "./answer-recorder";
import { AudioQueue, speakWithBrowser } from "./audio-queue";

// Protocol: projectprep.md, section 6.
type ServerMessage =
  | { type: "ready"; interview_id: string }
  | { type: "transcript"; role: "interviewer" | "candidate"; text: string }
  | { type: "audio_meta"; seq: number; text: string }
  | { type: "turn_end"; phase: string }
  | { type: "error"; code: string; message: string; text?: string };

export type Status = "connecting" | "ready" | "speaking" | "listening" | "thinking" | "failed";
export type Caption = { role: "interviewer" | "candidate"; text: string };

const CLOSE_REASONS: Record<number, string> = {
  4401: "Your session expired. Reload the page to sign in again.",
  4404: "This interview doesn't exist or belongs to another account.",
  1013: "The server is busy. Try again in a minute.",
};

export function useInterviewSocket(interviewId: string) {
  const [status, setStatus] = useState<Status>("connecting");
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [problem, setProblem] = useState<string | null>(null); // fatal: shown instead of status
  const [notice, setNotice] = useState<string | null>(null); // recoverable: "didn't catch that"
  const [userSpeaking, setUserSpeaking] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const audio = useRef<AudioQueue>(new AudioQueue());
  const recorder = useRef<AnswerRecorder | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let disposed = false;
    const queue = audio.current;

    async function handle(message: ServerMessage) {
      switch (message.type) {
        case "ready":
          setStatus("ready");
          break;
        case "transcript":
          setCaptions((c) => [...c, { role: message.role, text: message.text }]);
          if (message.role === "interviewer") setStatus("speaking");
          break;
        case "audio_meta":
          break; // the next binary frame is this sentence's audio; captions already show the text
        case "turn_end":
          // Arrives before the audio finishes: only start listening once playback ends,
          // or the mic would hear the interviewer (D28).
          await queue.idle();
          if (disposed) return;
          setStatus("listening");
          await recorder.current?.listen();
          break;
        case "error":
          if (message.code === "tts_unavailable" && message.text) {
            await queue.idle(); // finish what our TTS already sent, then read the rest (D26)
            await speakWithBrowser(message.text);
          } else {
            setNotice(message.message); // the server follows answer errors with turn_end
          }
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
      // Handlers run in arrival order; the queue keeps audio in order too.
      let pending = Promise.resolve();
      socket.onmessage = (event) => {
        pending = pending.then(() =>
          typeof event.data === "string" ? handle(JSON.parse(event.data) as ServerMessage) : queue.enqueue(event.data),
        );
      };
      socket.onclose = (event) => {
        if (disposed) return;
        setStatus("failed");
        setProblem(CLOSE_REASONS[event.code] ?? "Connection lost. Reload the page to continue.");
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

  /** Start button: unlock audio and ask for the mic in the same click (browsers require a gesture). */
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
  }, []);

  /** "Done answering": submit now instead of waiting for silence (D27). */
  const finishAnswer = useCallback(() => void recorder.current?.done(), []);

  return { status, captions, problem, notice, userSpeaking, start, finishAnswer };
}
