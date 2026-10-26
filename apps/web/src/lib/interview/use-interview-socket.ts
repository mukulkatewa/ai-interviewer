"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";
import { AudioQueue, speakWithBrowser } from "./audio-queue";

// Protocol: projectprep.md, section 6.
type ServerMessage =
  | { type: "ready"; interview_id: string }
  | { type: "transcript"; role: "interviewer" | "candidate"; text: string }
  | { type: "audio_meta"; seq: number; text: string }
  | { type: "turn_end"; phase: string }
  | { type: "error"; code: string; message: string; text?: string };

export type Status = "connecting" | "ready" | "speaking" | "your_turn" | "failed";
export type Caption = { role: "interviewer" | "candidate"; text: string };

const CLOSE_REASONS: Record<number, string> = {
  4401: "Your session expired. Reload the page to sign in again.",
  4404: "This interview doesn't exist or belongs to another account.",
  1013: "The server is busy. Try again in a minute.",
};

export function useInterviewSocket(interviewId: string) {
  const [status, setStatus] = useState<Status>("connecting");
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const audio = useRef<AudioQueue>(new AudioQueue());

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
          break;
        case "audio_meta":
          break; // the next binary frame is this sentence's audio; captions already show the text
        case "turn_end":
          // The message arrives before the audio finishes playing: wait for playback.
          await queue.idle();
          if (!disposed) setStatus("your_turn");
          break;
        case "error":
          if (message.code === "tts_unavailable" && message.text) {
            await queue.idle(); // finish what our TTS already sent, then read the rest (D26)
            await speakWithBrowser(message.text);
          } else {
            setProblem(message.message);
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
      audio.current = new AudioQueue(); // a fresh queue if the effect re-runs (React Strict Mode)
    };
  }, [interviewId]);

  /** Call from the Start button's click handler (audio unlock needs the gesture). */
  const start = useCallback(async () => {
    await audio.current.unlock();
    setStatus("speaking");
    ws.current?.send(JSON.stringify({ type: "start" }));
  }, []);

  return { status, captions, problem, start };
}
