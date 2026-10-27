"use client";

import { FileTextIcon, UploadIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { browserApi } from "@/lib/api/browser";
import { errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024; // mirrors the API limit, so users get instant feedback

/** Drop a PDF anywhere on the card, or click it. `prominent` is the first-time, centered version. */
export function UploadResume({ prominent = false }: { prominent?: boolean }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  async function upload(file: File) {
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      return toast.error("Upload a PDF file");
    }
    if (file.size > MAX_BYTES) return toast.error("That file is over 5 MB");

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
    <button
      type="button"
      disabled={uploading}
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) void upload(file);
      }}
      className={cn(
        "group flex w-full flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 text-center transition-colors",
        "hover:border-primary/60 hover:bg-accent/40 focus-visible:border-primary disabled:cursor-progress",
        prominent ? "py-16" : "py-8",
        dragging ? "border-primary bg-accent/60" : "border-border",
      )}
    >
      <span className="grid size-12 place-items-center rounded-full bg-accent text-accent-foreground transition-transform group-hover:scale-105">
        {uploading ? <FileTextIcon className="size-5 animate-pulse" aria-hidden /> : <UploadIcon className="size-5" aria-hidden />}
      </span>
      <span>
        <span className="block font-medium">
          {uploading ? "Reading your resume…" : dragging ? "Drop it here" : "Upload your resume"}
        </span>
        <span className="mt-0.5 block text-sm text-muted-foreground">
          {uploading ? "This takes a few seconds." : "Drag a PDF here or click to choose one. Up to 5 MB, text-based."}
        </span>
      </span>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        className="sr-only"
        tabIndex={-1}
        aria-label="Resume PDF"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
    </button>
  );
}
