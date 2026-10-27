import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";

/** Reads the session, so it streams in behind Suspense: the header shell and
 *  the page's loading state render instantly without waiting on cookies. */
async function Account() {
  // proxy.ts already redirects logged-out users; checking again here means a
  // matcher mistake can never expose these pages.
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect("/login");
  const email = typeof data.claims.email === "string" ? data.claims.email : null;
  return <UserMenu email={email} signOut={signOut} />;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between gap-4 px-4">
          <Logo href="/dashboard" />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Suspense fallback={<span className="size-9" aria-hidden />}>
              <Account />
            </Suspense>
          </div>
        </div>
      </header>
      {/* Pages read the session too; (app)/loading.tsx is their Suspense boundary. */}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  );
}
