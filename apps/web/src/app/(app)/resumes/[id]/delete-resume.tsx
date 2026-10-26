"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

export function DeleteResume({ resumeId }: { resumeId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function remove() {
    if (!window.confirm("Delete this resume and all its job match reports? This can't be undone.")) return;
    setPending(true);
    const { error, response } = await browserApi.DELETE("/resumes/{resume_id}", {
      params: { path: { resume_id: resumeId } },
    });
    if (!response.ok) {
      setPending(false);
      return toast.error(errorMessage(error));
    }
    toast.success("Resume deleted");
    router.replace("/dashboard");
    router.refresh(); // drop the cached dashboard that still lists it
  }

  return (
    <Button variant="destructive" size="sm" onClick={remove} disabled={pending}>
      Delete resume
    </Button>
  );
}
