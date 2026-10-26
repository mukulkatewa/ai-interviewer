import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { connection } from "next/server";

import { env } from "@/lib/env";

/** Supabase client for Server Components, Server Actions and Route Handlers.
 *  Create one per request: it is bound to that request's cookies. */
export async function createClient() {
  // Session checks compare the token's expiry with Date.now(). With Cache
  // Components, Next may prerender a per-session shell where cookies are
  // readable but the clock is not; connection() marks this as request-time work.
  await connection();
  const cookieStore = await cookies();

  return createServerClient(env.supabaseUrl, env.supabaseKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Server Components can't set cookies. Safe to ignore: proxy.ts
          // refreshes the session before any page renders (D20).
        }
      },
    },
  });
}
