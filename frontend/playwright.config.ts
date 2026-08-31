import { defineConfig, devices } from "@playwright/test";

const localChannel = process.env.PLAYWRIGHT_CHANNEL as "chrome" | undefined;
const e2eDatabase = `sqlite:////private/tmp/sitescribe-e2e-${process.pid}.db`;
const e2eRoot = `/private/tmp/sitescribe-e2e-data-${process.pid}`;
const e2eUploads = `${e2eRoot}/uploads`;
const e2eKnowledge = `${e2eRoot}/knowledge`;
const backendEnvironment = `DATABASE_URL=${e2eDatabase} UPLOAD_DIR=${e2eUploads} KNOWLEDGE_DIR=${e2eKnowledge} ASR_PROVIDER=mock EVENT_EXTRACTION_PROVIDER=mock AI_PROVIDER=mock RAG_PROVIDER=mock FRONTEND_ORIGIN=http://localhost:3100 UV_CACHE_DIR=/private/tmp/sitescribe-uv-cache`;

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", ...(localChannel ? { channel: localChannel } : {}), ...devices["Desktop Chrome"] },
  webServer: [
    { command: `${backendEnvironment} uv run alembic upgrade head && ${backendEnvironment} uv run python -m app.seed && ${backendEnvironment} uv run uvicorn app.main:app --port 8100`, cwd: "../backend", url: "http://localhost:8100/api/health", reuseExistingServer: false, timeout: 120_000 },
    { command: "BACKEND_URL=http://127.0.0.1:8100 ./node_modules/.bin/next dev -p 3100", cwd: ".", url: "http://127.0.0.1:3100/login", reuseExistingServer: true, timeout: 120_000 },
  ],
});
