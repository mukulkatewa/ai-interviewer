"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { track } from "@/lib/analytics";
import { errorMessage } from "@/lib/api/client";

const MIN_CHARS = 50; // mirrors AnalyzeRequest.job_description min_length

export function AnalyzeForm({ resumeId }: { resumeId: string }) {
  const router = useRouter();
  const [jd, setJd] = useState("");
  const [pending, setPending] = useState(false);
  const length = jd.trim().length;
  const tooShort = length < MIN_CHARS;
  // A disabled button alone looks broken: say what is missing, and catch the common mistake of pasting a link.
  const hint = /^https?:\/\/\S+$/.test(jd.trim())
    ? "That's a link. Copy the job description text from the page and paste it here."
    : length === 0
      ? `Paste the job description text (at least ${MIN_CHARS} characters).`
      : tooShort
        ? `A little more, please: ${MIN_CHARS - length} more characters needed.`
        : null;

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
    track("analysis_created", { score: data.match.score ?? -1 });
    // Keep the button disabled through navigation so it can't be double-submitted.
    router.push(`/analyses/${data.id}`);
  }

  return (
    <form onSubmit={analyze} className="space-y-3 rounded-2xl border bg-card p-5 shadow-sm">
      <div className="space-y-1">
        <Label htmlFor="jd" className="text-base">
          Match against a job (optional)
        </Label>
        <p className="text-sm text-muted-foreground">
          Paste a job description to see your match score, then practice for that role.
        </p>
      </div>
      <Textarea
        id="jd"
        value={jd}
        onChange={(e) => setJd(e.target.value)}
        rows={8}
        maxLength={20_000}
        placeholder="We're hiring a Backend Engineer…"
        className="resize-y"
        aria-describedby="jd-hint"
      />
      <p id="jd-hint" className="min-h-5 text-sm text-muted-foreground" aria-live="polite">
        {hint}
      </p>
      <Button type="submit" variant="outline" className="h-10 w-full" disabled={pending || tooShort || hint !== null}>
        {pending ? "Analyzing… (about 5 seconds)" : "Analyze match"}
      </Button>
    </form>
  );
}
