import type { Metadata } from "next";
import { Suspense } from "react";

import { Logo } from "@/components/logo";
import { Skeleton } from "@/components/ui/skeleton";
import { safeNext } from "@/lib/safe-next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

/** searchParams are per-request, so the form streams in; the heading is static shell. */
async function LoginFormFromParams({ searchParams }: Pick<PageProps<"/login">, "searchParams">) {
  const { next, error } = await searchParams;
  return <LoginForm next={safeNext(typeof next === "string" ? next : null)} failed={error !== undefined} />;
}

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <main className="bg-glow flex flex-1 flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm rounded-3xl border bg-card p-8 shadow-xl shadow-primary/5">
        <Logo />
        <h1 className="mt-8 text-2xl font-bold tracking-tight">Sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">Your resumes and reports are private to your account.</p>
        <Suspense fallback={<Skeleton className="mt-8 h-52 w-full" />}>
          <LoginFormFromParams searchParams={searchParams} />
        </Suspense>
      </div>
    </main>
  );
}
