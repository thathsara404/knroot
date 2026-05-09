VENV  := $(HOME)/.venvs/knroot
PIP   := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
FLASK := $(VENV)/bin/flask
FLAKE8 := $(VENV)/bin/flake8
MYPY  := $(VENV)/bin/mypy

.PHONY: init \
        up-dev down-dev restart-dev logs-dev build-dev \
        up-e2e down-e2e logs-e2e test-e2e-fresh \
        up-infra backend \
        playwright-install test-unit test-int test-e2e test \
        lint shell-db shell-redis \
        flush-cache

# ── Setup ─────────────────────────────────────────────────────────────────────

init:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements-dev.txt -q
	@echo "Setup complete. Activate: source $(VENV)/bin/activate"

# ── Development environment (port 5000) ───────────────────────────────────────

up-dev:
	docker compose --profile dev up --build -d

down-dev:
	docker compose --profile dev down

restart-dev:
	docker compose --profile dev down && docker compose --profile dev up --build -d

logs-dev:
	docker compose --profile dev logs -f

build-dev:
	docker compose --profile dev build --no-cache

up-infra:
	docker compose --profile dev up db redis -d

shell-db:
	docker compose --profile dev exec db psql -U postgres -d postgres

shell-redis:
	docker compose --profile dev exec redis redis-cli

backend:
	FLASK_ENV=development $(FLASK) --app wsgi:app run --debug --port 5000

# ── E2E environment (isolated DB + Redis, port 5001) ─────────────────────────

up-e2e:
	docker compose --profile e2e up --build -d

down-e2e:
	docker compose --profile e2e down

logs-e2e:
	docker compose --profile e2e logs -f

# ── Tests ─────────────────────────────────────────────────────────────────────

playwright-install:
	$(VENV)/bin/playwright install chromium
	sudo $(VENV)/bin/playwright install-deps chromium

test-unit:
	$(PYTEST) tests/unit/ -v --cov=backend --cov-report=term-missing --cov-fail-under=80

test-int:
	$(PYTEST) tests/integration/ -v --cov=backend --cov-append --cov-report=term-missing --cov-fail-under=80

test-e2e:
	docker compose --profile e2e logs -f --no-log-prefix web-e2e > e2e-server.log 2>&1 & \
	LOG_PID=$$!; \
	BASE_URL=$${BASE_URL:-http://localhost:5001} $(PYTEST) e2e/ -v; \
	EXIT=$$?; \
	kill $$LOG_PID 2>/dev/null || true; \
	echo "Server logs saved to e2e-server.log"; \
	exit $$EXIT

test-e2e-fresh:
	docker compose --profile e2e down
	docker compose --profile e2e build --no-cache
	docker compose --profile e2e up -d
	sleep 5
	docker compose --profile e2e logs -f --no-log-prefix web-e2e > e2e-server.log 2>&1 & \
	LOG_PID=$$!; \
	BASE_URL=$${BASE_URL:-http://localhost:5001} $(PYTEST) e2e/ -v; \
	EXIT=$$?; \
	kill $$LOG_PID 2>/dev/null || true; \
	echo "Server logs saved to e2e-server.log"; \
	exit $$EXIT

test: test-unit test-int

# ── Dev cache management ──────────────────────────────────────────────────────

flush-cache:
	@echo "[dev] Flushing Redis news caches (news:*)..."
	@docker compose --profile dev exec -T redis sh -c "redis-cli --scan --pattern 'news:*' | xargs -r redis-cli del"
	@echo "[dev] Done. Caches repopulate automatically on the next request."

# ── Lint ──────────────────────────────────────────────────────────────────────

lint:
	$(FLAKE8) backend/ wsgi.py --max-line-length=100
	$(MYPY) backend/ wsgi.py --ignore-missing-imports
