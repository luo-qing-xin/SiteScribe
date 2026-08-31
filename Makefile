.PHONY: install install-test init migrate seed demo-init demo-reset demo-backend demo-frontend dev dev-backend dev-frontend test test-backend test-e2e evaluate-event lint typecheck build check

# Prefer a globally installed pnpm. A clean Node.js installation can fall back
# to npx while still running the repository-pinned pnpm version.
PNPM_BIN := $(shell command -v pnpm 2>/dev/null)
ifeq ($(PNPM_BIN),)
PNPM := npx --yes pnpm@11.19.0
else
PNPM := $(PNPM_BIN)
endif

install:
	cd backend && uv sync --dev --extra asr
	cd frontend && $(PNPM) install

install-test:
	cd backend && uv sync --dev
	cd frontend && $(PNPM) install

init:
	$(MAKE) migrate
	$(MAKE) seed

migrate:
	cd backend && uv run alembic upgrade head
	cd backend && uv run alembic current

seed:
	cd backend && uv run python -m app.seed

demo-init:
	cd backend && DATABASE_URL=sqlite:///data/site_secretary_demo.db UPLOAD_DIR=data/uploads KNOWLEDGE_DIR=data/knowledge ASR_PROVIDER=mock EVENT_EXTRACTION_PROVIDER=mock AI_PROVIDER=mock RAG_PROVIDER=mock uv run alembic upgrade head
	cd backend && DATABASE_URL=sqlite:///data/site_secretary_demo.db UPLOAD_DIR=data/uploads KNOWLEDGE_DIR=data/knowledge ASR_PROVIDER=mock EVENT_EXTRACTION_PROVIDER=mock AI_PROVIDER=mock RAG_PROVIDER=mock uv run python -m app.seed
	cd backend && DATABASE_URL=sqlite:///data/site_secretary_demo.db UPLOAD_DIR=data/uploads KNOWLEDGE_DIR=data/knowledge ASR_PROVIDER=mock EVENT_EXTRACTION_PROVIDER=mock AI_PROVIDER=mock RAG_PROVIDER=mock uv run python -m scripts.prepare_competition_demo

demo-reset:
	cd backend && uv run python scripts/reset_competition_demo.py
	$(MAKE) demo-init

demo-backend:
	cd backend && DATABASE_URL=sqlite:///data/site_secretary_demo.db UPLOAD_DIR=data/uploads KNOWLEDGE_DIR=data/knowledge ASR_PROVIDER=mock EVENT_EXTRACTION_PROVIDER=mock AI_PROVIDER=mock RAG_PROVIDER=mock uv run uvicorn app.main:app --reload --port 8000

demo-frontend:
	cd frontend && $(PNPM) dev

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && $(PNPM) dev

dev:
	@echo "请在两个终端分别运行 make dev-backend 和 make dev-frontend"

test: test-backend

test-backend:
	cd backend && uv run pytest

test-e2e:
	cd frontend && $(PNPM) exec playwright install chromium && $(PNPM) test:e2e

evaluate-event:
	cd backend && uv run python scripts/evaluate_event_extraction.py --output /tmp/site-event-evaluation.json

lint:
	cd backend && uv run ruff check .
	cd frontend && $(PNPM) lint

typecheck:
	cd frontend && $(PNPM) typecheck

build:
	cd frontend && $(PNPM) build

check: lint typecheck test-backend build
