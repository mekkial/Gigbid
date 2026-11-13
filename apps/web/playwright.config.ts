import { defineConfig } from "@playwright/test";

// The e2e stack is fully offline: GigSim + API (deterministic LLM stand-ins) + the built web app.
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  retries: 0,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } }, testIgnore: /mobile\.spec\.ts/ },
    { name: "phone", use: { viewport: { width: 390, height: 844 } }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    { command: "cd ../.. && .venv/bin/python scripts/e2e_stack.py", url: "http://127.0.0.1:8100/health", timeout: 120_000, reuseExistingServer: true },
    { command: "API_URL=http://127.0.0.1:8100 npx vite --port 3100 --host 127.0.0.1", url: "http://127.0.0.1:3100", timeout: 60_000, reuseExistingServer: true },
  ],
});
