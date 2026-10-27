# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: app.spec.ts >> full voice interview through to the feedback report @slow
- Location: e2e/app.spec.ts:58:5

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/interviews\/[^/]+$/
Received string:  "http://localhost:3000/analyses/340f5a20-00d4-4c6b-9a81-370be057d7be"
Timeout: 60000ms

Call log:
  - Expect "toHaveURL" with timeout 60000ms
    123 × locator resolved to <html lang="en" class="T19VSG_variable _8Li5zG_variable h-full antialiased">…</html>
        - unexpected value "http://localhost:3000/analyses/340f5a20-00d4-4c6b-9a81-370be057d7be"

```

```yaml
- banner:
  - link "Interviewer":
    - /url: /dashboard
  - text: e2e-b681b0d7@example.com
  - button "Sign out"
- main:
  - text: 39 match score
  - heading "Backend Engineer (SDE-1)" [level=1]
  - paragraph: Razorpay · 27 Oct 2026
  - paragraph: Rahul shows some relevant backend experience, especially with Docker and Redis, but lacks several core must‑have technologies such as Python/Go, PostgreSQL, and REST API design, resulting in a low overall fit. The resume also misses key nice‑to‑have skills like Kubernetes and Kafka, keeping the alignment with the Razorpay role modest.
  - button "Start mock interview"
  - link "View resume":
    - /url: /resumes/49c3b19f-7a63-4cdd-9efa-a6028a631be7
  - heading "Must-have skills 2/5" [level=2]
  - list:
    - listitem: Python / GoMissing
    - listitem: PostgreSQLMissing
    - listitem: RedisAdd to skills
    - listitem: REST APIsMissing
    - listitem: DockerAdd to skills
  - heading "Nice-to-have skills 1/3" [level=2]
  - list:
    - listitem: KubernetesMissing
    - listitem: AWSOn resume
    - listitem: KafkaMissing
  - heading "Strengths" [level=2]
  - list:
    - listitem: Containerized a reporting service using Docker, demonstrating deployment automation
    - listitem: Built a real‑time chat app with Redis pub/sub, showing experience with event‑driven backend systems
    - listitem: Optimized API performance by adding MongoDB indexes, indicating performance‑tuning skills
    - listitem: Listed AWS among skills, matching a nice‑to‑have requirement
  - heading "What to work on" [level=2]
  - list:
    - listitem:
      - paragraph: Python
      - paragraph: Complete a Python backend development course and add Python to the skills section
    - listitem:
      - paragraph: Go
      - paragraph: Finish a Go programming tutorial and list Go in the skills section
    - listitem:
      - paragraph: PostgreSQL
      - paragraph: Build a small project using PostgreSQL and add PostgreSQL to the skills list
    - listitem:
      - paragraph: REST APIs
      - paragraph: Create a RESTful API project and include REST APIs in the skills section
    - listitem:
      - paragraph: Redis
      - paragraph: Add Redis to the skills section to reflect its mention in the project
    - listitem:
      - paragraph: Docker
      - paragraph: Add Docker to the skills section to highlight containerization experience
    - listitem:
      - paragraph: Kubernetes
      - paragraph: Take a Kubernetes fundamentals course and list Kubernetes in the skills section
    - listitem:
      - paragraph: Kafka
      - paragraph: Develop a simple Kafka producer/consumer demo and add Kafka to the skills list
  - heading "Stronger resume bullets" [level=2]
  - paragraph: Replace any [placeholder] with your real numbers before using these.
  - list:
    - listitem:
      - paragraph: Built an internal dashboard in React used by 50+ ops staff
      - paragraph: Engineered a full‑stack dashboard using React and Node.js, serving 50+ operations staff and exposing RESTful endpoints for data retrieval
      - button "Copy"
      - paragraph: Emphasizes backend API work and aligns with the REST API requirement
    - listitem:
      - paragraph: Reduced API response time by 30% by adding MongoDB indexes
      - paragraph: Optimized backend API performance, cutting response times by 30% through strategic MongoDB indexing
      - button "Copy"
      - paragraph: Highlights API performance improvement, a key backend skill
    - listitem:
      - paragraph: Containerized the reporting service with Docker for staging
      - paragraph: Dockerized the reporting microservice, enabling rapid staging deployments and consistent environment replication
      - button "Copy"
      - paragraph: Shows Docker expertise, matching a must‑have
    - listitem:
      - paragraph: Reduced API response time by 30% by adding MongoDB indexes
      - paragraph: Implemented database indexing strategies that decreased API latency by 30%, improving overall system responsiveness
      - button "Copy"
      - paragraph: Reframes the achievement to focus on backend scalability and performance
