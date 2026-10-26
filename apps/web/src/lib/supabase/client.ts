import { createBrowserClient } from "@supabase/ssr";

import { env } from "@/lib/env";

/** Supabase client for Client Components. createBrowserClient returns a
 *  singleton in the browser, so calling this in many components is cheap. */
export function createClient() {
  return createBrowserClient(env.supabaseUrl, env.supabaseKey);
}
