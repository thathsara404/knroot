# Knowledge Root — Architecture Document

> **Scope:** Reshaping the existing AI chat agent into a full-featured tech-learning platform with authentication, chat history, smart news caching, and an adaptive knowledge-check system.
>
> **Baseline stack:** Flask · PostgreSQL · LangGraph · OpenRouter LLM · React + TypeScript + Vite · Docker Compose

---

## 1. Product Vision

A focused **AI-powered tech learning companion** where users can:

1. Register and log in with a personal account.
2. Have persistent, named chat sessions with an AI tutor that specialises in AI/ML and software engineering.
3. Glance at the latest AI news in a live right-side panel — without hammering news APIs on every page load.
4. Test their own knowledge after any chat session through auto-generated technical MCQs derived from that conversation.

---

## 2. High-Level System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                          Browser (React)                          │
│                                                                    │
│  ┌─────────────┐   ┌────────────────────────┐   ┌─────────────┐  │
│  │  Left Pane  │   │     Chat Interface      │   │ Right Pane  │  │
│  │  Chat List  │   │  (Tech Learning Chat)   │   │  AI News    │  │
│  │             │   │  [Check Knowledge ▶]    │   │  Feed       │  │
│  └─────────────┘   └────────────────────────┘   └─────────────┘  │
│                                  │                                 │
│                    ┌─────────────▼────────────┐                   │
│                    │  Knowledge Check Tab      │                   │
│                    │  (MCQ Interface)          │                   │
│                    └──────────────────────────┘                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTPS / REST + JSON
┌───────────────────────────▼──────────────────────────────────────┐
│                      Flask API (Python)                            │
│                                                                    │
│  /auth/*     /sessions/*     /chat/*     /news     /quiz/*        │
└──────┬──────────────┬──────────────┬──────────────┬──────────────┘
       │              │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌───▼───┐   ┌─────▼──────┐
  │  Auth   │   │  Session  │  │LangG- │   │   Redis    │
  │  (JWT)  │   │  Manager  │  │raph   │   │   Cache    │
  └────┬────┘   └─────┬─────┘  └───┬───┘   └─────┬──────┘
       │              │            │              │
  ┌────▼──────────────▼────────────▼──────────────▼──────┐
  │                   PostgreSQL                          │
  │   users · chat_sessions · mcq_attempts · news_cache  │
  └───────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer         | Technology                            | Rationale                                                     |
|---------------|---------------------------------------|---------------------------------------------------------------|
| Frontend      | React 18 + TypeScript + Vite          | Existing; fast HMR, strong typing                             |
| Routing       | React Router v6                       | SPA routing for auth pages and quiz tab                       |
| Styling       | Tailwind CSS                          | Existing utility-first design system                          |
| Backend       | Flask 3 (Python)                      | Existing; lightweight, familiar                               |
| Auth          | JWT (PyJWT) + bcrypt                  | Stateless access tokens, secure password hashing              |
| AI Chat       | LangGraph + OpenRouter                | Existing; graph-based agent with persistent checkpointing     |
| MCQ Generation| OpenRouter LLM (separate call)        | Reuse existing LLM key; dedicated prompt chain                |
| Cache         | Redis 7                               | Sub-millisecond reads; TTL-native; separates fast-path state  |
| Database      | PostgreSQL 16                         | Existing; adds user, session, and quiz tables                 |
| Container     | Docker Compose                        | Existing; add Redis service                                   |

---

## 3.5 Backend Package Structure

All server-side Python lives inside the `backend/` package. The entry point for Gunicorn is `wsgi.py` at the project root.

```
ai-agent/
├── wsgi.py                             ← Gunicorn entry: from backend.app import create_app; app = create_app()
│
├── backend/                            ← Python package
│   ├── app.py                          ← create_app() factory — registers blueprints, extensions, migrations
│   ├── config.py                       ← Config / DevelopmentConfig / ProductionConfig / TestingConfig
│   ├── extensions.py                   ← db_pool, redis_client, limiter, scheduler — single instances
│   │
│   ├── api/                            ← One sub-package per API domain; each has its own Blueprint
│   │   ├── auth/
│   │   │   ├── routes.py               ← Blueprint('/auth') — thin handlers, no business logic
│   │   │   └── service.py              ← register_user(), login_user(), refresh_token(), logout()
│   │   ├── sessions/
│   │   │   ├── routes.py
│   │   │   └── service.py              ← create_session(), list_sessions(), rename(), delete(), get_messages()
│   │   ├── chat/
│   │   │   ├── routes.py
│   │   │   └── service.py              ← send_message(), auto_title(), extract_suggested_topics()
│   │   ├── news/
│   │   │   ├── routes.py
│   │   │   ├── service.py              ← get_news(category, force) — orchestrates cache + RSS
│   │   │   ├── cache.py                ← Redis day/hour cache, DB fallback, promote_hour_to_day()
│   │   │   └── feeds.py                ← NEWS_FEEDS dict keyed by 'ai' | 'programming' | 'political'
│   │   ├── discuss/
│   │   │   ├── routes.py
│   │   │   └── service.py              ← news_discuss(), create_learn_more_session(), get_tree()
│   │   └── quiz/
│   │       ├── routes.py
│   │       ├── service.py              ← attempt lifecycle: generate, save, submit, retry, relearn
│   │       └── generator.py            ← LLM MCQ prompt + validation; relearn prompt + cache
│   │
│   ├── agent/
│   │   ├── graph.py                    ← LangGraph StateGraph definition + compile_graph() helper
│   │   ├── prompts.py                  ← ALL system prompt strings as module-level constants
│   │   └── tools.py                    ← LangChain @tool definitions (get_latest_ai_news)
│   │
│   ├── core/
│   │   ├── auth.py                     ← @require_auth decorator; injects g.user_id from JWT sub
│   │   ├── db.py                       ← query(), query_one(), execute(), execute_returning(), run_migrations()
│   │   ├── llm.py                      ← build_llm_client() factory shared across chat + quiz + discuss
│   │   ├── errors.py                   ← AppError hierarchy, register_error_handlers(app)
│   │   └── scheduler.py                ← init_scheduler(app) — APScheduler with news promotion jobs
│   │
│   └── migrations/                     ← Idempotent SQL DDL, run in order at startup
│       ├── 001_users.sql
│       ├── 002_chat_sessions.sql
│       ├── 003_news_cache.sql
│       ├── 004_mcq_attempts.sql
│       └── 005_session_hierarchy.sql
│
├── tests/                              ← pytest — at project root, imports from backend.*
│   ├── conftest.py                     ← app fixture (TestingConfig), test DB, fakeredis, auth helpers
│   └── unit/
│       ├── test_auth.py
│       ├── test_sessions.py
│       ├── test_chat.py
│       ├── test_news.py
│       ├── test_discuss.py
│       └── test_quiz.py
│
├── frontend/                           ← React 18 + TypeScript (Vite)
├── e2e/                                ← Playwright E2E specs
├── docs/                               ← Architecture, implementation plan, progress tracker
├── .claude/agents/platform-dev.md     ← Claude Code sub-agent for this project
└── .github/workflows/                  ← CI, code-review, security-review, architecture-review
```

### Module Responsibilities (hard rules)

| File | Owns | Must NOT contain |
|------|------|-----------------|
| `backend/api/*/routes.py` | HTTP parsing, input validation, response serialisation | SQL, LLM calls, Redis ops, business logic |
| `backend/api/*/service.py` | Business logic, DB queries, orchestration | `request`, `g` (accepts `user_id` as parameter) |
| `backend/agent/graph.py` | LangGraph graph only | Route code, DB queries |
| `backend/agent/prompts.py` | Prompt string constants | Any logic |
| `backend/core/auth.py` | `@require_auth` decorator | Business logic beyond token validation |
| `backend/core/db.py` | Connection pool helpers | Domain logic |
| `backend/core/llm.py` | LLM client factory | Prompt strings (those live in prompts.py) |
| `backend/migrations/*.sql` | DDL (CREATE/ALTER/INDEX) | DML (INSERT/UPDATE/DELETE) |

---

## 4. Database Schema

### 4.1 `users`
```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    phone         VARCHAR(20),
    full_name     VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  DEFAULT NOW()
);
```

### 4.2 `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id       VARCHAR(255) UNIQUE NOT NULL,   -- LangGraph thread_id
    title           VARCHAR(255),                   -- NULL = auto-generate from content
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_last_message ON chat_sessions(user_id, last_message_at DESC);
```

### 4.3 `mcq_attempts`
```sql
CREATE TABLE mcq_attempts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id   UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    questions    JSONB NOT NULL,   -- MCQ question objects (see §7)
    answers      JSONB,            -- {question_id: selected_option_index}
    score        SMALLINT,         -- correct answer count
    attempted_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_mcq_session ON mcq_attempts(session_id);
```

### 4.4 `news_cache` (DB fallback for Redis)
```sql
CREATE TABLE news_cache (
    cache_key  VARCHAR(20) PRIMARY KEY,  -- "2026-05-04" or "2026-05-04-14"
    articles   JSONB       NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

---

## 5. Authentication

### 5.1 Registration — `POST /auth/register`

**Request body:**
```json
{
  "full_name": "Alice Smith",
  "username":  "alicesmith",
  "email":     "alice@example.com",
  "phone":     "+1-555-0100",
  "password":  "••••••••"
}
```

**Server logic:**
1. Validate all fields (username: 3–50 chars, alphanumeric+underscore; email: RFC 5322; phone: E.164; password: min 8 chars, at least one number).
2. Hash password with `bcrypt` (cost factor 12).
3. Insert into `users`.
4. Return `201` with the user profile (no password hash).

### 5.2 Login — `POST /auth/login`

**Request body:**
```json
{ "identifier": "alicesmith",  "password": "••••••••" }
```
`identifier` can be username **or** email.

**Server logic:**
1. Look up user by username OR email.
2. `bcrypt.checkpw(password, hash)`.
3. Issue **access token** (JWT, 15 min expiry) and **refresh token** (JWT, 7 days expiry).
4. Return access token in JSON body; set refresh token as `HttpOnly; SameSite=Strict` cookie.

### 5.3 Token Refresh — `POST /auth/refresh`

Uses the HttpOnly refresh cookie; returns a new access token. Refresh tokens are single-use (rotation); old token is invalidated in a `refresh_tokens` blocklist stored in Redis.

### 5.4 Middleware

Every protected route checks the `Authorization: Bearer <token>` header. The decoded `sub` (user UUID) is injected into `flask.g.user_id` for downstream handlers.

---

## 6. News Feed with Smart Caching

### 6.1 Caching Strategy

The goal: serve **today's older articles from cache** and **current-hour articles fresh** — without redundant RSS fetches.

```
Cache Keys (Redis + DB fallback):
  news:day:{YYYY-MM-DD}       TTL: until midnight UTC
  news:hour:{YYYY-MM-DD-HH}   TTL: 1 hour
```

**Fetch algorithm on `GET /news`:**

```
1. hour_key  = "news:hour:{today}-{current_hour}"
2. day_key   = "news:day:{today}"

3. hour_articles = redis.get(hour_key)
4. IF hour_articles is None:
       hour_articles = fetch_from_rss(since=start_of_current_hour)
       redis.set(hour_key, hour_articles, ex=3600)
       # Also upsert into DB news_cache for persistence

5. day_articles = redis.get(day_key)
6. IF day_articles is None:
       day_articles = db.query("SELECT articles FROM news_cache WHERE cache_key = ?", day_key)
       IF day_articles is None:
           day_articles = []
       redis.set(day_key, day_articles, ex=ttl_until_midnight())

7. MERGE(day_articles, hour_articles, dedupe_by="link")
8. RETURN merged_articles[:20]
```

At the **start of each new hour**, the scheduler (APScheduler inside Flask or a cron job) promotes the previous hour's cache into the day cache:
```
day_articles = merge(day_articles, prev_hour_articles)
redis.set(day_key, day_articles, ex=ttl_until_midnight())
db.upsert(day_key, day_articles)
```

### 6.2 Article Data Shape

```json
{
  "id":        "sha256_of_link[:12]",
  "source":    "HuggingFace Blog",
  "title":     "Introducing SmolVLM",
  "link":      "https://...",
  "summary":   "SmolVLM is a compact vision-language model...",
  "published": "2026-05-04T09:30:00Z",
  "hour_slot": "2026-05-04-09"
}
```

---

## 7. Chat System

### 7.1 Session Lifecycle

```
POST /sessions                  → create new session, return session_id + thread_id
GET  /sessions                  → list user's sessions (title, last_message_at, id)
PATCH /sessions/{id}            → rename session (user sets title)
DELETE /sessions/{id}           → delete session + LangGraph checkpoint
POST /chat                      → send message in a session
GET  /sessions/{id}/messages    → replay full message history (from LangGraph state)
```

### 7.2 Auto-Title Generation

When a session has no user-given title, the backend auto-generates one **after the first assistant reply**:

1. Pass the first user message + assistant reply to the LLM with a short prompt:
   > "In 4–6 words, summarise this tech discussion. No punctuation. Examples: 'LoRA fine-tuning on LLaMA 3', 'Docker networking bridge mode'."
2. Store the result as `chat_sessions.title`.
3. Frontend polls/updates the sidebar entry after the first response.

### 7.3 Chat API — `POST /chat`

**Request:**
```json
{
  "session_id": "uuid",
  "message":    "What is gradient checkpointing?"
}
```

**Response:**
```json
{
  "response":          "Gradient checkpointing is a memory-saving technique...",
  "thread_id":         "uuid",
  "session_id":        "uuid",
  "title":             "Gradient checkpointing memory trade-off",
  "suggested_topics":  ["Backpropagation memory complexity", "Mixed-precision training", "ZeRO optimisation"]
}
```

`suggested_topics` is extracted from an `<explore>` XML block that the agent appends to educational responses. The backend strips this block from `response` before returning. If the response is not educational (short answer, follow-up clarification), the field is an empty list.

This field is the mechanism for the **manual learning-tree entry point** — frontend renders topic chips below the message for the user to launch sub-sessions.

The `user_id` is extracted from the JWT, not from the request body.

---

## 8. Knowledge Check (MCQ) System

### 8.1 Flow

```
Chat Page                   New Tab (Quiz Page)
    │                              │
    │  Click [Check Knowledge]     │
    ├──────────────────────────────►
    │  POST /quiz/generate         │
    │  {session_id}                │
    │                              │ Spinner while generating
    │                              │ Receive questions JSON
    │                              │ Render MCQ cards
    │                              │ User answers
    │                              │
    │                              │ Auto-save on each answer
    │                              │ PUT /quiz/attempt/{id}
    │                              │
    │                              │ Submit → score displayed
    │                              │ PUT /quiz/attempt/{id} (completed_at set)
    │                              │
    │                              │ [Retry] → reset selections,
    │                              │  same questions, new attempt row
```

### 8.2 MCQ Generation — `POST /quiz/generate`

**Input:** `session_id`

**Server logic:**
1. Load the full conversation from LangGraph state for the session's `thread_id`.
2. Extract only the **technical content** (strip small-talk turns).
3. Build the generation prompt (see §8.3).
4. Call LLM → parse JSON response → validate structure.
5. Insert into `mcq_attempts` with `answers = null`, `score = null`.
6. Return `attempt_id` + `questions` array.

**Response:**
```json
{
  "attempt_id": "uuid",
  "questions": [
    {
      "id":      "q_01",
      "text":    "Which optimization reduces GPU memory by recomputing activations during the backward pass?",
      "options": [
        "Mixed-precision training",
        "Gradient checkpointing",
        "Gradient accumulation",
        "ZeRO Stage 3"
      ],
      "correct": 1
    }
  ]
}
```

> **Note:** `correct` is only returned when the attempt is submitted (or on retry load of a completed attempt), not during the initial quiz render, to prevent trivial cheating.

### 8.3 MCQ Generation Prompt

```
You are a technical quiz generator. Given the following AI/ML/software engineering
conversation, generate exactly 8 multiple-choice questions.

STRICT RULES — a question is INVALID if it asks about:
  ✗ People's names, company names, or organisations
  ✗ Dates, years, or time periods
  ✗ Geographic locations
  ✗ Who said what in the conversation
  ✗ General trivia unrelated to the technical concepts discussed

A question is VALID only if it tests:
  ✓ Technical concepts, algorithms, or architectures mentioned
  ✓ Trade-offs between approaches that were discussed
  ✓ How a technology works under the hood
  ✓ Practical implications of a technique
  ✓ Terminology and definitions in context

Return ONLY valid JSON, no prose:
{
  "questions": [
    {
      "id": "q_01",
      "text": "<question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct": <0|1|2|3>
    }
  ]
}

Conversation:
{conversation_text}
```

### 8.4 Auto-Save

- Every time the user selects an option, the frontend fires:
  ```
  PUT /quiz/attempt/{attempt_id}
  { "answers": { "q_01": 1, "q_03": 2 } }
  ```
  This is debounced 500 ms to avoid per-keystroke writes.

- On page reload, the frontend calls `GET /quiz/attempt/{attempt_id}` to restore saved state.

### 8.5 Retry

- User clicks **[Retry]**: frontend calls `POST /quiz/retry` with `{ "session_id": "..." }`.
- Backend creates a **new `mcq_attempts` row** with the same questions (no re-generation cost) and resets answers/score.
- Returns the new `attempt_id`; frontend resets all selections.
- Previous attempt is preserved — users can review old scores via `GET /quiz/attempts?session_id=...`.

---

## 9. Frontend Architecture

### 9.1 Page / Route Map

```
/                  → redirect to /login or /app based on auth
/login             → Login page
/register          → Registration page
/app               → Main 3-pane layout (protected)
/app/session/:id   → Auto-select specific session in left pane
/quiz/:attemptId   → Knowledge Check tab (opens in new tab)
```

### 9.2 Three-Pane Layout

```
┌──────────────┬────────────────────────────┬──────────────┐
│  LEFT PANE   │       CENTRE PANE          │  RIGHT PANE  │
│  240px fixed │  flex-1, min-w-0           │  320px fixed │
│              │                            │              │
│ ● New Chat   │  ┌──────────────────────┐  │  AI News     │
│              │  │   Message Thread     │  │              │
│ Today        │  │                      │  │  [HuggingFace│
│ ├ LoRA fine- │  │  User: What is ...   │  │   Blog]      │
│ │  tuning..  │  │  AI: ...             │  │  Introducing │
│ ├ Docker net │  │                      │  │  SmolVLM     │
│              │  └──────────────────────┘  │  > ...       │
│ Yesterday    │                            │              │
│ ├ Attention  │  ┌──────────────────────┐  │  [ArXiv ML]  │
│   mechanisms │  │   Input Bar          │  │  Flash Att.  │
│              │  └──────────────────────┘  │  3.0         │
│              │                            │              │
│              │  [Check Knowledge ▶]       │              │
└──────────────┴────────────────────────────┴──────────────┘
```

**Left pane** — `ChatSidebar`:
- Groups sessions by: Today / Yesterday / This Week / Older.
- Session item: `title` (auto or user-set) + relative timestamp.
- Long-press or right-click → rename / delete.
- Skeleton loaders while fetching.

**Centre pane** — `ChatInterface`:
- Existing `MessageList` + `InputBar`.
- "Check Knowledge" button appears below `InputBar` once there are ≥ 3 AI responses in the session.
- Button opens `/quiz/:attemptId` in `window.open('...', '_blank')`.

**Right pane** — `NewsPanel`:
- Grouped by source.
- Timestamp badge shows article age (e.g. "2h ago").
- Pull-to-refresh / manual refresh button triggers `GET /news?force=true`.
- Skeleton loaders on first load.

### 9.3 Knowledge Check Tab (`/quiz/:attemptId`)

```
┌──────────────────────────────────────────────────────┐
│  Knowledge Check  ·  LoRA fine-tuning on LLaMA 3     │
│                              Score: —/8  [Submit]    │
├──────────────────────────────────────────────────────┤
│  Q1. Which technique reduces trainable parameters... │
│                                                       │
│  ○ A  Full fine-tuning                               │
│  ● B  Low-Rank Adaptation (LoRA)    ← selected       │
│  ○ C  Prefix tuning                                   │
│  ○ D  Prompt tuning                                   │
│                                                       │
│  Q2. ...                                              │
│  ...                                                  │
├──────────────────────────────────────────────────────┤
│  [Retry]                          [Back to Chat]     │
└──────────────────────────────────────────────────────┘
```

After submit:
- Correct answers turn green, wrong selections turn red with the correct option highlighted.
- Score badge updates: `Score: 6/8`.
- `[Retry]` resets selections; questions are the same.

### 9.4 State Management

| Concern              | Solution                                              |
|----------------------|-------------------------------------------------------|
| Auth tokens          | `useAuthStore` (Zustand) + `localStorage` for access  |
| Refresh token        | HttpOnly cookie (browser manages automatically)        |
| Session list         | React Query (auto refetch on window focus)             |
| Active chat messages | React Query keyed by `session_id`                     |
| News                 | React Query, `staleTime: 60_000` (1 min client-side)  |
| Quiz state           | Local component state + auto-save effect               |

---

## 10. API Surface

| Method | Path                           | Auth | Description                              |
|--------|--------------------------------|------|------------------------------------------|
| POST   | `/auth/register`               | —    | Register new user                        |
| POST   | `/auth/login`                  | —    | Login, receive JWT + refresh cookie      |
| POST   | `/auth/refresh`                | —    | Rotate refresh token, return new access  |
| POST   | `/auth/logout`                 | JWT  | Invalidate refresh token                 |
| GET    | `/auth/me`                     | JWT  | Current user profile                     |
| GET    | `/sessions`                    | JWT  | List user's chat sessions                |
| POST   | `/sessions`                    | JWT  | Create session                           |
| PATCH  | `/sessions/{id}`               | JWT  | Rename session                           |
| DELETE | `/sessions/{id}`               | JWT  | Delete session                           |
| POST   | `/chat`                        | JWT  | Send message in session                  |
| GET    | `/sessions/{id}/messages`      | JWT  | Full message history                     |
| GET    | `/news`                        | JWT  | Cached + fresh news feed                 |
| POST   | `/quiz/generate`               | JWT  | Generate MCQs for a session              |
| GET    | `/quiz/attempt/{id}`           | JWT  | Load saved quiz state                    |
| PUT    | `/quiz/attempt/{id}`           | JWT  | Auto-save answers                        |
| POST   | `/quiz/retry`                  | JWT  | Create new attempt (same questions)      |
| GET    | `/quiz/attempts`               | JWT  | List past attempts for a session         |

---

## 11. Docker Compose Changes

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data

  db:
    # unchanged — existing PostgreSQL service

  web:
    environment:
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - JWT_ACCESS_EXPIRES_MINUTES=15
      - JWT_REFRESH_EXPIRES_DAYS=7
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  frontend:
    # unchanged

volumes:
  pgdata:
  redisdata:
```

---

## 12. New Python Dependencies

```
# Add to requirements.txt
PyJWT>=2.8
bcrypt>=4.1
redis>=5.0
APScheduler>=3.10       # hourly news promotion job
flask-limiter>=3.5      # rate limiting on auth endpoints
```

---

## 13. Security Considerations

| Risk                        | Mitigation                                                        |
|-----------------------------|-------------------------------------------------------------------|
| Brute-force login           | `flask-limiter`: 5 attempts/min per IP on `/auth/login`          |
| Token theft                 | Short-lived access tokens (15 min); refresh token in HttpOnly cookie |
| Password storage            | `bcrypt` with cost factor 12                                      |
| IDOR on sessions/quizzes    | Every DB query filters by `user_id` from JWT — never from body   |
| Prompt injection in MCQ gen | Conversation text is base64-encoded in the prompt context block  |
| News cache poisoning        | RSS feeds are fixed constants; no user-controlled URLs            |
| XSS                         | React escapes by default; `dangerouslySetInnerHTML` is avoided    |

---

## 14. Implementation Phases

### Phase 6 — News Tabs, Discuss & Learning Tree (Week 6–8)
- [ ] DB migration: session hierarchy columns on `chat_sessions`
- [ ] Extend news cache to support category keys (AI / Programming / Political)
- [ ] `POST /news/discuss` — create discussion session from article
- [ ] `POST /sessions/{id}/learn-more` — create sub-session
- [ ] `GET /sessions/{id}/tree` — full ancestry chain
- [ ] `POST /quiz/generate-hierarchical` + `GET /quiz/attempt/{id}/relearn/{q_id}`
- [ ] Frontend: news tab group with Discuss button
- [ ] Frontend: sectioned AI response renderer + Learn More button
- [ ] Frontend: `/learn/:sessionId` route with knowledge tree right pane
- [ ] Frontend: nested session tree in `ChatSidebar`
- [ ] Frontend: enhanced quiz page (relearn panel + correct → Learn More)

### Phase 1 — Auth Foundation (Week 1)
- [ ] DB migration: `users` table
- [ ] `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
- [ ] JWT middleware (`@require_auth` decorator)
- [ ] Frontend: Login page, Register page, auth token storage, route guards

### Phase 2 — Session Management (Week 2)
- [ ] DB migration: `chat_sessions` table
- [ ] Sessions CRUD endpoints
- [ ] Wire `/chat` to require auth + session ownership
- [ ] Auto-title generation after first AI reply
- [ ] Frontend: Left-pane `ChatSidebar` with session grouping

### Phase 3 — Smart News Cache (Week 2–3)
- [ ] Add Redis service to Docker Compose
- [ ] Rewrite `news.py` with day/hour Redis cache strategy
- [ ] DB fallback in `news_cache` table
- [ ] APScheduler job for hourly promotion
- [ ] Update `NewsPanel` to show article timestamps and per-source grouping

### Phase 4 — Knowledge Check (Week 3–4)
- [ ] DB migration: `mcq_attempts` table
- [ ] `POST /quiz/generate` with LLM MCQ generation
- [ ] `PUT /quiz/attempt/{id}` auto-save
- [ ] `POST /quiz/retry`
- [ ] Frontend: Quiz page (`/quiz/:attemptId`)
- [ ] "Check Knowledge" button in `ChatInterface`

### Phase 5 — Polish & Hardening (Week 4–5)
- [ ] Rate limiting on auth endpoints
- [ ] Refresh-token rotation with Redis blocklist
- [ ] Mobile-responsive layout (collapsible panes)
- [ ] Toast notifications (rename, delete, save confirmation)
- [ ] Error boundaries and skeleton loaders throughout

---

## 15. Key Design Decisions

**Why Redis and not in-memory dict for news cache?**
The current `_cache` dict in `news.py` is per-process and lost on every Gunicorn worker restart. Redis survives restarts, is shared across all workers, and naturally supports TTL expiry without manual cleanup.

**Why separate day and hour cache keys?**
It lets the system serve stable older articles from the day cache (zero latency) while still fetching fresh articles for the current hour. A single rolling TTL would either miss recent articles or refetch the full day's news too often.

**Why auto-save MCQ answers on every selection rather than on submit?**
Browser tabs can be closed accidentally, especially since the quiz runs in a separate tab. Auto-save ensures no attempt is lost; the user can return to the same URL and continue exactly where they left off.

**Why does the MCQ prompt filter out names, dates, and locations?**
Those surface details require only short-term recall of the conversation text, not understanding of the technical concepts. The goal is knowledge reinforcement, so questions must target comprehension and reasoning about technology.

**Why store `correct` index server-side and only return it after submission?**
Returning the correct answer in the initial `/quiz/generate` response would allow the frontend (or browser devtools) to reveal answers before the user attempts them. Separating the reveal moment enforces honest self-assessment.

**Why not use streaming for chat responses?**
The current architecture uses LangGraph's `invoke` (blocking). Streaming (`astream_events`) can be added in Phase 5 with minimal backend change (switch to `EventSource` on the frontend), but it is not required for the core feature set.

---

## 16. Multi-Category News Panel

### 16.1 Tab Groups

The right-side news panel becomes a tab group with three categories:

| Tab | Category key | Purpose |
|-----|-------------|---------|
| AI | `ai` | Existing AI/ML research and industry news |
| Programming | `programming` | Software engineering, tools, languages, infrastructure |
| Political | `political` | World affairs, policy, governance — for extracting legal/constitutional learning theories |

### 16.2 RSS Feeds per Category

```python
NEWS_FEEDS = {
    "ai": [
        ("ArXiv AI",         "https://arxiv.org/rss/cs.AI"),
        ("ArXiv ML",         "https://arxiv.org/rss/cs.LG"),
        ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml"),
        ("VentureBeat AI",   "https://venturebeat.com/ai/feed/"),
        ("The Verge AI",     "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ],
    "programming": [
        ("Hacker News",      "https://hnrss.org/frontpage"),
        ("GitHub Blog",      "https://github.blog/feed/"),
        ("Stack Overflow",   "https://stackoverflow.blog/feed/"),
        ("InfoQ",            "https://feed.infoq.com/"),
        ("Dev.to",           "https://dev.to/feed/tag/programming"),
    ],
    "political": [
        ("Reuters",          "https://feeds.reuters.com/reuters/politicsNews"),
        ("BBC News",         "https://feeds.bbci.co.uk/news/politics/rss.xml"),
        ("NPR Politics",     "https://feeds.npr.org/1014/rss.xml"),
        ("The Guardian",     "https://www.theguardian.com/politics/rss"),
        ("AP News",          "https://rsshub.app/apnews/topics/politics"),
    ],
}
```

### 16.3 Cache Key Extension

The existing day/hour cache strategy is extended with a `category` dimension:

```
Redis keys:
  news:day:{YYYY-MM-DD}:{category}       TTL: until midnight UTC
  news:hour:{YYYY-MM-DD-HH}:{category}   TTL: 1 hour

DB news_cache.cache_key examples:
  "2026-05-04:ai"
  "2026-05-04-14:programming"
  "2026-05-04:political"
```

`GET /news?category=ai` (default: `ai`) — clients pass the active tab's category. All three categories are pre-warmed by APScheduler at startup and on each hourly promotion.

### 16.4 Updated NewsPanel Layout

```
┌──────────────────────────────────────┐
│  [AI]  [Programming]  [Political]    │  ← tab group
│                                       │
│  Updated 12 min ago  [↺ Refresh]     │
│                                       │
│  ■ HuggingFace Blog                  │  ← source header
│  ┌──────────────────────────────┐    │
│  │ Introducing SmolVLM          │    │  ← article card
│  │ A compact vision-language... │    │
│  │ 3h ago · [↗ Source]  [Discuss]│  │
│  └──────────────────────────────┘    │
│                                       │
│  ■ ArXiv AI                          │
│  ┌──────────────────────────────┐    │
│  │ Flash Attention 3.0          │    │
│  │ New IO-aware exact attention │    │
│  │ 1h ago · [↗ Source]  [Discuss]│  │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

Each article card exposes:
- Title (linked to original source)
- 2-line summary
- Relative timestamp
- `[↗ Source]` — opens article URL in new tab
- `[Discuss]` — triggers the discussion flow described in §17

---

## 17. Discussion & Learning Session System

### 17.0 Two Entry Points into the Learning Tree

Every knowledge tree has a **root session** at depth 0. There are two ways a root is created:

| Entry Point | How | Session Type | First Response |
|-------------|-----|-------------|----------------|
| **Manual** | User opens a chat and asks a technical question | `regular` | Conversational AI reply + `suggested_topics` chips below the message |
| **News** | User clicks Discuss on a news article | `news_discussion` | Auto-generated sectioned overview (3–5 concept sections, no user prompt needed) |

Both root types support the same **Learn More** → sub-session flow. Clicking any `[Learn More]` chip or button from either root creates a `learn_more` child session in a new tab, extending the tree one level deeper.

**Manual entry flow:**
```
User types: "What is gradient checkpointing?"
AI reply: "Gradient checkpointing is a memory-saving technique..."
Below reply: [Learn More: Backpropagation memory] [Learn More: Mixed-precision training]
User clicks → opens /learn/{sub-session-id} in new tab
```

**News entry flow:**
```
User clicks [Discuss] on "Hugging Face releases SmolVLM"
Backend auto-generates first AI response (sectioned):
  § Vision-Language Model Architectures  [Learn More →]
  § Knowledge Distillation               [Learn More →]
  § Efficient Inference Techniques       [Learn More →]
User clicks → opens /learn/{sub-session-id} in new tab
```

### 17.1 Session Types

`chat_sessions` gains four new columns (Migration 005):

```sql
ALTER TABLE chat_sessions
    ADD COLUMN session_type    VARCHAR(20)  NOT NULL DEFAULT 'regular',
    ADD COLUMN parent_session_id UUID       REFERENCES chat_sessions(id),
    ADD COLUMN root_session_id   UUID       REFERENCES chat_sessions(id),
    ADD COLUMN depth_level       INTEGER    NOT NULL DEFAULT 0,
    ADD COLUMN topic             VARCHAR(500),
    ADD COLUMN news_article_id   VARCHAR(20);

CREATE INDEX idx_sessions_parent ON chat_sessions(parent_session_id);
CREATE INDEX idx_sessions_root   ON chat_sessions(root_session_id);
```

| `session_type` | Created by | `parent_session_id` | `root_session_id` | `depth_level` |
|----------------|-----------|--------------------|--------------------|---------------|
| `regular` | User starts new chat | NULL | NULL | 0 |
| `news_discussion` | Discuss button clicked | NULL | self | 0 |
| `learn_more` | Learn More button clicked | parent session | root session | parent depth + 1 |

### 17.2 Discuss Flow — `POST /news/discuss`

**Request:**
```json
{
  "article_id":   "a3f9b12c4d01",
  "article_title": "US halts military operations after 60 days",
  "article_source": "Reuters",
  "article_summary": "President announced a ceasefire citing constitutional constraints...",
  "article_link":  "https://reuters.com/..."
}
```

**Server logic:**
1. Create `chat_sessions` row: `session_type='news_discussion'`, `news_article_id=article_id`, `root_session_id=self.id`, `depth_level=0`.
2. Auto-title = article title (truncated to 80 chars) — no LLM call needed for the title.
3. Call LangGraph agent with a **discussion system prompt** instructing the AI to extract learning theories (see §18).
4. Store the AI's initial message in the thread.
5. Return `{session_id, thread_id, title, first_response}`.

**First response:** the AI analyses the article and returns a **sectioned response** (see §18). The frontend renders it in the main pane immediately without requiring the user to send a message first.

### 17.3 Learn More Flow — `POST /sessions/{id}/learn-more`

**Request:**
```json
{ "topic": "War Powers Resolution Act of 1973" }
```

**Server logic:**
1. Verify `id` ownership.
2. Load parent session's `root_session_id` and `depth_level`.
3. Create new `chat_sessions` row:
   - `session_type='learn_more'`
   - `parent_session_id = id`
   - `root_session_id = parent.root_session_id`
   - `depth_level = parent.depth_level + 1`
   - `topic = request.topic`
4. Call LangGraph agent with the **learn_more system prompt** — the AI explains the specific topic in sectioned format.
5. Return `{session_id, thread_id, title}`.

**Frontend:** opens `/learn/{session_id}` in a new browser tab (`window.open`).

### 17.4 System Prompts

**Discussion system prompt** (used for `news_discussion` and `learn_more` sessions, first turn only):
```
You are an educational AI that turns news events into structured learning experiences.

Given the following news article [or topic], identify the underlying theories, principles,
laws, constitutional provisions, technical concepts, or scientific mechanisms that explain
WHY this event happened or HOW this concept works.

DO NOT discuss:
  ✗ People's personal actions or decisions
  ✗ Political opinions or value judgements
  ✗ Specific dates, names, or organisations as the subject
  ✓ The underlying laws, rules, frameworks, or mechanisms involved
  ✓ Why those frameworks work the way they do
  ✓ Historical or technical context that explains the principle

Return your response in the following JSON format ONLY — no prose outside the JSON:
{
  "type": "sectioned",
  "intro": "<2–3 sentence overview of what principles this touches on>",
  "sections": [
    {
      "id": "s1",
      "title": "<name of the concept/principle/law>",
      "content": "<3–5 sentence explanation of this concept>",
      "learn_more_topic": "<exact topic string to pass to a follow-up learning session>"
    }
  ],
  "outro": "<1–2 sentences tying the concepts together>"
}

Generate 3–5 sections. Each section must be about a distinct, learnable concept.
```

**For subsequent turns** in a discussion session (when the user types a question), the AI responds normally in plain text (markdown). Only the first AI turn uses the sectioned format.

**Learn_more first turn:** same prompt as discussion, but the context is the `topic` field rather than a news article. Subsequent turns respond normally.

---

## 18. Structured Section Response Format

### 18.1 Backend Parsing

When the backend receives the LangGraph response for a `news_discussion` or `learn_more` first turn:
1. Attempt `json.loads(response)`.
2. Validate schema: `type == 'sectioned'`, `sections` is array, each section has `id`, `title`, `content`, `learn_more_topic`.
3. If valid: store as-is in the message content field (JSONB or JSON string in LangGraph checkpoint).
4. If invalid (LLM didn't follow format): retry once with an explicit format correction prompt. If still invalid, store as plain text with `type: 'plain'`.

### 18.2 Message Content Shape

```typescript
type MessageContent =
  | { type: 'plain';    text: string }
  | { type: 'sectioned'; intro: string; sections: Section[]; outro: string }

interface Section {
  id:                string
  title:             string
  content:           string
  learn_more_topic:  string
}
```

### 18.3 Frontend Rendering

**`SectionedMessage` component** (replaces `Message` for sectioned content):
```
┌────────────────────────────────────────────────────────────┐
│ This news touches on several constitutional principles...  │  ← intro
│                                                             │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ ⚡ War Powers Resolution Act                          │  │  ← section card
│ │                                                       │  │
│ │ The War Powers Resolution of 1973 (50 U.S.C. §§     │  │
│ │ 1541–1548) requires the President to notify Congress │  │
│ │ within 48 hours of committing armed forces...        │  │
│ │                                              [Learn More →] │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ ⚡ Article I, Section 8 — Congressional War Powers   │  │
│ │ ...                                    [Learn More →] │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ These constitutional provisions together form the...       │  ← outro
└────────────────────────────────────────────────────────────┘
```

**[Learn More →]** click handler:
1. Show loading spinner on the button.
2. `POST /sessions/{currentSessionId}/learn-more` with `{topic: section.learn_more_topic}`.
3. `window.open('/learn/{new_session_id}', '_blank', 'noopener,noreferrer')`.
4. Button becomes disabled (greyed, checkmark icon) after opening — prevents duplicate tabs.

---

## 19. Knowledge Tree (Visual Hierarchy Right Pane)

### 19.1 Data Model

**`GET /sessions/{id}/tree`** — returns the full ancestry chain from root to current node.

```json
{
  "current_session_id": "uuid-d2",
  "nodes": [
    {
      "session_id":   "uuid-root",
      "title":        "US halts military operations after 60 days",
      "topic":        null,
      "depth":        0,
      "session_type": "news_discussion",
      "is_current":   false,
      "news_source":  "Reuters"
    },
    {
      "session_id":   "uuid-d1",
      "title":        "War Powers Resolution Act",
      "topic":        "War Powers Resolution Act of 1973",
      "depth":        1,
      "session_type": "learn_more",
      "is_current":   false
    },
    {
      "session_id":   "uuid-d2",
      "title":        "50 U.S.C. §§ 1541–1548 — Statutory Text",
      "topic":        "50 U.S.C. Chapter 33 War Powers",
      "depth":        2,
      "session_type": "learn_more",
      "is_current":   true
    }
  ]
}
```

**Server logic:** walk `parent_session_id` chain upwards from `id` until `parent_session_id IS NULL`. Return array ordered root → current.

### 19.2 Knowledge Tree Component (`KnowledgeTree.tsx`)

Renders in the right pane of `/learn/:id` routes, replacing `NewsPanel`:

```
┌────────────────────────────────────────┐
│  Learning Path                         │
│                                         │
│  📰 US halts military operations...    │  ← depth 0 (news root)
│      Reuters                           │
│         │                              │
│         ▼                              │
│  ⚡ War Powers Resolution Act          │  ← depth 1
│         │                              │
│         ▼                              │
│  ▶ 50 U.S.C. §§ 1541–1548  ← current │  ← depth 2 (highlighted)
│                                         │
│  ─────────────────────────────────────  │
│  3 concepts deep                        │
│                                         │
│  [↩ Back to root]  [↩ Back one level] │
└────────────────────────────────────────┘
```

- Each node is clickable — clicking opens that session in its own tab (or navigates within if it's already open).
- Current node is highlighted with a left border accent.
- Navigation buttons: back to root (opens root session), back one level (opens parent).
- Depth counter: "N concepts deep".

### 19.3 Left Sidebar Hierarchy (`ChatSidebar` — updated)

The sidebar shows all sessions with nesting. `regular` and `news_discussion` sessions appear at the top level. `learn_more` sessions appear indented under their parent.

```
┌──────────────────────────────────────┐
│  Chats          [+ New Chat]         │
│                                       │
│  Today                                │
│  ├─ RAG vs Fine-tuning               │  ← regular
│  │                                    │
│  └─ 📰 US halts military operations │  ← news_discussion (root)
│     ├─ ⚡ War Powers Resolution Act  │  ← learn_more (depth 1)
│     │  └─ ⚡ 50 U.S.C. §§ 1541...  │  ← learn_more (depth 2)
│     └─ ⚡ Congressional War Auth.   │  ← learn_more (depth 1)
│                                       │
│  Yesterday                            │
│  ├─ Attention mechanisms             │
└──────────────────────────────────────┘
```

Session item appearance:
- `regular`: plain title
- `news_discussion`: `📰` prefix + title
- `learn_more`: `⚡` prefix + topic (indented by `depth * 16px`)

The subtree is **collapsible** — clicking the collapse arrow on a `news_discussion` node hides all its children.

`GET /sessions` now returns `parent_session_id`, `root_session_id`, `depth_level`, `session_type` so the frontend can build the tree client-side without a separate API call.

---

## 20. Hierarchical Knowledge Check

### 20.1 Scope

When **[Check Knowledge]** is clicked in any discussion page (`/learn/:id` or the main discuss session in `/app`), the MCQ generation gathers context from the **entire ancestry chain** — root to current — not just the current session.

**`POST /quiz/generate-hierarchical`** — body: `{session_id}`

**Server logic:**
1. Call `GET /sessions/{id}/tree` internally to get all ancestor sessions.
2. For each ancestor, load conversation text from LangGraph state.
3. Extract topics from each level's `topic` field.
4. Concatenate all conversation excerpts (oldest to newest).
5. Call LLM with the MCQ generation prompt, instructing it to generate questions spanning ALL topics in the path.
6. Each generated question must include a `topic` field (the concept it tests) and `source_depth` (which hierarchy level it came from).
7. Validate and store in `mcq_attempts` with `scope_sessions` JSONB = array of session IDs used.

**Updated `mcq_attempts` schema:**
```sql
ALTER TABLE mcq_attempts ADD COLUMN scope_sessions JSONB;
-- e.g. ["uuid-root", "uuid-d1", "uuid-d2"]
```

**Question shape** (extended):
```json
{
  "id":           "q_01",
  "text":         "Under the War Powers Resolution, within how many hours must the President notify Congress of committing armed forces?",
  "options":      ["24 hours", "48 hours", "72 hours", "7 days"],
  "correct":      1,
  "topic":        "War Powers Resolution Act notification requirement",
  "source_depth": 1
}
```

### 20.2 Wrong Answer — Relearn Panel

After quiz submission, for each **wrong** answer:

```
┌──────────────────────────────────────────────────────────┐
│ ✗ Q3. Under the War Powers Resolution...                 │
│                                                           │
│   ○ A  24 hours      ← your answer (red)                │
│   ● B  48 hours      ← correct answer (green)           │
│   ○ C  72 hours                                          │
│   ○ D  7 days                                            │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 📖 Relearn                                        │   │
│  │ The War Powers Resolution (50 U.S.C. § 1543)     │   │
│  │ explicitly requires notification within 48 hours  │   │
│  │ because Congress needed a timeframe short enough  │   │
│  │ to react but long enough for operational security.│   │
│  │                                                   │   │
│  │               [Learn More on this concept →]     │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

**`GET /quiz/attempt/{id}/relearn/{question_id}`** — lazy-loaded when the wrong-answer panel opens:
1. Look up `question.topic` from the stored question.
2. Call LLM with: "In 3–4 sentences, explain why the correct answer to this question is correct and why the alternatives are wrong. Relate it to the underlying principle. Question: {text}. Correct answer: {options[correct]}. Topic: {topic}."
3. Return `{explanation: string}`.
4. Cache the explanation on the attempt row to avoid re-fetching on the same session.

### 20.3 Correct Answer — Learn More Button

After quiz submission, for each **correct** answer:

```
┌──────────────────────────────────────────────────────────┐
│ ✓ Q1. Which article grants Congress war-declaration...   │
│                                                           │
│   ● A  Article I      ← correct (green ✓)              │
│   ○ B  Article II                                        │
│   ○ C  Article III                                       │
│   ○ D  Article IV                                        │
│                                                           │
│           ✅ Correct!  [Explore deeper: Article I →]    │
└──────────────────────────────────────────────────────────┘
```

**[Explore deeper]** click handler:
- `POST /sessions/{attempt.session_id}/learn-more` with `{topic: question.topic}`.
- Opens `/learn/{new_session_id}` in a new tab.
- This Learn More session is a child of the session the quiz was taken from.

---

## 21. Database Schema Additions (Migration 005)

```sql
-- 21.1 Session hierarchy columns
ALTER TABLE chat_sessions
    ADD COLUMN session_type      VARCHAR(20)  NOT NULL DEFAULT 'regular',
    ADD COLUMN parent_session_id UUID         REFERENCES chat_sessions(id),
    ADD COLUMN root_session_id   UUID         REFERENCES chat_sessions(id),
    ADD COLUMN depth_level       INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN topic             VARCHAR(500),
    ADD COLUMN news_article_id   VARCHAR(20);

CREATE INDEX idx_sessions_parent ON chat_sessions(parent_session_id);
CREATE INDEX idx_sessions_root   ON chat_sessions(root_session_id);

-- 21.2 MCQ scope tracking
ALTER TABLE mcq_attempts
    ADD COLUMN scope_sessions JSONB;
    -- ["uuid-root", "uuid-d1", "uuid-d2"] — sessions included in generation

-- 21.3 Relearn explanation cache (avoid repeated LLM calls)
ALTER TABLE mcq_attempts
    ADD COLUMN relearn_cache JSONB DEFAULT '{}';
    -- {"q_01": "explanation text", "q_03": "explanation text"}
```

---

## 22. New & Updated API Surface

### New Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/news?category={ai\|programming\|political}` | JWT | Category-filtered cached news |
| POST | `/news/discuss` | JWT | Create discussion session from article |
| POST | `/sessions/{id}/learn-more` | JWT | Create learn_more sub-session |
| GET | `/sessions/{id}/tree` | JWT | Full ancestry chain (root → current) |
| POST | `/quiz/generate-hierarchical` | JWT | MCQs spanning full ancestor path |
| GET | `/quiz/attempt/{id}/relearn/{question_id}` | JWT | AI relearn explanation for wrong answer |

### Updated Existing Endpoints

| Method | Path | Change |
|--------|------|--------|
| GET | `/sessions` | Now returns `session_type`, `parent_session_id`, `root_session_id`, `depth_level`, `topic` |
| GET | `/news` | `category` query param now required concept; defaults to `ai` |

---

## 23. Updated Frontend Architecture

### 23.1 New Routes

```
/app               → main app (regular + news_discussion sessions, news right pane)
/learn/:sessionId  → learning sub-thread tab (knowledge tree right pane)
/quiz/:attemptId   → quiz page (both flat and hierarchical)
/login             → Login (unchanged)
/register          → Register (unchanged)
```

### 23.2 Right Pane Strategy

| Route | Session type visible | Right pane |
|-------|---------------------|-----------|
| `/app` | regular OR news_discussion | `NewsPanel` (tab group: AI / Programming / Political) |
| `/learn/:id` | learn_more | `KnowledgeTree` |
| `/quiz/:id` | — | N/A (quiz is full-width) |

### 23.3 New & Updated Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `NewsTabs.tsx` | `components/` | Tab group wrapper (AI / Programming / Political) |
| `NewsArticleCard.tsx` | `components/` | Article card with Discuss button |
| `SectionedMessage.tsx` | `components/` | Renders sectioned AI response with Learn More buttons |
| `KnowledgeTree.tsx` | `components/` | Visual hierarchy tree for right pane of `/learn` |
| `TreeNode.tsx` | `components/` | Single node in the hierarchy tree |
| `RelearPanel.tsx` | `components/` | Wrong-answer explanation card in quiz |
| `ChatSidebar.tsx` | `components/` | Updated: nested `learn_more` sessions under parents |
| `useDiscuss.ts` | `hooks/` | POST /news/discuss, open sub-session |
| `useLearnMore.ts` | `hooks/` | POST /sessions/{id}/learn-more, open new tab |
| `useSessionTree.ts` | `hooks/` | GET /sessions/{id}/tree |
| `useHierarchicalQuiz.ts` | `hooks/` | POST /quiz/generate-hierarchical, relearn |

### 23.4 Updated State Management

| Concern | Solution |
|---------|---------|
| Active news tab | Local state in `NewsTabs` (no persistence needed) |
| Discuss loading state | `useDiscuss` hook local state |
| Learn More loading per section | Map of `{sectionId: loading\|done}` in `SectionedMessage` |
| Knowledge tree | React Query keyed by `['tree', sessionId]` |
| Hierarchical quiz | `useHierarchicalQuiz` hook (same pattern as `useQuiz`) |
| Relearn explanations | React Query keyed by `['relearn', attemptId, questionId]` |

---

## 24. Additional Key Design Decisions

**Why does the Discuss button create a session server-side and return the first AI response before the user types anything?**
The first message is synthesised from the article content — it's not a user message. Pre-generating it means the user sees learning content immediately without needing to know what to ask. The session still supports normal follow-up questions.

**Why limit sectioned format to only the first AI turn in a discussion session?**
If every reply were sectioned, the interface would feel rigid. After the first structured overview, the user should be able to ask natural questions and get conversational responses. Subsequent turns use plain text/markdown.

**Why traverse `parent_session_id` chain server-side rather than returning a flat list of session IDs from the client?**
The client could lie about which sessions are ancestors. Server-side traversal starting from the session row guarantees the tree is accurate and that the user owns all nodes in the chain.

**Why cache relearn explanations in `mcq_attempts.relearn_cache` rather than a separate table?**
The relearn explanations are 1:1 with a specific wrong answer in a specific attempt. Storing them inline on the attempt row avoids a join and makes it trivial to load the full quiz state (answers + explanations) in one query.

**Why are [Learn More] buttons disabled after clicking (showing a checkmark instead)?**
This prevents the user from accidentally opening duplicate tabs for the same section. The session was already created; reopening it means they can find it in the sidebar. The visual checkmark also serves as a "this has been explored" signal.

**Why does the hierarchical MCQ span the full root-to-current path, not just the current topic?**
Learning is cumulative. If the user is 3 levels deep studying "50 U.S.C. §§ 1541–1548", they should also be tested on "War Powers Resolution Act" (level 1) and "US military operations" (root context). The quiz reinforces the full reasoning chain, not just the terminal concept.
