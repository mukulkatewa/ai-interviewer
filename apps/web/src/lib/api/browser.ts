"use client";

import { createClient } from "@/lib/supabase/client";
import { createApiClient } from "./client";

const supabase = createClient();

/** API client for Client Components. The token is read per request, so the
 *  browser client's automatic refresh is always picked up. */
export const browserApi = createApiClient(async () => {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
});
