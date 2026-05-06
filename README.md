# Knowledge Root

> **knroot.com** — Build deep roots.

An AI-powered tech learning companion. Chat with an expert AI tutor about AI/ML and software engineering, browse live news, and explore knowledge through branching "Learn More" sub-threads backed by a hierarchical knowledge tree and MCQ-based knowledge checks.

Built with **Flask 3 + Jinja2**, **HTMX**, **Alpine.js**, **LangGraph**, **OpenRouter** (DeepSeek), **PostgreSQL**, and **Redis**.

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | System design, data schema, API surface, caching strategy, key decisions |
| [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) | Phase-by-phase task breakdown, branch strategy, test specs |
| [Progress Tracker](docs/PROGRESS.md) | Live checklist — completion status for every feature and test |

---

## Features

- **Authentication** — register and log in with username, email, and password. Server-side sessions stored in Redis.
- **Persistent Chat Sessions** — all conversations stored in PostgreSQL via LangGraph checkpointing. Sessions survive restarts and appear in the history panel, auto-titled from content.
- **Live Multi-Category News Feed** — three categories: AI, Programming, and Political. Smart Redis cache splits stable older articles (day cache) from fresh current-hour articles (hour cache).
- **Discuss Button** — click Discuss on any article to open a chat where the AI extracts the underlying theories, laws, and technical concepts.
- **Learn More Deep Dives** — each concept section has a Learn More button that opens a dedicated learning tab with a visual knowledge tree.
- **Hierarchical Knowledge Check** — generates MCQs spanning your full learning path. Wrong answers show an AI explanation. Correct answers unlock deeper exploration.
- **Tool-Enabled Agent** — the AI can re-fetch live news mid-conversation on demand.
- **Production-Ready** — Gunicorn, connection pooling, structured logging, Docker health checks, GitHub Actions CI/CD.

---

## Project Structure

```
ai-agent/
├── wsgi.py                        # Gunicorn entry point
│
├── backend/                       # All Python server code
│   ├── app.py                     # create_app() factory
│   ├── config.py                  # Dev / Prod / Testing config classes
│   ├── extensions.py              # redis_client, limiter, init_session()
│   │
│   ├── domain/                    # Pure Python domain models (no Flask/DB)
│   │   └── user.py                # User frozen dataclass + to_profile()
│   │
│   ├── repositories/              # All SQL encapsulated here; returns domain objects
│   │   └── user_repository.py     # UserRepository + module-level user_repo singleton
│   │
│   ├── api/                       # One Blueprint per domain
│   │   ├── pages/                 # Page routes — render_template() responses
│   │   ├── auth/                  # /auth/* — login, register, logout, /me
│   │   │   ├── schemas.py         # Pydantic v2 request validation schemas
│   │   │   ├── routes.py
│   │   │   └── service.py
│   │   ├── chat/                  # /chat — LangGraph-backed conversation
│   │   ├── news/                  # /news — RSS feed with Redis cache
│   │   ├── sessions/              # /sessions — session CRUD
│   │   ├── discuss/               # /discuss — article discussion + Learn More
│   │   ├── quiz/                  # /quiz — MCQ generation and attempts
│   │   └── health/                # /health
│   │
│   ├── templates/                 # Jinja2 SSR templates
│   │   ├── base.html              # Layout: HTMX + Alpine.js + Tailwind CDN
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   └── app/
│   │       └── index.html         # Dashboard (authenticated)
│   │
│   ├── static/
│   │   └── app.js                 # HTMX global config + HX-Redirect handler
│   │
│   ├── agent/
│   │   ├── graph.py               # LangGraph StateGraph
│   │   ├── prompts.py             # System prompt constants
│   │   └── tools.py               # LangChain @tool definitions
│   │
│   ├── core/
│   │   ├── auth.py                # require_auth (page redirect) + require_api_auth (401 JSON)
│   │   ├── db.py                  # query_one(), execute_returning(), run_migrations()
│   │   ├── llm.py                 # build_llm_client() factory
│   │   ├── errors.py              # AppError hierarchy + register_error_handlers()
│   │   └── scheduler.py           # APScheduler news promotion jobs
│   │
│   └── migrations/                # Idempotent SQL DDL, run at startup
│
├── tests/
│   ├── conftest.py                # Session fixtures, fakeredis, authed_client
│   └── unit/
│       ├── test_auth.py           # Auth routes — login, register, logout, /me
│       └── test_pages.py          # Page routes — render, auth guard, redirects
│
├── e2e/                           # Playwright E2E specs (added per phase)
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── PROGRESS.md
│
├── Makefile                       # All dev commands (replaces npm scripts)
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Dev + test dependencies
├── Dockerfile
├── docker-compose.yml
└── .env-example
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│          Browser (HTMX + Alpine.js + Tailwind)        │
└────────────────────────┬─────────────────────────────┘
                         │ HTML (full page + partials)
┌────────────────────────▼─────────────────────────────┐
│              Flask (Python) — Jinja2 SSR              │
│   /  /login  /register  (page routes)                 │
│   /auth/*  /chat  /news  /quiz/*  (API/HTMX routes)  │
└──────┬──────────────┬────────────────┬───────────────┘
       │              │                │
  Session Auth    LangGraph        Redis
  (Flask-Session  + OpenRouter     (Cache + Sessions)
   + bcrypt)           │
       │               │
  ┌────▼───────────────▼────────────────────────┐
  │              PostgreSQL 16                   │
  │  users · chat_sessions · mcq_attempts ·     │
  │  news_cache · session_hierarchy              │
  └─────────────────────────────────────────────┘
```