- region "Notifications alt+T"
- alert
```

# Test source

```ts
  1  | /**
  2  |  * End-to-end: the real stack in a real browser (projectprep.md 5.13).
  3  |  * `npm run e2e` (all) or `npm run e2e -- --grep-invert @slow` (skip the ~10-minute interview).
  4  |  */
  5  | import { join } from "node:path";
  6  | 
  7  | import { expect, test } from "@playwright/test";
  8  | 
  9  | import { API, createAnalysis, createUser, deleteUser, FIXTURES, JOB_DESCRIPTION, signIn, type TestUser, WEB } from "./support";
  10 | 
  11 | let user: TestUser;
  12 | test.beforeEach(async () => {
  13 |   user = await createUser();
  14 | });
  15 | test.afterEach(async () => {
  16 |   await deleteUser(user);
  17 | });
  18 | 
  19 | test("logged-out visitors are sent to sign in, signed-in users skip it", async ({ page, context }) => {
  20 |   await page.goto("/dashboard");
  21 |   await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
  22 | 
  23 |   await signIn(context, user);
  24 |   await page.goto("/login");
  25 |   await expect(page).toHaveURL(/\/dashboard$/);
  26 | });
  27 | 
  28 | test("resume upload to job match report", async ({ page, context }) => {
  29 |   await signIn(context, user);
  30 |   await page.goto("/dashboard");
  31 | 
  32 |   await page.locator('input[type="file"]').setInputFiles(join(FIXTURES, "resume.pdf"));
  33 |   await expect(page).toHaveURL(/\/resumes\//, { timeout: 30_000 });
  34 |   await expect(page.getByRole("heading", { name: "Rahul Sharma" })).toBeVisible();
  35 | 
  36 |   await page.getByLabel("Match against a job").fill(JOB_DESCRIPTION);
  37 |   await page.getByRole("button", { name: "Analyze match" }).click();
  38 |   await expect(page).toHaveURL(/\/analyses\//, { timeout: 60_000 });
  39 |   await expect(page.getByText("Must-have skills")).toBeVisible();
  40 |   await expect(page.getByText("match score")).toBeVisible();
  41 | });
  42 | 
  43 | test("other users' data is invisible", async ({ page, context }) => {
  44 |   const { analysisId } = await createAnalysis(user);
  45 |   const other = await createUser();
  46 |   try {
  47 |     await signIn(context, other);
  48 |     const response = await page.goto(`/analyses/${analysisId}`);
  49 |     await expect(page.getByText("Not found")).toBeVisible();
  50 |     expect(response?.status()).not.toBe(500);
  51 |     const api = await fetch(`${API}/analyses/${analysisId}`, { headers: { Authorization: `Bearer ${other.token}` } });
  52 |     expect(api.status).toBe(404);
  53 |   } finally {
  54 |     await deleteUser(other);
  55 |   }
  56 | });
  57 | 
  58 | test("full voice interview through to the feedback report @slow", async ({ page, context }) => {
  59 |   test.setTimeout(20 * 60_000); // ~10 planned turns, each spoken by Kokoro and answered by the fake mic
  60 |   const { analysisId } = await createAnalysis(user);
  61 |   await signIn(context, user);
  62 | 
  63 |   await page.goto(`/analyses/${analysisId}`);
  64 |   await page.getByRole("button", { name: "Start mock interview" }).click();
> 65 |   await expect(page).toHaveURL(/\/interviews\/[^/]+$/, { timeout: 60_000 });
     |                      ^ Error: expect(page).toHaveURL(expected) failed
  66 |   await page.getByRole("button", { name: "Start interview" }).click();
  67 | 
  68 |   // The fake mic (playwright.config.ts) answers every question; silence ends each turn (D27).
  69 |   await expect(page.getByRole("button", { name: "Done answering" })).toBeVisible({ timeout: 90_000 });
  70 |   await expect(page.getByText("You", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  71 |   await expect(page.getByText("Interview complete")).toBeVisible({ timeout: 18 * 60_000 });
  72 | 
  73 |   await page.getByRole("link", { name: "View report" }).click();
  74 |   await expect(page.getByText("Competencies")).toBeVisible({ timeout: 3 * 60_000 }); // written by the job worker
  75 |   await expect(page.getByText("How you spoke")).toBeVisible();
  76 |   expect(page.url()).toContain(WEB);
  77 | });
  78 | 
```