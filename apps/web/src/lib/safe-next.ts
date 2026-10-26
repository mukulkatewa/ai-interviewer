/** Only allow same-site relative paths as post-login redirects.
 *  "//evil.com" and "https://evil.com" would otherwise make /login an open redirect. */
export function safeNext(next: string | null | undefined, fallback = "/dashboard"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}
