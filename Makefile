.PHONY: install init seed dev dev-backend dev-frontend test test-backend test-e2e lint typecheck build check

# Prefer a globally installed pnpm. A clean Node.js installation can fall back
# to npx while still running the repository-pinned pnpm version.
PNPM_BIN := $(shell command -v pnpm 2>/dev/null)
ifeq ($(PNPM_BIN),)
PNPM := npx --yes pnpm@11.19.0
else
PNPM := $(PNPM_BIN)
endif

install:
	cd backend && uv sync --dev
	cd frontend && $(PNPM) install

init:
	cd backend && uv run alembic upgrade head
	$(MAKE) seed

seed:
	cd backend && uv run python -m app.seed

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

lint:
	cd backend && uv run ruff check .
	cd frontend && $(PNPM) lint

typecheck:
	cd frontend && $(PNPM) typecheck

build:
	cd frontend && $(PNPM) build

check: lint typecheck test-backend build
