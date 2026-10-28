/**
 * When should the interview page reconnect by itself? (D43) Pure functions, so the rules are unit-tested
 * without a browser (`npm run test:unit`).
 */

// Closes that mean "the server went away", not "you may not be here":
// 1001 going away, 1006 abnormal (a dropped connection, or the API restarting behind the proxy),
// 1011 server error, 1012 service restart (sent on every deploy).
// Not retried: 4401 session expired, 4404 not yours, 4409 another tab, 1013 server full (retrying makes it worse).
const RETRYABLE = new Set([1001, 1006, 1011, 1012]);

/** Waits between attempts: about 30 s in total, longer than a deploy takes. */
export const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 15000] as const;

/** Milliseconds to wait before the next attempt, or undefined to give up and show the problem. */
export function reconnectDelay(closeCode: number, attempt: number, wrappingUp: boolean): number | undefined {
  if (wrappingUp || !RETRYABLE.has(closeCode)) return undefined; // asked to end: an ended socket is the goal
  return RECONNECT_DELAYS_MS[attempt]; // undefined once the attempts are used up
}
