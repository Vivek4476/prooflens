import { defineConfig, devices } from "@playwright/test";

/**
 * Minimal config for internal audit / diagnosis specs (e.g. analytics-overflow).
 * No cross-browser matrix — chromium only. Assumes `npm run dev` (or an
 * equivalent server) is already running at PLAYWRIGHT_BASE_URL; this config does
 * not spawn a server itself so it can be pointed at any already-running instance.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
