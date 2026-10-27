

import { ButtonLink } from "@/components/button-link";

export default function NotFound() {
  return (
    <div className="rounded-xl border p-8 text-center">
      <h2 className="font-medium">Not found</h2>
      <p className="mt-1 text-sm text-muted-foreground">It may have been deleted, or it belongs to another account.</p>
      <ButtonLink className="mt-4" variant="outline" href="/dashboard">
        Back to dashboard
      </ButtonLink>
    </div>
  );
}
