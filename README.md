# Knowledge Root

> **knroot.com** — Build deep roots.

An AI-powered tech learning companion. Chat with an expert AI tutor about AI/ML and software engineering, browse live news across AI, Programming, and Politics, and explore knowledge through branching "Learn More" sub-threads backed by a hierarchical knowledge tree and MCQ-based knowledge checks.

Built with **React 18**, **Flask 3**, **LangGraph**, **OpenRouter** (DeepSeek), **PostgreSQL**, and **Redis**.

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | System design, data schema, API surface, caching strategy, and key decisions |
| [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) | Phase-by-phase task breakdown, branch strategy, unit test specs, and E2E test specs |
| [Progress Tracker](docs/PROGRESS.md) | Live checklist — track completion status for every feature and test |

---

## Features

- **Authentication** — register and log in with username, email, phone, and password. JWT access tokens with rotating HttpOnly refresh cookies.
- **Persistent Chat Sessions** — all conversations stored in PostgreSQL via LangGraph checkpointing. Sessions survive restarts and appear in the left-side history panel, auto-titled from content. Discussion sub-threads are nested visually under their parent.
- **Live Multi-Category News Feed** — right-side tab panel with three categories: AI, Programming, and Political. Smart Redis cache splits stable older articles (day cache) from fresh current-hour articles (hour cache).
- **Discuss Button** — click Discuss on any news article to open a new chat where the AI extracts the underlying theories, laws, and technical concepts — not personal or political opinions. First response is a structured learning overview with 3–5 concept sections.
- **Learn More Deep Dives** — each concept section has a [Learn More] button that opens a dedicated learning tab. The right pane of that tab shows a visual knowledge tree (where you are in the learning hierarchy). You can go arbitrarily deep; each level spawns a new tab with the tree extended.
- **Hierarchical Knowledge Check** — [Check Knowledge] at any depth generates MCQs spanning your full learning path from root to current topic. Wrong answers show an AI explanation panel. Correct answers show an [Explore deeper] button to open a new sub-thread on that concept.
- **Tool-Enabled Agent** — the AI can re-fetch live news mid-conversation on demand.
- **Production-Ready** — Gunicorn, nginx, connection pooling, structured logging, Docker health checks, GitHub Actions CI/CD with AI code + security + architecture review on every PR.

---

## Project Structure

