import "server-only";

import { notFound, redirect } from "next/navigation";
import { cache } from "react";

import { createClient } from "@/lib/supabase/server";
import { createApiClient } from "./client";

/** API client for Server Components, authenticated as the current user.
 *  `cache` makes it one client per request, however many components ask. */
export const getServerApi = cache(async () => {
  const supabase = await createClient();
  // getSession just reads the cookie. That's fine here: we only forward the
  // token, and FastAPI verifies its signature before trusting it (D16).
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) redirect("/login");

  const token = session.access_token;
  return createApiClient(async () => token);
});

/** Unwrap an API result in a Server Component: 404 → not-found page,
 *  401 → login, anything else → nearest error.tsx. */
export function unwrap<T>({ data, response }: { data?: T; response: Response }): T {
  if (data !== undefined) return data;
  if (response.status === 404) notFound();
  if (response.status === 401) redirect("/login");
  throw new Error(`API request failed with status ${response.status}`);
}
