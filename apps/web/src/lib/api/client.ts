// Typed client for the FastAPI backend (D21). Types come from `npm run gen:api`.

import createFetchClient, { type Middleware } from "openapi-fetch";

import { env } from "@/lib/env";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type ApiClient = ReturnType<typeof createApiClient>;

/** `getToken` runs before every request, so a refreshed session is always used. */
export function createApiClient(getToken: () => Promise<string | null>) {
  const client = createFetchClient<paths>({ baseUrl: env.apiUrl });

  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  client.use(auth);
  return client;
}

/** Turn a FastAPI error body into one human-readable sentence. */
export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  // 422 validation errors: a list of {msg, loc}.
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  return fallback;
}
