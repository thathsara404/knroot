# Knowledge Root — Architecture Document

> **Scope:** Reshaping the existing AI chat agent into a full-featured tech-learning platform with authentication, chat history, smart news caching, a multi-agent knowledge pipeline, and an adaptive knowledge-check system.
>
> **Baseline stack:** Flask · PostgreSQL · Redis · LangGraph (chat) · Google ADK (fact-check) · OpenRouter (DeepSeek) · Google AI (Gemini 2.0 Flash) · Jinja2 + HTMX + Alpine.js · Docker Compose

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
│                   Browser (HTMX + Alpine.js)                      │
│                                                                    │
│  ┌─────────────┐   ┌────────────────────────┐   ┌─────────────┐  │
│  │  Left Pane  │   │     Chat Interface      │   │ Right Pane  │  │
│  │  Chat List  │   │  (Tech Learning Chat)   │   │  AI News    │  │
│  │  (HTMX)     │   │  [Check Knowledge ▶]    │   │  (HTMX)     │  │
│  └─────────────┘   └────────────────────────┘   └─────────────┘  │
│                                  │                                 │
│                    ┌─────────────▼────────────┐                   │
│                    │  Knowledge Check Tab      │                   │
│                    │  (MCQ Interface, HTMX)    │                   │
│                    └──────────────────────────┘                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTPS (full pages + HTMX partial requests)
┌───────────────────────────▼──────────────────────────────────────┐
│             Flask (Python) — Jinja2 SSR + REST API                │
│                                                                    │
│  /pages/*    /auth/*    /sessions/*    /chat/*    /news    /quiz/*│
└──────┬──────────────┬──────────────┬──────────────┬──────────────┘
       │              │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌───▼───┐   ┌─────▼──────┐
  │  Auth   │   │  Session  │  │LangG- │   │   Redis    │
  │(Session)│   │  Manager  │  │raph   │   │(Cache+Sess)│
  └────┬────┘   └─────┬─────┘  └───┬───┘   └─────┬──────┘
       │              │            │              │
  ┌────▼──────────────▼────────────▼──────────────▼──────┐
  │                   PostgreSQL                          │
  │   users · chat_sessions · mcq_attempts · news_cache  │
  └───────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer         | Technology                            | Rationale                                                               |
|---------------|---------------------------------------|-------------------------------------------------------------------------|
| Templates     | Jinja2 (Flask built-in)               | Server-side rendering; no npm, no build step, no separate process       |
| Interactivity | HTMX                                  | Partial page updates via HTML-over-the-wire; loaded from CDN            |
| Client state  | Alpine.js (CDN)                       | Lightweight reactivity for toggles, tabs, dropdowns — no framework      |
| Styling       | Tailwind CSS (CDN)                    | Utility-first CSS; CDN removes all Node.js/npm from the stack           |
| Backend       | Flask 3 (Python)                      | Serves both Jinja2 pages and REST/HTMX partial responses                |
| Validation    | Pydantic v2                           | Request schema validation at the HTTP boundary; `@model_validator` for cross-field rules |
| Auth          | Flask-Session + Redis + bcrypt        | Server-side sessions stored in Redis; signed cookie; simpler than JWT for SSR |
| AI Chat       | LangGraph + OpenRouter                | Existing; graph-based agent with persistent checkpointing               |
| MCQ Generation| OpenRouter LLM (separate call)        | Reuse existing LLM key; dedicated prompt chain                          |
| Cache/Session | Redis 7                               | Shared for news cache (day/hour TTL) and Flask-Session storage          |
| Database      | PostgreSQL 16                         | Existing; adds user, session, and quiz tables                           |
| Container     | Docker Compose                        | Single web service — no separate frontend container required            |

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
│   ├── domain/                         ← Pure Python domain models — no Flask, no DB, no business logic
│   │   └── user.py                     ← User frozen dataclass + to_profile() method
│   │
│   ├── repositories/                   ← All SQL encapsulated here; returns domain objects
│   │   └── user_repository.py          ← UserRepository class + module-level user_repo singleton
│   │
│   ├── api/                            ← One sub-package per API domain; each has its own Blueprint
│   │   ├── auth/
│   │   │   ├── routes.py               ← Blueprint('/auth') — thin handlers, no business logic
│   │   │   ├── schemas.py              ← Pydantic v2 request schemas: RegisterRequest, LoginRequest
│   │   │   └── service.py              ← register_user(), login_user(), get_user()
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
│       ├── 002_chat_sessions.sql       ← sessions table + full hierarchy columns
│       ├── 003_news_cache.sql
│       ├── 004_mcq_attempts.sql        ← includes scope_sessions + relearn_cache columns
│       ├── 005_session_messages.sql
│       ├── 006_cascade_fk.sql
│       └── 007_quiz_session.sql        ← adds linked_attempt_id to chat_sessions
│
├── backend/templates/                  ← Jinja2 HTML templates (served by Flask directly)
│   ├── base.html                       ← HTML shell: head with CDN links, nav, flash messages
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── app/
│   │   └── index.html                  ← 3-pane layout (sidebar + chat + news)
│   ├── learn/
│   │   └── session.html                ← Learning tab (sidebar + chat + knowledge tree)
│   ├── quiz/
│   │   └── attempt.html
│   └── partials/                       ← HTMX partial responses (HTML fragments)
│       ├── session_list.html           ← Sidebar session tree with hierarchy + green-dot indicator
│       ├── message.html                ← Single chat message bubble
│       ├── messages.html               ← Full message history list (session replay)
│       ├── sectioned_message.html      ← Sectioned AI response (Explore / Learn More)
│       ├── news_panel.html             ← 3-tab news panel (AI / Dev / World)
│       ├── topic_news_panel.html       ← Topic-filtered news articles partial
│       ├── knowledge_tree.html         ← Knowledge tree node list
│       ├── knowledge_tree_panel.html   ← Right-pane knowledge tree wrapper
│       ├── quiz_section.html           ← Per-section inline quiz cards
│       ├── quiz_inline.html            ← Full inline quiz loaded into #chat-messages
│       └── fact_check_report.html      ← ADK fact-check verdict card
│
├── backend/static/                     ← Served at /static/ — minimal custom JS only
│   ├── app.js                          ← Alpine appState() + all HTMX event wiring
│   ├── quiz.js                         ← quizState() / quizStateInline() Alpine components
│   ├── auth.js                         ← Login/register page helpers
│   └── toast.js                        ← Lightweight toast notification helper
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
├── e2e/                                ← Playwright E2E specs
├── docs/                               ← Architecture, implementation plan, progress tracker
├── .claude/agents/platform-dev.md     ← Claude Code sub-agent for this project
└── .github/workflows/                  ← CI, code-review, security-review, architecture-review
```

### Module Responsibilities (hard rules)

| File | Owns | Must NOT contain |
|------|------|-----------------|
| `backend/domain/*.py` | Immutable data models (`@dataclass(frozen=True)`), `to_*()`  serialisation helpers | Flask imports, SQL, business logic |
| `backend/repositories/*.py` | All SQL for a domain; returns domain objects | `request`, `g`, business logic, LLM calls |
| `backend/api/*/schemas.py` | Pydantic request validation at the HTTP boundary | SQL, Redis ops, domain logic |
| `backend/api/*/routes.py` | HTTP parsing, schema validation via `_parse()`, response serialisation | SQL, LLM calls, Redis ops, business logic |
| `backend/api/*/service.py` | Business logic, orchestration; calls repositories | `request`, `g` (accepts `user_id` as parameter); no raw SQL |
| `backend/agent/graph.py` | LangGraph graph only | Route code, DB queries |
| `backend/agent/prompts.py` | Prompt string constants | Any logic |
| `backend/core/auth.py` | `@require_auth` / `@require_api_auth` decorators; sets `g.user_id` from session | Business logic beyond session validation |
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
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id         VARCHAR(255) UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    title             VARCHAR(255),                   -- NULL = auto-generate from content
    session_type      VARCHAR(20) NOT NULL DEFAULT 'regular',
    parent_session_id UUID REFERENCES chat_sessions(id),
    root_session_id   UUID REFERENCES chat_sessions(id),
    depth_level       INTEGER NOT NULL DEFAULT 0,
    topic             VARCHAR(500),
    news_article_id   VARCHAR(20),
    linked_attempt_id UUID,                          -- points to mcq_attempts row for quiz sessions
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    last_message_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_last ON chat_sessions(user_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_parent    ON chat_sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_root      ON chat_sessions(root_session_id);
```

