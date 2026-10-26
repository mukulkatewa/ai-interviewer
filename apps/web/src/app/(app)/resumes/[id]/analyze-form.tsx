"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

const MIN_CHARS = 50; // mirrors AnalyzeRequest.job_description min_length

export function AnalyzeForm({ resumeId }: { resumeId: string }) {
  const router = useRouter();
  const [jd, setJd] = useState("");
  const [pending, setPending] = useState(false);
  const tooShort = jd.trim().length < MIN_CHARS;

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    const { data, error } = await browserApi.POST("/analyses", {
      body: { resume_id: resumeId, job_description: jd },
    });
    if (error || !data) {
      setPending(false);
      return toast.error(errorMessage(error));
    }
    // Keep the button disabled through navigation so it can't be double-submitted.
    router.push(`/analyses/${data.id}`);
  }

  return (
    <form onSubmit={analyze} className="space-y-3 rounded-xl border bg-card p-5">
      <div className="space-y-1">
        <Label htmlFor="jd" className="text-base">
          Match against a job
        </Label>
        <p className="text-sm text-muted-foreground">Paste the full job description.</p>
      </div>
      <Textarea
        id="jd"
        value={jd}
        onChange={(e) => setJd(e.target.value)}
        rows={12}
        maxLength={20_000}
        placeholder="We're hiring a Backend Engineer…"
        className="resize-y"
      />
      <Button type="submit" className="h-10 w-full" disabled={pending || tooShort}>
        {pending ? "Analyzing… (about 5 seconds)" : "Analyze match"}
      </Button>
    </form>
  );
}
