# Knowledge Root

> **knroot.com** — Build deep roots.

An AI-powered tech learning companion. Chat with an expert AI tutor about AI/ML and software engineering, browse live news with AI-curated rankings, fact-check headlines against Google Search, and explore knowledge through branching "Learn More" sub-threads backed by a hierarchical knowledge tree and MCQ-based knowledge checks.

Built with **Flask 3 + Jinja2**, **HTMX**, **Alpine.js**, **LangGraph** (chat), **Google ADK** (fact-check), **OpenRouter** (DeepSeek), **Google AI** (Gemini 2.0 Flash), **PostgreSQL**, and **Redis**.

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
- **Always-Visible Chat Input** — the message bar is always available; sending the first message auto-creates a session, so there's no "New Chat" friction.
- **Collapsible Session Tree** — left sidebar shows chat history as a hierarchical tree; news discussion sessions show their Learn More sub-threads with expand/collapse arrows.
- **Live Multi-Category News Feed** — three tabs: AI, Dev, World. Each card shows source, date, title, and description with `[Read article]`, `[Explore]`, and `[Fact Check]` buttons. Smart Redis cache splits stable older articles (day cache) from fresh current-hour articles (hour cache).
- **Hourly AI News Curation** — DeepSeek ranks freshly fetched RSS articles by importance every hour so the most impactful news always appears first; falls back to RSS order on LLM failure.
- **Fact-Check Button** — click `[Fact Check]` on any news article to trigger a Google Search-powered ADK pipeline (Search Agent + Verdict Agent) that verifies key claims and rates them verified / disputed / unverifiable with source links.
- **Explore Button** — click `[Explore]` on an article to open a chat where the AI extracts the underlying theories, laws, and technical concepts as a sectioned response.
- **Learn More Deep Dives** — each concept section has a Learn More button that opens a dedicated learning tab with a visual knowledge tree.
- **Hierarchical Knowledge Check** — generates MCQs spanning your full learning path. Wrong answers show an AI explanation. Correct answers unlock deeper exploration.
- **Tool-Enabled Chat Agent** — a LangGraph ReAct agent can re-fetch live news mid-conversation on demand.
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
┌──────────────────────────────────────────────────────────────┐
│          Browser (HTMX + Alpine.js + Tailwind)                │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTML (full page + partials)
┌────────────────────────▼─────────────────────────────────────┐
│              Flask (Python) — Jinja2 SSR                      │
│   /  /login  /register  (page routes)                         │
│   /auth/*  /chat  /news  /news/discuss  /news/fact-check      │
│   /sessions/*  /quiz/*           (API + HTMX routes)          │
└────┬──────────┬──────────────┬────────────────┬──────────────┘
     │          │              │                │
 Session     LangGraph     Direct DeepSeek    Google ADK
 Auth        ReAct Agent   (Explore /         SequentialAgent
 (bcrypt +   (chat —       Learn More +       (fact-check —
  Redis-     OpenRouter    hourly news        Gemini 2.0
  backed)    DeepSeek)     curation)          Flash + Search)
     │          │              │                │
  ┌──▼──────────▼──────────────▼────────────────▼───┐
  │       PostgreSQL 16            +    Redis 7     │
  │   users · chat_sessions ·         news cache    │
  │   mcq_attempts · news_cache ·     (day + hour   │
  │   LangGraph checkpoints           per category) │
  └─────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md §25](docs/ARCHITECTURE.md) for the full five-layer AI architecture (RSS cache → AI curation → LangGraph chat → direct discuss pipeline → ADK fact-check).

---

## First-Time Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| make | any | `sudo apt install make` |
| Docker + Docker Compose | 24+ / v2 | For running the full stack |
| OpenRouter API Key | — | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Google AI API Key | optional | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — only required for the `[Fact Check]` button |

### 1. Clone and configure

```bash
git clone <repo-url>
cd ai-agent

cp .env-example .env
```

Edit `.env` and fill in the values:

```env
SESSION_SECRET_KEY=your-long-random-secret-here   # required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx  # required (chat, Explore, news curation)
GOOGLE_API_KEY=AIzaSy-xxxxxxxxxxxxxxxxxxxxxxxx    # optional — required for [Fact Check] button
```

`GOOGLE_API_KEY` is optional. Without it the rest of the app works normally, but clicking `[Fact Check]` on a news article will render a graceful error card. Get a free key at https://aistudio.google.com/apikey.

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
make up-dev        # build images + start all services (port 5000)
make logs-dev      # follow logs
make down-dev      # stop (keep data)
make restart-dev   # down + rebuild + up in one command
docker compose --profile dev down -v   # stop + wipe data
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
make init              # Create venv + install requirements-dev.txt
make backend           # Run Flask dev server locally (port 5000)

# Dev stack (port 5000)
make up-dev            # Build images + start all services
make down-dev          # Stop services (keep data)
make restart-dev       # down + rebuild + up in one command
make build-dev         # Rebuild images without cache
make logs-dev          # Follow service logs
make up-infra          # Start only Postgres + Redis

# E2E stack (isolated, port 5001)
make up-e2e            # Start isolated E2E environment
make down-e2e          # Stop E2E environment
make logs-e2e          # Follow E2E service logs

# Testing
make test-unit         # pytest tests/unit/ with coverage (threshold: 80%)
make test-int          # pytest tests/integration/
make test              # test-unit + test-int
make test-e2e          # Run Playwright E2E suite (captures server log to e2e-server.log)
make test-e2e-fresh    # Rebuild E2E stack from scratch + run E2E suite

# Quality
make lint              # flake8 + mypy

# Database / Redis shells
make shell-db          # psql into the Postgres container
make shell-redis       # redis-cli into the Redis container
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `SESSION_SECRET_KEY` | Yes | — | Signs the session cookie |
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key — used for chat, Explore / Learn More, and hourly news curation |
| `OPENROUTER_MODEL` | No | `deepseek/deepseek-chat` | Any OpenRouter model ID |
| `GOOGLE_API_KEY` | No | — | Google AI API key for the Gemini fact-check pipeline. Optional, but `[Fact Check]` returns a graceful error card if unset. Get a key at https://aistudio.google.com/apikey |
| `FACT_CHECK_MODEL` | No | `gemini-2.0-flash` | Gemini model used by the ADK fact-check `SequentialAgent` |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@db:5432/postgres` | PostgreSQL connection |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection |
| `FLASK_ENV` | No | `production` | `development` \| `production` \| `testing` |

### Switching models

OpenRouter (chat, Explore / Learn More, news curation):
```bash
OPENROUTER_MODEL=deepseek/deepseek-chat      # default — fast, cheap
OPENROUTER_MODEL=deepseek/deepseek-r1        # reasoning model
OPENROUTER_MODEL=anthropic/claude-sonnet-4-6 # Claude Sonnet
OPENROUTER_MODEL=google/gemini-2.5-flash     # Gemini Flash via OpenRouter
```

Google AI (fact-check `SequentialAgent` only):
```bash
FACT_CHECK_MODEL=gemini-2.0-flash      # default — fast, cheap
FACT_CHECK_MODEL=gemini-2.5-flash      # more capable
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
