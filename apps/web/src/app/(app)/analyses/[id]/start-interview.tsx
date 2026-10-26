"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

export function StartInterview({ analysisId }: { analysisId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function start() {
    setPending(true);
    const { data, error } = await browserApi.POST("/interviews", { body: { analysis_id: analysisId } });
    if (error || !data) {
      setPending(false);
      return toast.error(errorMessage(error));
    }
    router.push(`/interviews/${data.id}`);
  }

  return (
    <Button size="lg" className="h-10 px-5" onClick={start} disabled={pending}>
      {pending ? "Setting up…" : "Start mock interview"}
    </Button>
  );
}
