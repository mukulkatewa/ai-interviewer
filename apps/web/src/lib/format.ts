const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** "27 Oct 2026". Fixed locale so server and browser render identical text (no hydration mismatch). */
export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso));
}
