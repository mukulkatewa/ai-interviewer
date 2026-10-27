/**
 * Shared setup for the end-to-end suite (projectprep.md 5.13).
 *
 * Needs the running stack (web, API, Kokoro) and these env vars, e.g. `set -a; source ../api/.env`:
 *   SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY (creates and deletes a test user)
 *   E2E_WEB_URL (default http://localhost:3000), E2E_API_URL (default http://localhost:8000)
 *   E2E_LOCAL_DB_URL: only when the API runs on a local Postgres, which has no Supabase auth
 *                     users; the test user's id is mirrored into its auth.users table.
 */
import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { type BrowserContext } from "@playwright/test";
import { createServerClient } from "@supabase/ssr";
import pg from "pg";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing ${name}. See apps/web/e2e/support.ts.`);
  return value;
}

export const WEB = process.env.E2E_WEB_URL ?? "http://localhost:3000";
export const API = process.env.E2E_API_URL ?? "http://localhost:8000";
export const FIXTURES = join(__dirname, "fixtures");

const SUPABASE_URL = required("SUPABASE_URL");
const PUBLISHABLE = required("SUPABASE_PUBLISHABLE_KEY");
const admin = () => {
  const secret = required("SUPABASE_SECRET_KEY");
  return { apikey: secret, Authorization: `Bearer ${secret}`, "Content-Type": "application/json" };
};

async function localDb<T>(fn: (db: pg.Client) => Promise<T>): Promise<T | undefined> {
  if (!process.env.E2E_LOCAL_DB_URL) return undefined;
  const db = new pg.Client({ connectionString: process.env.E2E_LOCAL_DB_URL });
  await db.connect();
  try {
    return await fn(db);
  } finally {
    await db.end();
  }
}

export type TestUser = { id: string; email: string; token: string; cookies: { name: string; value: string }[] };

/** A brand-new confirmed user, signed in exactly the way the app does (cookies via @supabase/ssr). */
export async function createUser(): Promise<TestUser> {
  const email = `e2e-${randomBytes(4).toString("hex")}@example.com`;
  const password = randomBytes(16).toString("base64url");
  const created = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: admin(),
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  if (!created.ok) throw new Error(`Creating test user failed: ${created.status}`);
  const { id } = (await created.json()) as { id: string };
  await localDb((db) => db.query("insert into auth.users values ($1)", [id]));

  const jar = new Map<string, string>();
  const supabase = createServerClient(SUPABASE_URL, PUBLISHABLE, {
    cookies: {
      getAll: () => [...jar].map(([name, value]) => ({ name, value })),
      setAll: (cookies) => cookies.forEach(({ name, value }) => jar.set(name, value)),
    },
  });
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error || !data.session) throw new Error(`Sign-in failed: ${error?.message}`);
  return { id, email, token: data.session.access_token, cookies: [...jar].map(([name, value]) => ({ name, value })) };
}

export async function deleteUser(user: TestUser): Promise<void> {
  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${user.id}`, { method: "DELETE", headers: admin() });
  await localDb((db) => db.query("delete from auth.users where id = $1", [user.id])); // cascades to all their rows
}

export async function signIn(context: BrowserContext, user: TestUser): Promise<void> {
  await context.addCookies(user.cookies.map((c) => ({ ...c, url: WEB })));
}

/** Seed through the API (fast, and the UI for these steps is covered by its own test). */
export async function createAnalysis(user: TestUser): Promise<{ resumeId: string; analysisId: string }> {
  const auth = { Authorization: `Bearer ${user.token}` };
  const form = new FormData();
  form.append("file", new Blob([readFileSync(join(FIXTURES, "resume.pdf"))], { type: "application/pdf" }), "resume.pdf");
  const resume = await fetch(`${API}/resumes`, { method: "POST", headers: auth, body: form });
  if (!resume.ok) throw new Error(`Upload failed: ${resume.status} ${await resume.text()}`);
  const { id: resumeId } = (await resume.json()) as { id: string };
  const analysis = await fetch(`${API}/analyses`, {
    method: "POST",
    headers: { ...auth, "Content-Type": "application/json" },
    body: JSON.stringify({ resume_id: resumeId, job_description: JOB_DESCRIPTION }),
  });
  if (!analysis.ok) throw new Error(`Analysis failed: ${analysis.status} ${await analysis.text()}`);
  return { resumeId, analysisId: ((await analysis.json()) as { id: string }).id };
}

export const JOB_DESCRIPTION =
  "Backend Engineer (SDE-1) - Razorpay, Bangalore. Requirements: Python or Go, PostgreSQL, Redis, " +
  "REST APIs, Docker. Good to have: Kubernetes, AWS, Kafka. You will own payment reconciliation services.";
