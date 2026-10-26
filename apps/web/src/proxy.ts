import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { env } from "@/lib/env";

// Pages that need a logged-in user. Everything else is public.
const PROTECTED = ["/dashboard", "/resumes", "/analyses", "/interviews"];

/**
 * Runs before every matched request (D20):
 *  1. Refreshes the Supabase session if the access token is about to expire,
 *     writing the new cookies to both the request (for this render) and the response.
 *  2. Redirects logged-out users away from protected pages, and logged-in users away from /login.
 */
export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(env.supabaseUrl, env.supabaseKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        // No-store headers: a CDN must never cache a response carrying someone's session.
        Object.entries(headers).forEach(([key, value]) => response.headers.set(key, value));
      },
    },
  });

  // getClaims verifies the JWT signature (locally, via cached JWKS); getSession
  // would trust whatever the cookie says.
  const { data } = await supabase.auth.getClaims();
  const loggedIn = Boolean(data?.claims);
  const { pathname, search } = request.nextUrl;

  if (!loggedIn && PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  if (loggedIn && pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  // Skip static assets and images: they never need a session.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
