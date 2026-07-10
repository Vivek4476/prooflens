import { defineConfig, devices } from "@playwright/test";

/**
 * Config for the e2e specs (analytics-overflow, mobile-nav-smoke). Chromium only
 * — no cross-browser matrix.
 *
 * `webServer` boots `next dev` on port 3000 so `npx playwright test` runs from
 * cold (e.g. in CI) with no manual server management. Locally it REUSES an
 * already-running dev server (`reuseExistingServer` when not in CI), so an
 * existing `npm run dev` is never restarted. The specs are data-independent or
 * mock the API (see analytics-overflow.spec.ts), so the backend API does not
 * need to be running — the pages render their chrome + heading regardless of
 * API state. Point at another instance with PLAYWRIGHT_BASE_URL.
 *
 * For a stricter CI you can swap the command to `npm run build && npm run start`
 * (add ~60s to the timeout) to avoid per-route dev compilation on first hit.
 */
const PORT = 3000;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    stdout: "pipe",
    stderr: "pipe",
  },
});