`linked_attempt_id` links a quiz-type session (created by "Check Knowledge") to its corresponding `mcq_attempts` row, enabling direct navigation from sidebar to a specific quiz attempt.

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

Authentication uses **server-side session cookies** via Flask-Session backed by Redis. No JWT issuance, no refresh token rotation — the session stores the user ID directly in Redis; the browser receives only a signed session ID cookie.

### 5.1 Registration — `POST /auth/register`

**Request (HTML form or JSON):**
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
1. Validate all fields (username: 3–50 chars, alphanumeric+underscore; email: RFC 5322; phone: E.164 optional; password: min 8 chars, at least one digit).
2. Hash password with `bcrypt` (cost factor 12).
3. Insert into `users`.
4. `session['user_id'] = str(user['id'])`, `session.permanent = True`.
5. On success: redirect to `/app` (PRG pattern). On HTMX request, return `HX-Redirect: /app` header. On failure: re-render form with error context, or return HTML error fragment.

### 5.2 Login — `POST /auth/login`

**Request (HTML form or JSON):**
```json
{ "identifier": "alicesmith",  "password": "••••••••" }
```
`identifier` can be username **or** email.

**Server logic:**
1. Look up user by username OR email.
2. `bcrypt.checkpw(password, hash)` — constant-time comparison.
3. `session['user_id'] = str(user['id'])`, `session.permanent = True`.
4. Redirect to `/app`. On failure: re-render login template with error message.

### 5.3 Logout — `POST /auth/logout`

`session.clear()` — this deletes the session data from Redis. Redirect to `/login`.

### 5.4 Session Storage (Flask-Session + Redis)

```python
# backend/config.py
SESSION_TYPE = 'redis'               # stored in Redis, not in the cookie
SESSION_COOKIE_NAME = 'knroot_sess'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True         # False in development
PERMANENT_SESSION_LIFETIME = timedelta(days=7)
SESSION_USE_SIGNER = True            # HMAC-sign the session ID
SESSION_REFRESH_EACH_REQUEST = True  # renew TTL on every request
```

The cookie contains only a signed session ID. The payload (`user_id`) lives in Redis under key `session:<id>`. Session expiry is enforced by Redis TTL.

### 5.5 Auth Middleware (`backend/core/auth.py`)

Two decorators — one for page routes (redirects), one for HTMX/API endpoints (returns 401):

