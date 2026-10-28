"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { browserApi } from "@/lib/api/browser";
import { track } from "@/lib/analytics";
import { errorMessage } from "@/lib/api/client";

/**
 * Start an interview from a resume alone: the job description is optional (D36).
 * `compact` is the one-button version used in lists.
 */
export function StartInterviewNow({ resumeId, compact = false }: { resumeId: string; compact?: boolean }) {
  const router = useRouter();
  const [role, setRole] = useState("");
  const [pending, setPending] = useState(false);

  async function start(e?: React.FormEvent) {
    e?.preventDefault();
    setPending(true);
    const { data, error } = await browserApi.POST("/interviews", {
      body: { resume_id: resumeId, target_role: role.trim() || null },
    });
    if (error || !data) {
      setPending(false);
      return toast.error(errorMessage(error));
    }
    track("interview_started_from_resume");
    router.push(`/interviews/${data.id}`); // stay disabled through navigation: no double submit
  }

  if (compact) {
    return (
      <Button size="sm" className="rounded-full" onClick={() => start()} disabled={pending}>
        {pending ? "Setting up…" : "Practice now"}
      </Button>
    );
  }

  return (
    <form onSubmit={start} className="space-y-4 rounded-2xl border bg-card p-5 shadow-sm">
      <div>
        <h2 className="text-base font-semibold">Practice an interview now</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          No job description needed. Questions come from your resume.
        </p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="role">Role you are practicing for (optional)</Label>
        <Input
          id="role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          maxLength={120}
          placeholder="e.g. Backend Engineer"
        />
      </div>
      <Button type="submit" size="lg" className="h-11 w-full rounded-full" disabled={pending}>
        {pending ? "Setting up your interview… (about 10 seconds)" : "Start interview"}
      </Button>
    </form>
  );
}
