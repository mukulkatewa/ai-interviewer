"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

const POLL_MS = 3000;
const GIVE_UP_MS = 3 * 60_000; // jobs normally take 5-15 s; past this something is wrong

/** While the report job runs: re-render the server page every few seconds until it's ready. */
export function ReportPending() {
  const router = useRouter();
  const [startedAt] = useState(() => Date.now());
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      if (Date.now() - startedAt > GIVE_UP_MS) {
        setSlow(true);
        clearInterval(timer);
        return;
      }
      router.refresh(); // re-runs the Server Component, which re-fetches the report
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [router, startedAt]);

  return (
    <div className="rounded-2xl border bg-card px-6 py-12 text-center" role="status" aria-live="polite">
      <div className="mx-auto size-10 animate-spin rounded-full border-4 border-primary/20 border-t-primary" aria-hidden />
      <p className="mt-4 font-medium">Writing your feedback report…</p>
      <p className="mt-1 text-sm text-muted-foreground">
        {slow ? "This is taking longer than usual. Our AI may be at capacity; check back in a few minutes." : "Usually under a minute."}
      </p>
    </div>
  );
}

/** The report job failed for good: let the user queue it again. */
export function ReportFailed({ interviewId }: { interviewId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function retry() {
    setPending(true);
    const { error, response } = await browserApi.POST("/interviews/{interview_id}/report/retry", {
      params: { path: { interview_id: interviewId } },
    });
    if (!response.ok) {
      setPending(false);
      return toast.error(errorMessage(error));
    }
    router.refresh();
  }

  return (
    <div className="rounded-2xl border bg-card px-6 py-12 text-center">
      <p className="font-medium">We couldn&apos;t write your report</p>
      <p className="mt-1 text-sm text-muted-foreground">Your answers are saved. Trying again usually works.</p>
      <Button className="mt-4" onClick={retry} disabled={pending}>
        {pending ? "Retrying…" : "Try again"}
      </Button>
    </div>
  );
}