```
ai-agent/
├── wsgi.py                        # Gunicorn entry: from backend.app import create_app; app = create_app()
│
├── backend/                       # All Python server code
│   ├── app.py                     # create_app() factory — blueprints, extensions, migrations
│   ├── config.py                  # Config / DevelopmentConfig / ProductionConfig / TestingConfig
│   ├── extensions.py              # db_pool, redis_client, limiter singletons
│   │
│   ├── api/                       # One Blueprint per domain
│   │   ├── auth/                  # routes.py (handlers) + service.py (logic)
│   │   ├── sessions/              # routes.py + service.py
│   │   ├── chat/                  # routes.py + service.py (includes suggested_topics extraction)
│   │   ├── news/                  # routes.py + service.py + cache.py + feeds.py
│   │   ├── discuss/               # routes.py + service.py (Discuss + Learn More + Tree)
│   │   └── quiz/                  # routes.py + service.py + generator.py (MCQ + Relearn)
│   │
│   ├── agent/
│   │   ├── graph.py               # LangGraph StateGraph
│   │   ├── prompts.py             # All system prompt strings as constants
│   │   └── tools.py               # LangChain @tool definitions
│   │
│   ├── core/
│   │   ├── auth.py                # @require_auth decorator
│   │   ├── db.py                  # query(), query_one(), execute(), run_migrations()
│   │   ├── llm.py                 # build_llm_client() factory
│   │   ├── errors.py              # AppError hierarchy, register_error_handlers(app)
│   │   └── scheduler.py           # APScheduler setup + news promotion jobs
│   │
│   └── migrations/                # Idempotent SQL DDL, run at startup
│       ├── 001_users.sql
│       ├── 002_chat_sessions.sql
│       ├── 003_news_cache.sql
│       ├── 004_mcq_attempts.sql
│       └── 005_session_hierarchy.sql
│
├── tests/
│   ├── conftest.py                # pytest fixtures (TestingConfig, fakeredis, auth helpers)
│   └── unit/                      # test_auth, test_sessions, test_chat, test_news, test_discuss, test_quiz
│
├── e2e/                           # Playwright E2E specs (per phase)
│
├── frontend/
│   ├── src/
│   │   ├── api/                   # auth.ts, sessions.ts, news.ts, quiz.ts, discuss.ts
│   │   ├── hooks/                 # useAuth, useSessions, useChat, useNews, useDiscuss,
│   │   │                          #   useLearnMore, useSessionTree, useQuiz, useHierarchicalQuiz
│   │   ├── store/                 # authStore.ts (Zustand — auth only)
│   │   ├── pages/                 # LoginPage, RegisterPage, LearnPage, QuizPage
│   │   ├── components/            # ChatSidebar, NewsTabs, NewsArticleCard, SectionedMessage,
│   │   │                          #   KnowledgeTree, MCQCard, RelearPanel, ProtectedRoute, …
│   │   └── types/index.ts
│   ├── nginx.conf
│   ├── Dockerfile
│   └── package.json
│
├── docs/
│   ├── ARCHITECTURE.md            # Full system design
│   ├── IMPLEMENTATION_PLAN.md     # Phase tasks, test specs, branch strategy
│   └── PROGRESS.md                # Live completion tracker
│
├── .claude/
│   └── agents/platform-dev.md    # Claude Code sub-agent for this project
│
├── .github/workflows/
│   ├── ci.yml                     # Lint → unit tests → E2E on every PR
│   ├── code-review.yml            # AI code quality review (Gemini)
│   ├── security-review.yml        # OWASP + LLM Top 10 security review
│   └── architecture-review.yml   # Architecture drift detection on PRs to main
│
├── requirements.txt
├── .env-example
├── Dockerfile
└── docker-compose.yml
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                          Browser (React)                          │
│  ┌─────────────┐   ┌────────────────────────┐   ┌─────────────┐ │
│  │  Chat List  │   │   Tech Learning Chat   │   │  AI News    │ │
│  │  (sidebar)  │   │  [Check Knowledge ▶]   │   │  Feed       │ │
│  └─────────────┘   └────────────────────────┘   └─────────────┘ │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST + JSON
┌───────────────────────────▼──────────────────────────────────────┐
│                   Flask API (Python)                              │
│   /auth/*   /sessions/*   /chat   /news   /quiz/*               │
└──────┬─────────────┬──────────────┬──────────────┬──────────────┘
       │             │              │              │
  JWT Auth      Session        LangGraph      Redis Cache
  bcrypt        Manager        + OpenRouter   (news feed)
       │             │              │              │
  ┌────▼─────────────▼──────────────▼──────────────▼──────┐
  │                   PostgreSQL 16                        │
  │   users · chat_sessions · mcq_attempts · news_cache   │
  └───────────────────────────────────────────────────────┘
```

For the full design — including data schema, caching algorithm, MCQ generation prompt, and all API contracts — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Branch Strategy

Each feature is developed on its own branch and merged to `main` via PR. Three automated AI reviewers run on every PR.

| Branch | Feature | Phase |
|---|---|---|
| `feature/auth` | Registration, login, JWT, refresh tokens | 1 |
| `feature/session-management` | Chat session CRUD, left-pane sidebar, auto-titles | 2 |
| `feature/smart-news-cache` | Redis day/hour cache, APScheduler promote job | 3 |
| `feature/knowledge-check` | MCQ generation, quiz page, auto-save, retry | 4 |
| `feature/polish` | Rate limiting, mobile layout, error boundaries | 5 |
| `feature/news-discuss-learn` | News tab group (AI/Programming/Political), Discuss button, sectioned AI responses, Learn More sub-threads, knowledge tree, hierarchical MCQ with relearn | 6 |

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for every task and test within each phase.
Track completion in [docs/PROGRESS.md](docs/PROGRESS.md).

