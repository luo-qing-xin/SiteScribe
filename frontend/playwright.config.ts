import { defineConfig, devices } from "@playwright/test";

const localChannel = process.env.PLAYWRIGHT_CHANNEL as "chrome" | undefined;

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  fullyParallel: false,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", ...(localChannel ? { channel: localChannel } : {}), ...devices["Desktop Chrome"] },
  webServer: [
    { command: "UV_CACHE_DIR=/private/tmp/sitescribe-uv-cache uv run alembic upgrade head && UV_CACHE_DIR=/private/tmp/sitescribe-uv-cache uv run python -m app.seed && UV_CACHE_DIR=/private/tmp/sitescribe-uv-cache uv run uvicorn app.main:app --port 8000", cwd: "../backend", url: "http://localhost:8000/api/health", reuseExistingServer: true, timeout: 120_000 },
    { command: "./node_modules/.bin/next dev", cwd: ".", url: "http://localhost:3000/login", reuseExistingServer: true, timeout: 120_000 },
  ],
});
