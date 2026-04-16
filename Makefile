.PHONY: install test test-lf watch lint format mypy cov check push pull hooks \
        frontend-install frontend-dev frontend-build frontend-lint dev

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
PTW    := .venv/bin/ptw
RUFF   := .venv/bin/ruff
MYPY   := .venv/bin/mypy
PRECOMMIT := .venv/bin/pre-commit
UVICORN := .venv/bin/uvicorn

install:
	uv sync --extra dev
	$(MAKE) frontend-install
	$(MAKE) hooks

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint

# Regenerate frontend/src/types/api.ts from FastAPI's OpenAPI schema.
# Run after any backend route change so the TS types stay in sync.
frontend-types:
	$(PYTHON) -c "from fm_web.api.app import create_app; import json; print(json.dumps(create_app().openapi(), indent=2))" \
		> frontend/src/types/openapi.json
	cd frontend && npx openapi-typescript src/types/openapi.json -o src/types/api.ts

# Run FastAPI backend on :8000 (Vite proxies /api to it)
dev:
	$(UVICORN) fm_web.api.app:app --reload --port 8000

hooks:
	$(PRECOMMIT) install --hook-type pre-commit --hook-type pre-push

test:
	$(PYTEST)

test-lf:
	$(PYTEST) --lf

watch:
	$(PTW) -- --tb=short

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

mypy:
	$(MYPY) src/

cov:
	$(PYTEST) --cov --cov-report=term-missing

check: lint mypy cov

pull:
	git pull origin main

push: check
	git push origin main