```python
def require_auth(f):
    """Page routes — redirects to /login if unauthenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('pages.login'))
        g.user_id = session['user_id']
        return f(*args, **kwargs)
    return decorated

def require_api_auth(f):
    """HTMX/JSON endpoints — returns 401 JSON if unauthenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        g.user_id = session['user_id']
        return f(*args, **kwargs)
    return decorated
```

`g.user_id` is set exclusively from the server-side session — never from client-supplied request data.

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

### 6.2 Topic-Specific News Cache

When a user asks about a specific topic in the news panel, the backend also maintains a short-lived topic cache:

```
Redis keys:
  news:topic:{sha256(topic)[:12]}:30    TTL: 30 min  — exact topic match
  news:topic:{sha256(topic)[:12]}:10    TTL: 10 min  — fallback / partial match
```

Served via `GET /news/topic-partial?topic=<text>`. Falls back to the category cache if no topic-specific articles are available.

**`_age_hours` handling:** articles computed during RSS fetch include a transient `_age_hours` field used for in-flight filtering. This field is **stripped before any Redis `setex` call** (both in `cache.py`'s `set_cache()` and in `service.py`'s `get_topic_news()`) so stale age values are never stored in the cache.

### 6.3 Article Data Shape

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

The quiz loads **inline** into the centre chat pane (`#chat-messages`) — no new tab is opened.

```
Chat Pane (#chat-messages)
    │
    │  Click [🧠 Check Knowledge]  — button disabled while any content is loading
    │  POST /quiz/generate {session_id}
    │  ← {attempt_id, questions, quiz_session_id}
    │
    │  HTMX GET /quiz/{attempt_id}/partial → loads quiz_inline.html into #chat-messages
    │
    │  User answers MCQ cards
    │  Auto-save: PUT /quiz/attempt/{id} {answers}  (debounced 500ms)
    │
    │  Submit → PUT /quiz/attempt/{id} {answers, completed: true}
    │  ← {score, questions with correct fields}
    │  Score banner displayed inline
    │
    │  [Retry] → POST /quiz/retry → HTMX reloads fresh quiz inline
    │
    │  [🧠 Follow-up Quiz]  (shown after a quiz is submitted)
    │  POST /quiz/generate-followup {attempt_id}
    │  ← new attempt focusing on wrong answers from previous attempt
    │  HTMX GET /quiz/{new_attempt_id}/partial → loads new inline quiz
```

**Button disable rules:**
- `[🧠 Check Knowledge]` / `[🧠 Follow-up Quiz]` is disabled whenever `chatLoading`, `contentBusy`, or a quiz is currently loaded but not yet submitted (`quizViewState && !quizViewState.submitted`).
- Tooltip shows "Submit the quiz first" when blocked by an unsubmitted quiz.

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

- User clicks **[Retry]**: frontend calls `POST /quiz/retry` with `{ "attempt_id": "..." }`.
- Backend creates a **new `mcq_attempts` row** with the same questions (no re-generation cost) and resets answers/score.
- Returns the new `attempt_id`; HTMX reloads the inline quiz partial.
- Previous attempt is preserved — users can review old scores via `GET /quiz/attempts?session_id=...`.

### 8.6 Follow-up Quiz

After a quiz is submitted, the **[🧠 Follow-up Quiz]** button becomes available:

- Frontend calls `POST /quiz/generate-followup` with `{ "attempt_id": "..." }`.
- Backend builds an attempt summary listing each question, the user's answer, and the correct answer.
- Calls the LLM with `MCQ_FOLLOWUP_PROMPT` which instructs it to:
  - Prioritise concepts the user answered **wrong** — probe them at a deeper level.
  - For correctly-answered concepts, test related or adjacent ideas.
  - Generate exactly 8 new questions; no question text may be reused verbatim.
- Creates a new sibling `chat_session` (under the same parent content session) with title `"Quiz: … (follow-up)"` and a new `mcq_attempts` row.
- Returns `{attempt_id, quiz_session_id, questions, session_id}`; HTMX loads the new inline quiz.

**`MCQ_FOLLOWUP_PROMPT`** lives in `backend/agent/prompts.py`. The follow-up generator (`generate_mcq_followup()`) lives in `backend/api/quiz/generator.py` and uses the same retry-twice validation pattern as `generate_mcq()`.

---

## 9. Frontend Architecture

Flask serves all HTML pages through Jinja2 templates. Dynamic interactions use HTMX for partial page replacements without full reloads. Client-side reactivity (toggles, tabs, dropdowns) uses Alpine.js. Tailwind CSS is loaded from CDN. No Node.js, npm, or build step required.

### 9.1 Page / Route Map (`backend/api/pages/routes.py`)

```
GET /                   → redirect to /app if session active, else /login
GET /login              → render auth/login.html
GET /register           → render auth/register.html
GET /app                → render app/index.html  [require_auth]
GET /app/session/<id>   → render app/index.html, preload session  [require_auth]
GET /learn/<id>         → render learn/session.html  [require_auth]
GET /quiz/<id>          → render quiz/attempt.html  [require_auth]
```

### 9.2 Three-Pane Layout

The left and right panes are **user-resizable** via drag handles. Alpine.js tracks `sidebarWidth` and `rightPanelWidth` with pixel values; CSS transitions animate open/close.

