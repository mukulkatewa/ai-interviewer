import { cn } from "@/lib/utils";
import { scoreTone } from "./score-badge";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Circular 0–100 gauge. Pure SVG, so it renders on the server with no JS. */
export function ScoreRing({ score, label = "match score" }: { score: number | null; label?: string }) {
  const filled = score == null ? 0 : (score / 100) * CIRCUMFERENCE;

  return (
    <div className={cn("relative size-32 shrink-0", scoreTone(score))}>
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="10" className="stroke-muted" />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          stroke="currentColor"
          strokeDasharray={`${filled} ${CIRCUMFERENCE}`}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <span>
          <span className="block text-3xl font-semibold tabular-nums">{score ?? "n/a"}</span>
          <span className="block text-xs text-muted-foreground">{label}</span>
        </span>
      </div>
    </div>
  );
}
