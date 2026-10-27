"use client";

import { useEffect } from "react";

import { initAnalytics, track } from "@/lib/analytics";

/** Mounted once in the root layout; a no-op without a PostHog key. */
export function Analytics() {
  useEffect(() => {
    initAnalytics();
  }, []);
  return null;
}

/** Fire one event when a server-rendered page is shown (e.g. a finished report). */
export function TrackOnMount({ event }: { event: Parameters<typeof track>[0] }) {
  useEffect(() => {
    track(event);
  }, [event]);
  return null;
}