```
┌──────────────┬──┬───────────────────────────┬──┬──────────────┐
│  LEFT PANE   │▌ │       CENTRE PANE         │▌ │  RIGHT PANE  │
│  resizable   │  │  flex-1, min-w-0          │  │  resizable   │
│              │  │                           │  │              │
│ ● New Chat   │  │  Message thread           │  │  AI News     │
│              │  │  (HTMX beforeend swap     │  │  (HTMX load  │
│ Session list │  │   on chat submit)         │  │   on mount)  │
│ (HTMX load)  │  │                           │  │              │
│              │  │  Inline quiz in           │  │  Tab group:  │
│ Green dot on │  │  #chat-messages when      │  │  AI / Dev /  │
│ active thread│  │  "Check Knowledge"        │  │  World       │
│ (bubbles to  │  │  is clicked               │  │  (Alpine.js) │
│  parent when │  │                           │  │              │
│  collapsed)  │  │  [🧠 Check Knowledge]     │  │  Loading     │
│              │  │  (disabled during loads)  │  │  overlay     │
└──────────────┴──┴───────────────────────────┴──┴──────────────┘
           resize handles
```

**Left pane** — `partials/session_list.html` (HTMX-loaded):
- Groups sessions by: Today / Yesterday / This Week / Older.
- Session item: title (auto or user-set) + relative timestamp.
- Hierarchical: `news_discussion` roots are collapsible; `learn_more` children indented.
- **Green dot active indicator**: a `.knr-dot` `<span>` inside each session row `<a data-session-id="...">`. `window._reapplyActiveDot()` highlights the active row. When a parent is collapsed and the active session is a hidden descendant, the dot appears on the nearest visible ancestor row (softer shade). Triggered by `setActiveSession()`, HTMX `afterSettle` on `#session-list`, and collapse-toggle clicks.
- Skeleton placeholder rendered server-side while loading.

**Centre pane** — messages + input bar:
- `[🧠 Check Knowledge]` strip shown only when a session is active (`x-show="activeSessionId"`).
- Quiz loads **inline** into `#chat-messages` (no new tab).
- Button label toggles: "🧠 Check Knowledge" → "🧠 Follow-up Quiz" after a quiz is submitted.
- Button disabled via `:disabled="quizLoading || chatLoading || contentBusy || (quizViewState && !quizViewState.submitted)"`.
- **`contentBusy`** — single Alpine boolean set `true` during all content-loading operations (chat send, quiz generation, Explore, section quiz, Discuss, sidebar session switch, learn-more creation). Both Send and Check Knowledge buttons bind to it.

**Right pane** — `partials/news_panel.html` (HTMX-loaded):
- News tab group controlled by Alpine.js `x-data`.
- Each tab triggers `hx-get=/news/partial?category=<tab>` on activate.
- **Loading overlay**: absolutely-positioned spinner (`z-20`, `x-show="newsPanelLoading"`) covers the right pane while news is fetching, leaving existing content visible underneath.

### 9.3 HTMX Interaction Patterns

**Login/Register (Post → Redirect → Get):**
```html
<form hx-post="/auth/login" hx-target="#form-error" hx-swap="innerHTML">
  ...
</form>
```
Success: server returns `HX-Redirect: /app` header → browser navigates.
Failure: server returns HTML error fragment → HTMX swaps into `#form-error`.

**Chat submission:**
```html
<form hx-post="/chat" hx-target="#messages" hx-swap="beforeend"
      hx-on::after-request="this.reset()">
  <input type="hidden" name="session_id" value="{{ session_id }}">
  <textarea name="message" required></textarea>
  <button type="submit">Send</button>
</form>
```
`POST /chat` returns a rendered `partials/message.html` fragment containing both the user message and the AI response.

**Quiz MCQ auto-save:**
```html
<input type="radio" name="q_01" value="1"
       hx-post="/quiz/attempt/{{ attempt_id }}/answer"
       hx-vals='{"question_id": "q_01", "option": 1}'
       hx-trigger="change">
```

### 9.4 Alpine.js for Client State

```html
<!-- Show/hide password -->
<div x-data="{ show: false }">
  <input :type="show ? 'text' : 'password'" name="password">
  <button @click="show = !show" type="button" :aria-label="show ? 'Hide' : 'Show'">
    <span x-text="show ? 'Hide' : 'Show'"></span>
  </button>
</div>

<!-- News tab group -->
<div x-data="{ tab: 'ai' }">
  <button @click="tab = 'ai'" :class="{'active': tab === 'ai'}">AI</button>
  <button @click="tab = 'programming'" :class="{'active': tab === 'programming'}">Programming</button>
  <div x-show="tab === 'ai'"
       hx-get="/news/partial?category=ai" hx-trigger="intersect once"></div>
  <div x-show="tab === 'programming'"
       hx-get="/news/partial?category=programming" hx-trigger="intersect once"></div>
</div>
```

### 9.5 State Management

| Concern                  | Solution                                                              |
|--------------------------|-----------------------------------------------------------------------|
| Auth / current user      | Flask session (server-side, Redis-backed cookie)                      |
| Session list             | HTMX loads `/sessions/partial` on mount + `sessionListRefresh` event  |
| Active chat messages     | HTMX loads `/sessions/<id>/messages/partial` on select                |
| News content             | HTMX loads `/news/partial?category=<tab>` on tab activate             |
| Active news tab          | Alpine.js `x-data` local state                                        |
| Active session highlight | `window._activeSessionId` + `window._reapplyActiveDot()` DOM function |
| Content loading lock     | Alpine `contentBusy` boolean — set by HTMX body listeners + JS calls  |
| News panel loading       | Alpine `newsPanelLoading` boolean — overlay spinner in right pane      |
| Quiz inline state        | `window.dispatchEvent(CustomEvent('quiz-view-changed'))` from `quiz.js` → `appState.quizViewState` |
| Quiz answers             | Alpine state in `quizState()` component; auto-saved to DB via `PUT /quiz/attempt/{id}` |
| Pane widths              | Alpine `sidebarWidth` / `rightPanelWidth` — mousedown drag handlers    |
| UI state                 | Alpine.js `x-data` per component (toggles, dropdowns)                 |

