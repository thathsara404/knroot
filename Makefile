.PHONY: help \
        up down build logs restart \
        up-infra up-backend up-frontend \
        start-backend start-frontend \
        test test-backend-unit test-backend-integration test-frontend-unit test-e2e \
        lint lint-backend lint-frontend \
        db-shell redis-shell

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
help:
	@echo ""
	@echo "  AI Learning Platform — developer commands"
	@echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  DOCKER (full stack)"
	@echo "    make up                   Build and start all services (db, redis, web, frontend)"
	@echo "    make down                 Stop and remove containers"
	@echo "    make build                Rebuild Docker images without cache"
	@echo "    make restart              down + up"
	@echo "    make logs                 Tail logs from all services"
	@echo ""
	@echo "  DOCKER (infra only — for local dev)"
	@echo "    make up-infra             Start only DB + Redis (use with local flask/vite)"
	@echo ""
	@echo "  LOCAL DEV (no Docker for app processes)"
	@echo "    make start-backend        Flask dev server (requires up-infra first)"
	@echo "    make start-frontend       Vite dev server"
	@echo ""
	@echo "  TESTS"
	@echo "    make test-backend-unit    pytest tests/unit/  (no DB, fakeredis)"
	@echo "    make test-backend-int     pytest tests/integration/ (test DB + fakeredis)"
	@echo "    make test-frontend        Vitest + RTL (cd frontend)"
	@echo "    make test-e2e             Playwright (full stack must be running)"
	@echo "    make test                 unit + integration + frontend (no e2e)"
	@echo ""
	@echo "  LINT"
	@echo "    make lint-backend         flake8 + mypy"
	@echo "    make lint-frontend        eslint + tsc"
	@echo "    make lint                 both"
	@echo ""
	@echo "  UTILS"
	@echo "    make db-shell             psql into the running DB container"
	@echo "    make redis-shell          redis-cli into the running Redis container"
	@echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DOCKER — FULL STACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

up:
	docker compose up --build -d
	@echo ""
	@echo "  Stack is up:"
	@echo "    Backend   → http://localhost:5000"
	@echo "    Frontend  → http://localhost:3000"
	@echo ""

down:
	docker compose down

build:
	docker compose build --no-cache

restart: down up

logs:
	docker compose logs -f

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DOCKER — INFRA ONLY (DB + Redis for local dev)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

up-infra:
	docker compose up db redis -d
	@echo ""
	@echo "  DB    → localhost:5432"
	@echo "  Redis → localhost:6379"
	@echo ""
	@echo "  Now run:  make start-backend   (in one terminal)"
	@echo "            make start-frontend  (in another)"
	@echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL DEV SERVERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

start-backend:
	FLASK_ENV=development flask --app wsgi:app run --debug --port 5000

start-frontend:
	cd frontend && npm run dev

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test-backend-unit:
	pytest tests/unit/ -v \
	  --cov=backend \
	  --cov-report=term-missing \
	  --cov-fail-under=80

test-backend-int:
	pytest tests/integration/ -v \
	  --cov=backend \
	  --cov-append \
	  --cov-report=term-missing

test-frontend:
	cd frontend && npm run test:unit

test-e2e:
	npx playwright test --config=e2e/playwright.config.ts

test: test-backend-unit test-backend-int test-frontend

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lint-backend:
	flake8 backend/ wsgi.py --max-line-length=100
	mypy backend/ wsgi.py --ignore-missing-imports

lint-frontend:
	cd frontend && npm run lint
	cd frontend && npm run typecheck

lint: lint-backend lint-frontend

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

db-shell:
	docker compose exec db psql -U postgres -d postgres

redis-shell:
	docker compose exec redis redis-cli
