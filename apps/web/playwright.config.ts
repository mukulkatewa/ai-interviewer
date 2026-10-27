import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

// End-to-end suite against the running stack (e2e/support.ts lists the env it needs).
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1, // tests share one API and one Groq rate limit
  timeout: 3 * 60_000,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_WEB_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    permissions: ["microphone"],
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          // Chrome's fake mic plays this file in a loop: a spoken answer between silences.
          args: [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            `--use-file-for-fake-audio-capture=${join(__dirname, "e2e", "fixtures", "answer.wav")}`,
          ],
          executablePath: process.env.E2E_CHROMIUM_PATH, // optional: reuse an installed Chromium
        },
      },
    },
  ],
});