**`quizViewState` event flow:** `quiz.js`'s `quizState()` component dispatches `quiz-view-changed` on `init()` and after `submitQuiz()`. `appState().init()` listens for this event and stores `{isQuiz, attemptId, quizSessionId, parentSessionId, submitted, score}` in `quizViewState`. The `htmx:afterSettle` handler clears `quizViewState` when `#chat-messages` no longer contains a `.knr-quiz-root` element.

---

## 10. API Surface

### Page Routes

| Method | Path               | Auth    | Description                        |
|--------|--------------------|---------|------------------------------------|
| GET    | `/`                | —       | Redirect to `/app` or `/login`     |
| GET    | `/login`           | —       | Login page                         |
| GET    | `/register`        | —       | Register page                      |
| GET    | `/app`             | Session | Main 3-pane dashboard              |
| GET    | `/learn/<id>`      | Session | Learning sub-thread page           |
| GET    | `/quiz/<id>`       | Session | Full-page quiz (standalone)        |

### Auth

| Method | Path             | Auth    | Description                                         |
|--------|------------------|---------|-----------------------------------------------------|
| POST   | `/auth/register` | —       | Register new user, set session cookie               |
| POST   | `/auth/login`    | —       | Authenticate, set session cookie, redirect to /app  |
| POST   | `/auth/logout`   | Session | Clear session, redirect to /login                   |
| GET    | `/auth/me`       | Session | Current user profile (JSON)                         |

### Sessions

| Method | Path                                    | Auth    | Description                            |
|--------|-----------------------------------------|---------|----------------------------------------|
| GET    | `/sessions`                             | Session | List user's sessions (with hierarchy)  |
| POST   | `/sessions`                             | Session | Create session                         |
| PATCH  | `/sessions/<id>`                        | Session | Rename session                         |
| DELETE | `/sessions/<id>`                        | Session | Delete session                         |
| GET    | `/sessions/partial`                     | Session | HTMX partial — sidebar session list    |
| GET    | `/sessions/<id>/messages`               | Session | Full message history (JSON)            |
| GET    | `/sessions/<id>/messages/partial`       | Session | HTMX partial — message list HTML       |
| GET    | `/sessions/<id>/tree`                   | Session | Full ancestry chain (root → current)   |
| POST   | `/sessions/<id>/learn-more`             | Session | Create learn_more sub-session          |

### Chat

| Method | Path    | Auth    | Description                                        |
|--------|---------|---------|----------------------------------------------------|
| POST   | `/chat` | Session | Send message; returns rendered message partial     |

### News

| Method | Path                             | Auth    | Description                                           |
|--------|----------------------------------|---------|-------------------------------------------------------|
| GET    | `/news`                          | Session | Cached + fresh news feed (JSON)                       |
| GET    | `/news/partial`                  | Session | HTMX partial — news panel HTML (`?category=ai`)       |
| GET    | `/news/topic-partial`            | Session | HTMX partial — topic-filtered articles (`?topic=...`) |
| POST   | `/news/discuss`                  | Session | Create news_discussion session from article           |
| POST   | `/news/fact-check`               | Session | ADK fact-check pipeline — returns verdict card HTML   |

### Quiz

| Method | Path                                       | Auth    | Description                                           |
|--------|--------------------------------------------|---------|-------------------------------------------------------|
| POST   | `/quiz/generate`                           | Session | Generate MCQs for a session                           |
| POST   | `/quiz/generate-followup`                  | Session | Generate follow-up quiz targeting previous weak areas |
| GET    | `/quiz/<attempt_id>/partial`               | Session | HTMX partial — inline quiz loaded into #chat-messages |
| GET    | `/quiz/attempt/<id>`                       | Session | Load saved quiz state (JSON)                          |
| PUT    | `/quiz/attempt/<id>`                       | Session | Auto-save answers; `completed: true` submits quiz     |
| POST   | `/quiz/retry`                              | Session | Create new attempt (same questions)                   |
| GET    | `/quiz/attempts`                           | Session | List past attempts for a session                      |
| GET    | `/quiz/attempt/<id>/relearn/<question_id>` | Session | AI relearn explanation for a wrong answer             |

---

## 11. Docker Compose

The frontend container is removed. Flask now serves both the API and HTML pages from one process. The `web` service is the only application container.

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data

  db:
    # unchanged — existing PostgreSQL service

  web:
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}                # signs session cookies
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}                # DeepSeek for chat / discuss / curation
      - OPENROUTER_MODEL=${OPENROUTER_MODEL:-deepseek/deepseek-chat}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}                        # optional — Gemini for fact-check (Layer 5)
      - FACT_CHECK_MODEL=${FACT_CHECK_MODEL:-gemini-2.0-flash}  # Gemini model used by ADK fact-check
      - FLASK_ENV=${FLASK_ENV:-production}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  pgdata:
  redisdata:
