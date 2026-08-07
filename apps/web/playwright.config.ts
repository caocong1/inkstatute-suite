import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E test configuration for @inkstatute/web.
 *
 * Two projects:
 * - desktop-chromium: Desktop Chrome (1280×720)
 * - mobile-iphone: iPhone 13 (390×844)
 *
 * The webServer auto-starts the Vite dev server on port 5173.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-iphone",
      use: { ...devices["iPhone 13"] },
    },
  ],
  webServer: {
    command: "npx vite dev --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
