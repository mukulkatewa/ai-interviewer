"use client";

/**
 * Optional product analytics (projectprep.md 5.13).
 *
 * With no NEXT_PUBLIC_POSTHOG_KEY nothing is loaded: posthog-js is a dynamic
 * import, so it isn't even in the bundle that browsers download by default.
 * Visitors stay anonymous (no email or name is ever sent) and autocapture is off.
 */
import type { PostHog } from "posthog-js";

type Event = "analysis_created" | "interview_started" | "interview_completed" | "report_viewed";

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";

let client: Promise<PostHog> | null = null;

function load(): Promise<PostHog> | null {
  if (!KEY) return null;
  client ??= import("posthog-js").then(({ default: posthog }) => {
    posthog.init(KEY, {
      api_host: HOST,
      autocapture: false, // only the events below: no accidental capture of form text
      capture_pageview: "history_change", // page views for client-side navigation too
      person_profiles: "identified_only", // we never identify, so everyone stays anonymous
      disable_session_recording: true,
    });
    return posthog;
  });
  return client;
}

export function initAnalytics(): void {
  void load();
}

export function track(event: Event, properties?: Record<string, string | number>): void {
  void load()?.then((posthog) => posthog.capture(event, properties));
}