```

---

## 12. Python Dependencies

```
# requirements.txt
flask>=3.0
flask-session>=0.8      # server-side sessions backed by Redis
bcrypt>=4.1             # password hashing (cost factor 12)
redis>=5.0              # session storage + news cache
APScheduler>=3.10       # hourly news promotion job
flask-limiter>=3.5      # rate limiting on auth endpoints
```

`PyJWT` is removed — session cookies replace JWT entirely.

---

## 13. Security Considerations

| Risk                        | Mitigation                                                        |
|-----------------------------|-------------------------------------------------------------------|
| Brute-force login           | `flask-limiter`: 5 attempts/min per IP on `/auth/login`                      |
| Session hijacking           | Sessions stored server-side in Redis; signed cookie ID; `HttpOnly`+`Secure`  |
| CSRF                        | Flask-WTF CSRF tokens on all state-changing forms; HTMX includes `X-CSRFToken` header |
| Password storage            | `bcrypt` with cost factor 12                                                  |
| IDOR on sessions/quizzes    | Every DB query filters by `user_id` from `g.user_id` (set from session) — never from body |
| Prompt injection in MCQ gen | Conversation text wrapped in `<conversation>…</conversation>` delimiter       |
| News cache poisoning        | RSS feeds are fixed constants in `feeds.py`; no user-controlled URLs          |
| XSS                         | Jinja2 auto-escapes all template variables by default; `| safe` only for trusted content |

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
┌──────────────────────────────────────────┐
│  [AI]   [Dev]   [World]                  │  ← tab group
│                                           │
│  ┌──────────────────────────────────┐    │
│  │ HuggingFace Blog · 3h ago        │    │  ← source · date header
│  │                                  │    │
│  │ Introducing SmolVLM              │    │  ← title
│  │ A compact vision-language model  │    │  ← description
│  │ for on-device inference...       │    │
│  │                                  │    │
│  │ [Read article] [Explore] [Fact ✓]│    │  ← action row
│  └──────────────────────────────────┘    │
│                                           │
│  ┌──────────────────────────────────┐    │
│  │ ArXiv AI · 1h ago                │    │
│  │ Flash Attention 3.0              │    │
│  │ New IO-aware exact attention...  │    │
│  │ [Read article] [Explore] [Fact ✓]│    │
│  └──────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

Each article card exposes three actions:
- `[Read article]` — opens article URL in a new tab (`rel="noopener noreferrer"`)
- `[Explore]` — triggers Layer 4 (`POST /news/discuss`); creates a `news_discussion` session and renders the sectioned response in the chat pane
- `[Fact Check]` — triggers Layer 5 (`POST /news/fact-check`); runs the ADK Search → Verdict pipeline and renders a verdict card in-place under the article (verified / disputed / unverifiable claims with source links)

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
| GET | `/news?category={ai\|programming\|political}` | Session | Category-filtered cached news |
| POST | `/news/discuss` | Session | Create discussion session from article |
| POST | `/sessions/{id}/learn-more` | Session | Create learn_more sub-session |
| GET | `/sessions/{id}/tree` | Session | Full ancestry chain (root → current) |
| POST | `/quiz/generate-hierarchical` | Session | MCQs spanning full ancestor path |
| GET | `/quiz/attempt/{id}/relearn/{question_id}` | Session | AI relearn explanation for wrong answer |

### Updated Existing Endpoints

| Method | Path | Change |
|--------|------|--------|
| GET | `/sessions` | Now returns `session_type`, `parent_session_id`, `root_session_id`, `depth_level`, `topic` |
| GET | `/news` | `category` query param now required concept; defaults to `ai` |

---

## 23. Phase 6 Frontend Architecture (SSR)

### 23.1 New Page Routes

```
GET /app               → main app (sidebar + chat + news tab group)
GET /learn/<sessionId> → learning sub-thread (sidebar + chat + knowledge tree)
GET /quiz/<attemptId>  → quiz page (full-width MCQ cards)
GET /login             → Login
GET /register          → Register
```

### 23.2 Right Pane Strategy

| Route | Session type visible | Right pane template |
|-------|---------------------|---------------------|
| `/app` | regular OR news_discussion | `partials/news_panel.html` (tab group: AI / Programming / Political) |
| `/learn/<id>` | learn_more | `partials/knowledge_tree.html` |
| `/quiz/<id>` | — | N/A (full-width) |

### 23.3 New Templates and Partials

| Template | Purpose |
|----------|---------|
| `partials/news_tabs.html` | Tab group: AI / Programming / Political (Alpine.js tabs + HTMX per-tab load) |
| `partials/news_article_card.html` | Article card with Discuss button (HTMX post) |
| `partials/sectioned_message.html` | Sectioned AI response with Learn More buttons |
| `partials/knowledge_tree.html` | Visual hierarchy tree (server-rendered nodes) |
| `partials/relearn_panel.html` | Wrong-answer explanation (HTMX lazy-load) |
| `partials/session_list.html` | Updated: nested learn_more sessions under parents |

### 23.4 Phase 6 State Management

| Concern | Solution |
|---------|---------|
| Active news tab | Alpine.js `x-data` local state |
| Discuss loading state | HTMX `hx-indicator` on the Discuss button |
| Learn More loading per section | Alpine.js per-button state `{loading, opened}` |
| Knowledge tree | Server-rendered via `GET /sessions/<id>/tree`; HTMX on mount |
| Hierarchical quiz | Same HTMX MCQ pattern; `POST /quiz/generate-hierarchical` |
| Relearn explanations | HTMX lazy-load `GET /quiz/attempt/<id>/relearn/<q_id>` on expand |

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

---

## 25. AI Architecture

The system has **five distinct AI/data layers** that operate independently. The originally-planned ADK Research → FactCheck → Editor pipeline was **not shipped** — what is implemented is the simpler, more direct architecture below.

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: APScheduler (hourly RSS fetch — NO AI)                │
│  feedparser → 3 articles per source × 5 sources × 3 categories  │
│  Redis: news:hour:YYYY-MM-DD-HH:category (TTL 1h)               │
│         news:day:YYYY-MM-DD:category    (TTL 24h)               │
│  Jobs: promote_hour_to_day + fetch_and_cache (every hour)       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ cached articles
┌─────────────────────────────────▼───────────────────────────────┐
│  Layer 2: AI News Curation (DeepSeek via OpenRouter, hourly)    │
│  curate_with_ai() in backend/api/news/cache.py                  │
│  Ranks articles by importance for technical audience            │
│  NEWS_CURATION_PROMPT → reorders cached list                    │
│  Falls back to original RSS order on LLM failure                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: LangGraph ReAct Agent (DeepSeek via OpenRouter)       │
│  POST /chat → compiled.invoke() → PostgreSQL checkpoint          │
│  Single StateGraph in backend/agent/graph.py:                    │
│    nodes: agent (DeepSeek call) + tools (ToolNode)               │
│  Tool: get_latest_ai_news (reads Redis cache mid-conversation)   │
│  First message of new session: top 5 cached headlines injected   │
│  Used for: regular chat, news_discussion follow-up turns         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Direct LLM Pipeline (DeepSeek) — Explore / Learn More │
│  _run_discussion_pipeline() in backend/api/discuss/service.py   │
│  Direct DeepSeek call (NO LangGraph graph traversal)            │
│  DISCUSSION_PROMPT / LEARN_MORE_PROMPT → sectioned JSON          │
│  POST /news/discuss              (Explore button on article)     │
│  POST /sessions/<id>/learn-more  (Explore on a section card)     │
│  First exchange stored in LangGraph checkpoint via update_state │
│  (no second LLM call to persist — direct write-through)         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Layer 5: ADK Fact-Check Pipeline (Gemini 2.0 Flash, on-demand) │
│  backend/agent/pipeline.py — SequentialAgent with 2 sub-agents: │
│    1. Search Agent — Gemini + native google_search ADK tool      │
│       searches Google for 3–4 key claims in the article          │
│    2. Verdict Agent — Gemini evaluates findings, rates each      │
│       claim (verified/disputed/unverifiable), returns JSON       │
│  Triggered ONLY by [Fact Check] button on news article cards    │
│  Requires GOOGLE_API_KEY; gracefully returns error card if unset│
│  Completely separate from chat / discuss flow                   │
└─────────────────────────────────────────────────────────────────┘
```

