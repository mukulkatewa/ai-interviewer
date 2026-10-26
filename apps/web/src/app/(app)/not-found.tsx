import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="rounded-xl border p-8 text-center">
      <h2 className="font-medium">Not found</h2>
      <p className="mt-1 text-sm text-muted-foreground">It may have been deleted, or it belongs to another account.</p>
      <Button className="mt-4" variant="outline" nativeButton={false} render={<Link href="/dashboard" />}>
        Back to dashboard
      </Button>
    </div>
  );
}
