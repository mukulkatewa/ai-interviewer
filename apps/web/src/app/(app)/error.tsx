"use client";

import { Button } from "@/components/ui/button";

export default function AppError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="rounded-xl border p-8 text-center" role="alert">
      <h2 className="font-medium">Something went wrong</h2>
      <p className="mt-1 text-sm text-muted-foreground">Our server may be waking up. Give it a moment.</p>
      <Button className="mt-4" variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