### 25.1 Layer 1 — Hourly RSS Cache (no AI)

`feedparser` pulls **3 articles per source** from RSS feeds (5 sources × 3 categories = 15 articles per category). Two APScheduler jobs run hourly:

| Job | Purpose |
|-----|---------|
| `promote_hour_to_day` | Merges the previous hour's cache into the day cache and extends TTL until midnight UTC |
| `fetch_and_cache` | Fetches fresh RSS articles, dedupes by link, runs Layer 2 curation, writes to Redis (and the `news_cache` DB fallback) |

Redis keys:
- `news:hour:{YYYY-MM-DD-HH}:{category}` — TTL 1 hour
- `news:day:{YYYY-MM-DD}:{category}` — TTL until midnight UTC

### 25.2 Layer 2 — AI News Curation

After each RSS fetch, `curate_with_ai()` in `backend/api/news/cache.py` calls DeepSeek with `NEWS_CURATION_PROMPT`. The model ranks the freshly fetched articles by importance for a technical audience and returns a re-ordered list. The cache is then rewritten so the most impactful headlines appear first. If the LLM call fails, the original RSS order is preserved (no service interruption).

### 25.3 Layer 3 — LangGraph ReAct Agent

The chat agent in `backend/agent/graph.py` is a single `StateGraph` with two nodes:

| Node | Role |
|------|------|
| `agent` | Calls DeepSeek with the conversation history + system prompt |
| `tools` | LangGraph `ToolNode` that executes any tool calls returned by the agent |

A conditional edge routes from `agent` → `tools` when the model requests a tool, then back to `agent`. The single tool, `get_latest_ai_news`, reads from the Redis cache (Layer 1) so the agent can reference current headlines mid-conversation.

