"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { createClient } from "@/lib/supabase/client";

/** Google's four-color "G". Inline so there is no image request; the colors are Google's brand colors. */
function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

export function LoginForm({ next, failed }: { next: string; failed: boolean }) {
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  // Both flows come back through /auth/callback, which swaps the one-time code for a session.
  const callbackUrl = () => `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;

  function signInWithGoogle() {
    startTransition(async () => {
      const { error } = await createClient().auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: callbackUrl() },
      });
      // On success the browser is already navigating to Google.
      if (error) toast.error(error.message);
    });
  }

  function sendMagicLink(e: React.FormEvent) {
    e.preventDefault();
    startTransition(async () => {
      const { error } = await createClient().auth.signInWithOtp({
        email,
        options: { emailRedirectTo: callbackUrl() },
      });
      if (error) toast.error(error.message);
      else setSentTo(email);
    });
  }

  if (sentTo) {
    return (
      <p className="mt-8 rounded-lg border bg-muted/50 p-4 text-sm" role="status">
        Check <span className="font-medium">{sentTo}</span> for a sign-in link.
      </p>
    );
  }

  return (
    <div className="mt-8 space-y-6">
      {failed && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          That sign-in link didn&apos;t work. It may have expired, so try again.
        </p>
      )}

      <Button
        className="h-12 w-full gap-3 rounded-full border-border bg-card text-base font-medium shadow-sm hover:bg-muted"
        variant="outline"
        onClick={signInWithGoogle}
        disabled={pending}
      >
        <GoogleMark />
        Continue with Google
      </Button>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <Separator className="flex-1" />
        or use email
        <Separator className="flex-1" />
      </div>

      <form onSubmit={sendMagicLink} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="h-10"
          />
        </div>
        <Button type="submit" variant="ghost" className="h-10 w-full text-muted-foreground" disabled={pending}>
          Email me a sign-in link
        </Button>
      </form>
    </div>
  );
}
