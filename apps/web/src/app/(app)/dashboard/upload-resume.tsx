"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";

const MAX_BYTES = 5 * 1024 * 1024; // mirrors the API limit, so users get instant feedback

export function UploadResume() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(file: File) {
    if (file.size > MAX_BYTES) return toast.error("File too large (max 5 MB)");

    setUploading(true);
    // Straight to FastAPI, not through Next.js: Vercel caps request bodies at 4.5 MB (D19).
    const { data, error } = await browserApi.POST("/resumes", {
      // The generated type says `string` for binary fields; the real value is the File.
      body: { file: file as unknown as string },
      bodySerializer: ({ file }) => {
        const form = new FormData();
        form.append("file", file as unknown as File);
        return form;
      },
    });
    setUploading(false);
    if (input.current) input.current.value = ""; // allow re-selecting the same file

    if (error || !data) return toast.error(errorMessage(error));
    router.push(`/resumes/${data.id}`);
  }

  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-6 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-medium">Upload a resume</p>
        <p className="text-sm text-muted-foreground">Text-based PDF, up to 5 MB. Reading it takes a few seconds.</p>
      </div>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        className="sr-only"
        aria-label="Resume PDF"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <Button onClick={() => input.current?.click()} disabled={uploading}>
        {uploading ? "Reading your resume…" : "Choose PDF"}
      </Button>
    </div>
  );
}
