"use client";

import { VoiceOrb } from "@/components/voice-orb";

// A gentle, never-repeating-looking wobble stands in for real audio on the landing page.
const demoLevel = () => 0.3 + 0.18 * Math.sin(Date.now() / 330) + 0.1 * Math.sin(Date.now() / 140);

/** The product's real moment: a question being spoken, and the quote-backed feedback that follows. */
export function HeroDemo() {
  return (
    <div className="relative mx-auto w-full max-w-md pb-14 lg:mx-0">
      <div className="dark overflow-hidden rounded-[1.75rem] border border-white/10 bg-[oklch(0.15_0.035_268)] px-6 pt-8 pb-24 text-center text-foreground shadow-2xl shadow-primary/20">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-3/4 bg-[radial-gradient(ellipse_at_50%_30%,oklch(0.27_0.09_268/0.55),transparent_65%)]" />
        <div className="relative">
          <VoiceOrb state="interviewer" getLevel={demoLevel} className="mx-auto w-36" />
          <p className="mt-6 text-sm font-medium text-muted-foreground">The interviewer is speaking</p>
          <p className="mx-auto mt-2 max-w-sm text-balance text-lg leading-snug">
            You cut API response time by 30%. How did you find the bottleneck before adding the index?
          </p>
        </div>
      </div>

      <figure className="absolute right-0 bottom-0 left-8 rounded-2xl border bg-card p-4 shadow-xl shadow-black/5 sm:left-14">
        <figcaption className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-medium">Technical depth</span>
          <span className="tabular-nums text-muted-foreground">4 of 5</span>
        </figcaption>
        <blockquote className="mt-2 border-l-2 border-primary/40 pl-3 text-sm text-muted-foreground italic">
          &ldquo;I ran EXPLAIN and saw a full collection scan, so I added a compound index.&rdquo;
        </blockquote>
        <p className="mt-2 text-xs text-muted-foreground">Quoted from your answer, checked against the transcript.</p>
      </figure>
    </div>
  );
}
