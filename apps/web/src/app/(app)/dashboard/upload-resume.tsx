"use client";

import { FileUpIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024; // mirrors the API limit, so users get instant feedback

export function UploadResume() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  async function upload(file: File) {
    if (file.type !== "application/pdf") return toast.error("Please choose a PDF file");
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
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file && !uploading) void upload(file);
      }}
      className={cn(
        "flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed bg-card/60 px-6 py-10 text-center transition-colors",
        dragging && "border-primary bg-accent",
      )}
    >
      <span className="grid size-12 place-items-center rounded-2xl bg-accent text-accent-foreground">
        <FileUpIcon className="size-6" aria-hidden />
      </span>
      <div>
        <p className="font-semibold">{uploading ? "Reading your resume…" : "Drop your resume here"}</p>
        <p className="mt-1 text-sm text-muted-foreground">Text-based PDF, up to 5 MB. This takes a few seconds.</p>
      </div>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        className="sr-only"
        aria-label="Resume PDF"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <Button className="rounded-full px-5" onClick={() => input.current?.click()} disabled={uploading}>
        {uploading ? "Please wait…" : "Choose PDF"}
      </Button>
    </div>
  );
}
