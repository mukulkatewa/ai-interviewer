/**
 * End-to-end: the real stack in a real browser (projectprep.md 5.13).
 * `npm run e2e` (all) or `npm run e2e -- --grep-invert @slow` (skip the ~10-minute interview).
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { API, createAnalysis, createUser, deleteUser, FIXTURES, JOB_DESCRIPTION, signIn, type TestUser, WEB } from "./support";

let user: TestUser;
test.beforeEach(async () => {
  user = await createUser();
});
test.afterEach(async () => {
  await deleteUser(user);
});

test("logged-out visitors are sent to sign in, signed-in users skip it", async ({ page, context }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);

  await signIn(context, user);
  await page.goto("/login");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("resume upload to job match report", async ({ page, context }) => {
  await signIn(context, user);
  await page.goto("/dashboard");

  await page.locator('input[type="file"]').setInputFiles(join(FIXTURES, "resume.pdf"));
  await expect(page).toHaveURL(/\/resumes\//, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Rahul Sharma" })).toBeVisible();

  await page.getByLabel("Match against a job").fill(JOB_DESCRIPTION);
  await page.getByRole("button", { name: "Analyze match" }).click();
  await expect(page).toHaveURL(/\/analyses\//, { timeout: 60_000 });
  await expect(page.getByText("Must-have skills")).toBeVisible();
  await expect(page.getByText("match score")).toBeVisible();
});

test("other users' data is invisible", async ({ page, context }) => {
  const { analysisId } = await createAnalysis(user);
  const other = await createUser();
  try {
    await signIn(context, other);
    const response = await page.goto(`/analyses/${analysisId}`);
    await expect(page.getByText("Not found")).toBeVisible();
    expect(response?.status()).not.toBe(500);
    const api = await fetch(`${API}/analyses/${analysisId}`, { headers: { Authorization: `Bearer ${other.token}` } });
    expect(api.status).toBe(404);
  } finally {
    await deleteUser(other);
  }
});

test("End interview works on the first click, even while the interviewer is speaking", async ({ page, context }) => {
  // Regression: the server used to read "end" only after the interviewer finished speaking, and a stale
  // "your turn" then put the screen back into listening mode, so the first click looked broken (D33).
  const { analysisId } = await createAnalysis(user);
  await signIn(context, user);
  // The Content-Security-Policy (D40) must not block anything the interview needs: mic, voice model, audio, sockets.
  const blocked: string[] = [];
  page.on("console", (m) => /content security policy|refused to/i.test(m.text()) && blocked.push(m.text()));

  await page.goto(`/analyses/${analysisId}`);
  await page.getByRole("button", { name: "Start mock interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[^/]+$/, { timeout: 60_000 });
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText("Interviewer is speaking")).toBeVisible({ timeout: 30_000 });

  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "End interview" }).click();
  await expect(page.getByText("Interview complete")).toBeVisible({ timeout: 15_000 });

  await page.waitForTimeout(4_000); // a stale "your turn" would have reappeared by now
  await expect(page.getByRole("button", { name: "Done answering" })).toBeHidden();
  expect(blocked).toEqual([]);
});

test("full voice interview through to the feedback report @slow", async ({ page, context }) => {
  test.setTimeout(20 * 60_000); // ~10 planned turns, each spoken by Kokoro and answered by the fake mic
  const { analysisId } = await createAnalysis(user);
  await signIn(context, user);

  await page.goto(`/analyses/${analysisId}`);
  await page.getByRole("button", { name: "Start mock interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[^/]+$/, { timeout: 60_000 });
  await page.getByRole("button", { name: "Start interview" }).click();

  // The fake mic (playwright.config.ts) answers every question; silence ends each turn (D27).
  await expect(page.getByRole("button", { name: "Done answering" })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("You", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("Interview complete")).toBeVisible({ timeout: 18 * 60_000 });

  await page.getByRole("link", { name: "View report" }).click();
  await expect(page.getByText("Competencies")).toBeVisible({ timeout: 3 * 60_000 }); // written by the job worker
  await expect(page.getByText("How you spoke")).toBeVisible();
  expect(page.url()).toContain(WEB);
});