**State persistence:** all conversation history is stored via `PostgresSaver` (LangGraph's PostgreSQL checkpointer). Sessions survive server restarts; the checkpointer is keyed by `thread_id`, which equals the `chat_sessions.id` row.

**News injection:** when a session has no prior messages, the first `system` message includes the top 5 cached AI headlines so the agent has fresh context without needing to call the tool.

This layer powers `POST /chat` and any follow-up turns inside a `news_discussion` session.

### 25.4 Layer 4 — Direct LLM Pipeline (Explore / Learn More)

The Explore and Learn More flows do **not** go through LangGraph. `_run_discussion_pipeline()` in `backend/api/discuss/service.py` makes a direct DeepSeek call with the appropriate prompt:

- `DISCUSSION_PROMPT` — for `POST /news/discuss` (Explore button on a news card)
- `LEARN_MORE_PROMPT` — for `POST /sessions/<id>/learn-more` (Explore on a section card)

Both prompts return **structured sectioned JSON** (intro, 3–5 sections, outro — see §18). After the call, the response is validated and the first exchange is written into the LangGraph checkpoint via `update_state` so subsequent turns in the session can use Layer 3 with the full history. There is no second LLM call to persist the message — the direct call's output is the stored content.

### 25.5 Layer 5 — ADK Fact-Check Pipeline (on-demand)

`backend/agent/pipeline.py` defines a Google ADK `SequentialAgent` with two sub-agents, both running Gemini 2.0 Flash:

| Sub-agent | Tool | Output |
|-----------|------|--------|
| **Search Agent** | Native `google_search` ADK tool | Raw search results for 3–4 key claims extracted from the article |
| **Verdict Agent** | None (LLM-only reasoning) | Structured JSON: each claim rated `verified` / `disputed` / `unverifiable` with source links |

Triggered **only** by the `[Fact Check]` button on news article cards (`POST /news/fact-check`). Requires `GOOGLE_API_KEY` to be set; without it the endpoint returns a graceful error card so the rest of the app keeps working. This pipeline is completely isolated from the chat/discuss flow — it never writes to `chat_sessions` or LangGraph state.

### 25.6 Agent Package Structure

```
backend/agent/
├── graph.py         ← LangGraph StateGraph (Layer 3 — chat agent + checkpointer)
├── pipeline.py      ← Google ADK SequentialAgent (Layer 5 — Search + Verdict)
├── prompts.py       ← All prompt constants:
│                       SYSTEM_PROMPT (Layer 3 chat)
│                       AUTO_TITLE_PROMPT
│                       NEWS_CURATION_PROMPT (Layer 2)
│                       DISCUSSION_PROMPT (Layer 4 — Explore)
│                       LEARN_MORE_PROMPT (Layer 4 — Learn More)
│                       MCQ_GENERATION_PROMPT
│                       MCQ_FOLLOWUP_PROMPT  ← follow-up quiz targeting weak areas
│                       RELEARN_PROMPT
│                       FACT_CHECK_SEARCH_PROMPT (Layer 5)
│                       FACT_CHECK_VERDICT_PROMPT (Layer 5)
└── tools.py         ← LangChain @tool: get_latest_ai_news
```

**`MCQ_FOLLOWUP_PROMPT`** wraps the previous attempt summary (per-question correct/wrong breakdown) and instructs the LLM to generate 8 new questions that probe wrong answers at a deeper level and test adjacent ideas for correct answers. No question text from the previous attempt may be reused verbatim.

### 25.7 Three-Pane Layout

The app uses a full-screen three-pane layout. The left sidebar is collapsible and all three panes are **user-resizable** via drag handles:

```
┌──────────────────────────────────────────────────────────────────────┐
│  [☰]  Knowledge Root                                    Sign Out     │  ← nav
├──────────────────┬──┬──────────────────────────────┬──┬─────────────┤
│  LEFT SIDEBAR    │▌ │      CHAT (centre)            │▌ │  NEWS PANE  │
│  resizable       │  │      flex-1                   │  │  resizable  │
│  (toggleable)    │  │                               │  │             │
│                  │  │  Message thread               │  │ [AI][Dev]   │
│  [+ New Chat]    │  │  (HTMX append)                │  │ [World]     │
│  ──────────      │  │                               │  │ ──────────  │
│  Today           │  │  Inline quiz inside           │  │ Article     │
│  ├─ Chat A ●     │  │  #chat-messages               │  │ cards       │
│  │  ├─ Sub 1     │  │  (.knr-quiz-root)             │  │             │
│  │  └─ Sub 2     │  │                               │  │ [Read]      │
│  └─ 📰 News X    │  │  [🧠 Check Knowledge]         │  │ [Explore]   │
│     ├─ ⚡ Sub 1  │  │  (disabled during loads or    │  │ [Fact ✓]    │
│  Yesterday       │  │   unsubmitted quiz)            │  │             │
│  └─ Chat B       │  │                               │  │ Loading     │
│                  │  │  [Type a message...]   [Send] │  │ overlay     │
└──────────────────┴──┴──────────────────────────────┴──┴─────────────┘
```

**Sidebar toggle** (Alpine.js + CSS transition):
- `[☰]` button dispatches `toggle-sidebar` event; sidebar width transitions to 0.
- Collapsible: each `news_discussion` root has an expand/collapse arrow hiding its `learn_more` children. Collapsing triggers `_reapplyActiveDot()` to bubble the green dot to the nearest visible ancestor.

**Green dot active indicator** (`session_list.html`):
- Each `<a data-session-id="...">` has an absolutely-positioned `.knr-dot hidden` span.
- `window._reapplyActiveDot()` shows the dot on the active row. If the active session is hidden (collapsed subtree), walks up `[x-data]` ancestors to find the nearest visible parent row and shows a softer dot there.

**Centre pane input bar** is **always visible** — sending a message with no active session auto-creates a `regular` session before the first turn.

---

## 26. New Dependencies

```
# requirements.txt additions
google-adk>=0.5   # Google ADK — fact-check SequentialAgent (Layer 5)
litellm>=1.40     # LiteLlm routing (available for future use)
```

`google-adk` provides the `SequentialAgent`, `LlmAgent`, and the native `google_search` tool used by the Layer 5 fact-check pipeline. The `litellm` dependency is installed as a transitive requirement of `google-adk` and is available for future routing of non-Gemini models through ADK if needed.
