"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

/** Deletes every resume, report and interview of this user (projectprep.md 5.13). */
export function DeleteMyData() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function remove() {
    if (!window.confirm("Delete all your resumes, job match reports and interviews? This can't be undone.")) return;
    setPending(true);
    const { error, response } = await browserApi.DELETE("/me/data");
    setPending(false);
    if (!response.ok) return toast.error(errorMessage(error));
    toast.success("All your data was deleted");
    router.refresh();
  }

  return (
    <section className="space-y-2 border-t pt-6">
      <h2 className="text-sm font-medium text-muted-foreground">Your data</h2>
      <p className="text-sm text-muted-foreground">
        Delete everything you&apos;ve uploaded or recorded. Your sign-in stays, so you can start fresh.
      </p>
      <Button variant="destructive" size="sm" onClick={remove} disabled={pending}>
        {pending ? "Deleting…" : "Delete all my data"}
      </Button>
    </section>
  );
}
