import type { NextConfig } from "next";

/** Where the browser may connect: our own API (HTTP and WebSocket), Supabase, and optional PostHog. */
function connectSources(): string[] {
  const hosts = [process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.NEXT_PUBLIC_API_URL].flatMap((raw) => {
    if (!raw) return [];
    const { host, protocol } = new URL(raw);
    return protocol === "https:" ? [`https://${host}`, `wss://${host}`] : [`http://${host}`, `ws://${host}`];
  });
  return ["'self'", ...hosts, ...posthogSources()];
}

/** PostHog (optional) fetches its own helper scripts and sends events; allowed only when a key is set. */
function posthogSources(): string[] {
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return [];
  const custom = process.env.NEXT_PUBLIC_POSTHOG_HOST;
  return ["https://*.posthog.com", ...(custom ? [custom] : [])];
}

// Content-Security-Policy (D40). Next.js ships small inline bootstrap scripts, so script-src needs
// 'unsafe-inline' (a nonce would make every page dynamic and defeat prerendering). What the policy
// still blocks is the dangerous part: scripts, frames, forms and connections to any other origin.
// 'wasm-unsafe-eval' is for the voice-detection model (onnxruntime WebAssembly), nothing else.
const isDev = process.env.NODE_ENV !== "production";
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' ${posthogSources().join(" ")}${isDev ? " 'unsafe-eval'" : ""}`.trim(),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:", // interviewer speech is decoded from blobs
  "worker-src 'self' blob:",
  `connect-src ${connectSources().join(" ")}`,
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

// Applied to every response (projectprep.md 5.13).
const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }, // ignored over plain http
  { key: "X-Frame-Options", value: "DENY" }, // no clickjacking: the app is never framed
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The mic is needed for interviews, on our own pages only; nothing else is.
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