---

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2 (`docker compose`) |
| OpenRouter API Key | [openrouter.ai/keys](https://openrouter.ai/keys) |

### 1. Configure environment

```bash
cp .env-example .env
```

Edit `.env` and fill in required values:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
JWT_SECRET_KEY=your-strong-random-secret-here
```

### 2. Build and start

```bash
docker compose up --build
```

### 3. Open the app

| Service | URL |
|---|---|
| **React UI** | http://localhost:3000 |
| Flask API | http://localhost:5000 |
| Health check | http://localhost:5000/health |

### 4. Stop

```bash
docker compose down          # keep data
docker compose down -v       # wipe data (fresh start)
```

---

## Configuration

| Variable | Default | Required | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | — | Yes | OpenRouter API key |
| `JWT_SECRET_KEY` | — | Yes | Secret for signing JWT tokens |
| `OPENROUTER_MODEL` | `deepseek/deepseek-chat` | No | Any OpenRouter model ID |
| `DATABASE_URL` | `postgresql://postgres:postgres@db:5432/postgres` | No | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | No | Redis connection string |
| `APP_URL` | `http://localhost:5000` | No | Sent as `HTTP-Referer` to OpenRouter |
| `CORS_ORIGINS` | `*` | No | Allowed CORS origins (set explicitly in production) |

### Switching models

```bash
OPENROUTER_MODEL=deepseek/deepseek-r1        # reasoning model
OPENROUTER_MODEL=anthropic/claude-sonnet-4-6 # Claude Sonnet
OPENROUTER_MODEL=google/gemini-2.5-flash     # Gemini Flash
```

---

## API Reference

Full API surface is documented in [docs/ARCHITECTURE.md § 10](docs/ARCHITECTURE.md#10-api-surface).

**Quick reference:**

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Login, receive JWT + refresh cookie |
| POST | `/auth/refresh` | cookie | Rotate refresh token |
| GET | `/sessions` | JWT | List chat sessions |
| POST | `/chat` | JWT | Send message in a session |
| GET | `/news` | JWT | Cached + fresh news feed |
| POST | `/quiz/generate` | JWT | Generate MCQs from a session |
| PUT | `/quiz/attempt/{id}` | JWT | Auto-save answers |
| POST | `/quiz/retry` | JWT | Start fresh attempt on same questions |

---

## Local Development (without Docker)

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Spin up Postgres and Redis via Docker
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7-alpine

export OPENROUTER_API_KEY=sk-or-v1-xxx
export JWT_SECRET_KEY=dev-secret
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export REDIS_URL=redis://localhost:6379/0

python app.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### Run tests

```bash
# Backend unit tests
pytest tests/unit/ -v --cov=. --cov-report=term-missing

# Frontend unit tests
cd frontend && npx vitest run --coverage

# E2E (requires full stack running)
cd e2e && npx playwright test
```

---

## GitHub Actions

Every pull request runs four automated workflows:

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | All PRs | Lint, unit tests (80% coverage gate), E2E smoke |
| `code-review.yml` | All PRs | Senior engineer AI review (code quality, patterns) |
| `security-review.yml` | All PRs | OWASP Top 10 + LLM Top 10 security review |
| `architecture-review.yml` | PRs to `main` | Architecture drift detection vs `docs/ARCHITECTURE.md` |

All four workflows use Gemini to review the diff. Set `GEMINI_API_KEY` in your repository secrets.

---

## News Sources

| Source | Feed |
|---|---|
| ArXiv AI | `https://arxiv.org/rss/cs.AI` |
| ArXiv ML | `https://arxiv.org/rss/cs.LG` |
| HuggingFace Blog | `https://huggingface.co/blog/feed.xml` |
| VentureBeat AI | `https://venturebeat.com/ai/feed/` |
| The Verge AI | `https://www.theverge.com/ai-artificial-intelligence/rss/index.xml` |

---

## License

MIT
