import { cn } from "@/lib/utils";

/** Score bands shared by the badge and the ring so colors always agree. */
export function scoreTone(score: number | null | undefined) {
  if (score == null) return "text-muted-foreground";
  if (score >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
}

export function ScoreBadge({ score }: { score: number | null | undefined }) {
  return (
    <span className={cn("font-mono text-sm font-semibold tabular-nums", scoreTone(score))}>
      {score == null ? "n/a" : `${score}%`}
    </span>
  );
}