---

## First-Time Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| make | any | `sudo apt install make` |
| Docker + Docker Compose | 24+ / v2 | For running the full stack |
| OpenRouter API Key | — | [openrouter.ai/keys](https://openrouter.ai/keys) |

### 1. Clone and configure

```bash
git clone <repo-url>
cd ai-agent

cp .env-example .env
```

Edit `.env` and fill in the required values:

```env
SESSION_SECRET_KEY=your-long-random-secret-here   # required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx  # required
```

Generate a strong secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Create the Python venv and install dependencies

```bash
make init
```

This creates `~/.venvs/knroot`, upgrades pip, and installs `requirements-dev.txt`.

### 3. Start infrastructure (Postgres + Redis)

```bash
make up-infra
```

### 4. Run the dev server

```bash
make backend
```

App is now at **http://localhost:5000**

---

## Running with Docker (full stack)

```bash
make up        # build images + start all services
make logs      # follow logs
make down      # stop (keep data)
docker compose down -v   # stop + wipe data
```

| Service | URL |
|---|---|
| App | http://localhost:5000 |
| Health check | http://localhost:5000/health |

---

## Running Tests

### Unit tests (no database or Redis needed)

```bash
make test-unit
```

Save output to a file while still seeing it in the terminal:

```bash
make test-unit 2>&1 | tee test-output.txt
```

### What the unit tests cover

| File | Tests |
|---|---|
| `tests/unit/test_auth.py` | Register, login, logout, `/auth/me`, rate limiting |
| `tests/unit/test_pages.py` | Page rendering, auth guard on `/`, redirects |

### Integration tests (requires Postgres + Redis running)

```bash
make test-int
```

### Run everything

```bash
make test
```

### How the test environment works

- No real database or Redis needed for unit tests — both are mocked via `fakeredis` and `unittest.mock`
- Flask-Session is skipped in `TESTING` mode — Flask's built-in cookie session is used instead
- Heavy packages (`langgraph`, `langchain_*`, `psycopg_pool`) are stubbed with `MagicMock` before import
- Rate limiter uses `memory://` storage and resets between every test
- `authed_client` fixture pre-sets `session['user_id']` so protected-route tests skip the login flow

---

## All Make Targets

```bash
make init          # Create venv + install requirements-dev.txt
make backend       # Run Flask dev server (port 5000)

make up            # Docker Compose up (all services)
make down          # Docker Compose down
make build         # Rebuild images (no cache)
make restart       # down + up
make logs          # Follow all service logs
make up-infra      # Start only Postgres + Redis

make test-unit     # pytest tests/unit/ with coverage (threshold: 80%)
make test-int      # pytest tests/integration/
make test          # test-unit + test-int

make lint          # flake8 + mypy

make shell-db      # psql into the Postgres container
make shell-redis   # redis-cli into the Redis container
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `SESSION_SECRET_KEY` | Yes | — | Signs the session cookie |
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key |
| `OPENROUTER_MODEL` | No | `deepseek/deepseek-chat` | Any OpenRouter model ID |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@db:5432/postgres` | PostgreSQL connection |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection |
| `FLASK_ENV` | No | `production` | `development` \| `production` \| `testing` |

### Switching models

```bash
OPENROUTER_MODEL=deepseek/deepseek-r1        # reasoning model
OPENROUTER_MODEL=anthropic/claude-sonnet-4-6 # Claude Sonnet
OPENROUTER_MODEL=google/gemini-2.5-flash     # Gemini Flash
```

---

## API Reference

Full API surface is documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Auth routes:**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/login` | — | Login page |
| GET | `/register` | — | Register page |
| POST | `/auth/login` | — | Authenticate, set session cookie |
| POST | `/auth/register` | — | Create account, set session cookie |
| POST | `/auth/logout` | — | Clear session, redirect to /login |
| GET | `/auth/me` | Session | Return current user profile (JSON) |

**App routes (session required):**

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| POST | `/chat` | Send message to AI |
| GET | `/news` | Cached news feed |
| POST | `/quiz/generate` | Generate MCQs |

---

## GitHub Actions

Every pull request runs automated workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | All PRs | Lint → unit tests (80% coverage gate) → E2E |
| `code-review.yml` | All PRs | AI code quality review |
| `security-review.yml` | All PRs | OWASP Top 10 + LLM Top 10 security review |
| `architecture-review.yml` | PRs to `main` | Architecture drift detection |

Set `GEMINI_API_KEY` in repository secrets for the AI review workflows.

---

## License

MIT
