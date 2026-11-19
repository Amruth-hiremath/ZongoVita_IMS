import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests for both web apps.
 *
 * The apps are built and served in production mode, because that is where the strict Content
 * Security Policy applies in full (no 'unsafe-inline' for styles, no 'unsafe-eval'): a screen
 * that only works under the development relaxations fails here.
 *
 * - tenant-web        the wireframe screens on sample data (IMS_SESSION_SOURCE=fixtures, :3200)
 * - platform-console  the Platform Console on sample data (IMS_CONSOLE_SESSION_SOURCE=fixtures, :3300)
 * - tenant-core       the Tenant Web App signed in to the real IMS Core (:3201)
 * - console-platform  the Platform Console signed in to the real Platform Service (:3301)
 *
 * tools/e2e_backend.py serves IMS Core on :8180 and the Platform Service on :8181 against the
 * ims-test database stack. That script wipes the test cluster first: do not run it alongside
 * pytest.
 *
 * Set IMS_E2E_REUSE=1 to run against servers you already have on these ports.
 */
const TENANT_PORT = 3200;
const TENANT_CORE_PORT = 3201;
const PLATFORM_PORT = 3300;
const CONSOLE_PLATFORM_PORT = 3301;
const CORE_PORT = 8180;
const reuse = process.env.IMS_E2E_REUSE === "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  // Each screen is rendered per request; more browsers than this mostly measure the test machine.
  workers: 4,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [
    { name: "tenant-web", testMatch: "tenant-*.spec.ts", use: { baseURL: `http://localhost:${TENANT_PORT}` } },
    { name: "platform-console", testMatch: "platform-*.spec.ts", use: { baseURL: `http://localhost:${PLATFORM_PORT}` } },
    {
      name: "core-setup",
      testMatch: "core.setup.ts",
      timeout: 120_000,
      use: { baseURL: `http://localhost:${TENANT_CORE_PORT}` },
    },
    {
      name: "tenant-core",
      testMatch: "core-*.spec.ts",
      dependencies: ["core-setup"],
      use: { baseURL: `http://localhost:${TENANT_CORE_PORT}` },
    },
    {
      name: "console-setup",
      testMatch: "console.setup.ts",
      timeout: 120_000,
      use: { baseURL: `http://localhost:${CONSOLE_PLATFORM_PORT}` },
    },
    {
      name: "console-platform",
      testMatch: "console-*.spec.ts",
      dependencies: ["console-setup"],
      use: { baseURL: `http://localhost:${CONSOLE_PLATFORM_PORT}` },
    },
  ],
  webServer: [
    {
      command: "uv run python tools/e2e_backend.py",
      url: `http://127.0.0.1:${CORE_PORT}/healthz`,
      reuseExistingServer: reuse,
      timeout: 300_000,
    },
    {
      // One build, served in both session modes (tools/e2e-servers.mjs).
      command: "npm run build -w @ims/tenant-web && node tools/e2e-servers.mjs tenant-web",
      url: `http://localhost:${TENANT_PORT}/login`,
      reuseExistingServer: reuse,
      timeout: 300_000,
    },
    {
      command: "npm run build -w @ims/platform-console && node tools/e2e-servers.mjs platform-console",
      url: `http://localhost:${PLATFORM_PORT}/overview`,
      reuseExistingServer: reuse,
      timeout: 300_000,
    },
  ],
});
