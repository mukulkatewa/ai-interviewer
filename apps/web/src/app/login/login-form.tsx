"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { createClient } from "@/lib/supabase/client";

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

      <Button className="h-10 w-full" variant="outline" onClick={signInWithGoogle} disabled={pending}>
        Continue with Google
      </Button>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <Separator className="flex-1" />
        or
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
        <Button type="submit" className="h-10 w-full" disabled={pending}>
          Email me a sign-in link
        </Button>
      </form>
    </div>
  );
}
