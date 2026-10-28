import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";

/** Reads the session, so it streams in behind Suspense: the header shell and
 *  the page's loading state render instantly without waiting on cookies. */
async function UserMenu() {
  // proxy.ts already redirects logged-out users; checking again here means a
  // matcher mistake can never expose these pages.
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect("/login");
  const email = typeof data.claims.email === "string" ? data.claims.email : null;

  return (
    <div className="flex items-center gap-3 text-sm">
      {email && <span className="hidden text-muted-foreground sm:inline">{email}</span>}
      <form action={signOut}>
        <Button type="submit" variant="ghost" size="sm">
          Sign out
        </Button>
      </form>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3.5">
          <Logo href="/dashboard" />
          <Suspense>
            <UserMenu />
          </Suspense>
        </div>
      </header>
      {/* Pages read the session too; (app)/loading.tsx is their Suspense boundary. */}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">{children}</main>
    </div>
  );
}
