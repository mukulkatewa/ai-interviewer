"use client";

import { type CSSProperties, useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/** Who the orb is about right now. Color carries it: blue is the interviewer, amber is you. */
export type OrbState = "idle" | "interviewer" | "you" | "thinking" | "done";

const COLOR: Record<OrbState, string> = {
  idle: "oklch(0.62 0.05 268)",
  interviewer: "var(--voice-interviewer)",
  you: "var(--voice-you)",
  thinking: "var(--voice-interviewer)",
  done: "oklch(0.74 0.15 160)",
};

const LABEL: Record<OrbState, string> = {
  idle: "Waiting",
  interviewer: "The interviewer is speaking",
  you: "Your turn to speak",
  thinking: "Working on a reply",
  done: "Finished",
};

// Each ring follows the loudness a little more than the one inside it.
const RINGS = [
  { inset: "0%", reach: 0.16, opacity: 0.55 },
  { inset: "-7%", reach: 0.3, opacity: 0.36 },
  { inset: "-14%", reach: 0.46, opacity: 0.2 },
];

/**
 * The interview's one memorable element: a ring that moves with the real audio level.
 * `getLevel` is read every animation frame and written straight to a CSS variable, so
 * React never re-renders 60 times a second. With reduced motion requested, the size
 * stays still and only the color and label change.
 */
export function VoiceOrb({
  state,
  getLevel,
  className,
}: {
  state: OrbState;
  getLevel: () => number;
  className?: string;
}) {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (calm || state === "idle" || state === "done" || state === "thinking") {
      el.style.setProperty("--level", "0");
      return;
    }
    let frame = 0;
    let level = 0;
    const tick = () => {
      level = level * 0.78 + getLevel() * 0.22; // smoothing: raw levels flicker
      el.style.setProperty("--level", level.toFixed(3));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [state, getLevel]);

  return (
    <div
      ref={root}
      role="img"
      aria-label={LABEL[state]}
      className={cn("relative aspect-square", className)}
      style={{ "--orb": COLOR[state], "--level": 0 } as CSSProperties}
    >
      <div
        className="absolute -inset-[22%] rounded-full opacity-50 blur-3xl transition-[background] duration-700"
        style={{
          background: "radial-gradient(circle, var(--orb), transparent 62%)",
          transform: "scale(calc(1 + var(--level) * 0.6))",
        }}
      />
      {RINGS.map((ring) => (
        <div
          key={ring.inset}
          className="orb-ring absolute rounded-full border transition-[transform,border-color] duration-150 ease-out"
          style={{
            inset: ring.inset,
            borderColor: "color-mix(in oklch, var(--orb) 55%, transparent)",
            opacity: ring.opacity,
            transform: `scale(calc(1 + var(--level) * ${ring.reach}))`,
          }}
        />
      ))}
      {state === "thinking" && (
        <div
          className="orb-spin absolute -inset-[8%] rounded-full"
          style={{
            background: "conic-gradient(from 0deg, transparent 0 50%, var(--orb))",
            WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
            mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
            animation: "orb-spin 1.6s linear infinite",
          }}
        />
      )}
      <div
        className="orb-ring absolute inset-[14%] rounded-full transition-[background,transform] duration-700"
        style={{
          background:
            "radial-gradient(circle at 34% 28%, color-mix(in oklch, var(--orb) 35%, white), var(--orb) 52%, color-mix(in oklch, var(--orb) 55%, black))",
          boxShadow: "inset 0 -10px 30px color-mix(in oklch, var(--orb) 40%, black), 0 20px 60px -20px var(--orb)",
          transform: "scale(calc(1 + var(--level) * 0.1))",
          animation: state === "idle" ? "orb-breathe 4.5s ease-in-out infinite" : undefined,
        }}
      />
    </div>
  );
}
