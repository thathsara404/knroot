# Knowledge Root — Architecture Document

> **Scope:** Reshaping the existing AI chat agent into a full-featured tech-learning platform with authentication, chat history, smart news caching, a multi-agent knowledge pipeline, and an adaptive knowledge-check system.
>
> **Baseline stack:** Flask · PostgreSQL · Redis · LangGraph (chat) · google-genai (fact-check, Gemini 2.0 Flash + Google Search grounding) · OpenRouter (DeepSeek) · fastembed (topic-news embeddings) · Jinja2 + HTMX + Alpine.js · Docker Compose

---

## 1. Product Vision

A **news-anchored AI learning platform** where users can explore any topic — technology, science, history, economics, biology, politics — through structured, progressive AI-guided learning sessions triggered by real-world news.

1. Register and log in with a personal account.
2. Ask about **any topic** and receive a structured conceptual map covering every major pillar of that subject, ordered foundational → applied → advanced — so no important concept is missed.
3. Click **Explore** on any news article across six categories (AI · Dev · World · Bio · Econ · Health) to extract the underlying concepts from current real-world events.
4. Drill deeper into any concept via recursive **Learn More** sessions — each click goes one level deeper, building a personal knowledge tree.
5. Test knowledge at any depth via adaptive MCQs derived from the full conversation ancestry, with per-question Relearn explanations and Follow-up quizzes targeting weak areas.

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
│   │   │   ├── service.py              ← get_news(category) / get_topic_news(topic) — orchestrates cache + RSS; _infer_category() fallback
│   │   │   ├── cache.py                ← Redis day/hour cache; fetch_topic_news() embedding pipeline; refresh_article_embeddings()
│   │   │   ├── embeddings.py           ← all-MiniLM-L6-v2 loader; embed_articles(); weighted_scores(); adaptive_threshold(); mmr_rerank()
│   │   │   └── feeds.py                ← NEWS_FEEDS dict keyed by 'ai' | 'programming' | 'political' | 'biology' | 'economy' | 'health'
│   │   ├── discuss/
│   │   │   ├── routes.py
│   │   │   └── service.py              ← news_discuss(), create_learn_more_session(), get_tree()
│   │   ├── quiz/
│   │   │   ├── routes.py
│   │   │   ├── service.py              ← attempt lifecycle: generate, save, submit, retry, relearn
│   │   │   └── generator.py            ← LLM MCQ prompt + validation; _shuffle_options() post-generation randomiser; relearn prompt + cache
│   │   └── wall/
│   │       ├── routes.py               ← Blueprint('/wall'): shares CRUD, votes, comments, follow, profile, preview, import
│   │       └── service.py              ← create/delete share, cast_vote, add/list/delete comment, follow, get_profile, get_share_preview, import_share
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
│       ├── 007_quiz_session.sql        ← adds linked_attempt_id to chat_sessions
│       ├── 008_source_category.sql     ← adds source_category to chat_sessions (news-tab origin for topic-news fallback)
│       ├── 009_social.sql              ← shares, share_votes, share_comments, user_follows tables
│       ├── 010_import.sql              ← chat_sessions.imported_from_share_id + shares.source_share_id
│       ├── 011_follow_requests.sql     ← adds status + requested_at to user_follows; partial index on pending
│       ├── 012_cascade_reshare.sql     ← changes source_share_id FK to ON DELETE CASCADE (cascade-delete re-shares)
│       └── 013_wall_saves.sql          ← wall_saves: user bookmarks a public share to their private wall
│
├── backend/templates/                  ← Jinja2 HTML templates (served by Flask directly)
│   ├── base.html                       ← HTML shell: head with CDN links, nav, flash messages
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── app/
│   │   └── index.html                  ← 3-pane layout (sidebar + chat + news) with bottom nav (Root/Wall/Profile)
│   ├── learn/
│   │   └── session.html                ← Learning tab (sidebar + chat + knowledge tree)
│   ├── quiz/
│   │   └── attempt.html
│   └── partials/                       ← HTMX partial responses (HTML fragments)
│       ├── session_list.html           ← Sidebar session tree with hierarchy + green-dot indicator + share button + ↗ badge
│       ├── message.html                ← Single chat message bubble
│       ├── messages.html               ← Full message history list (session replay)
│       ├── sectioned_message.html      ← Sectioned AI response (Explore / Learn More)
│       ├── news_panel.html             ← 6-tab news panel (AI / Dev / World / Bio / Econ / Health)
│       ├── topic_news_panel.html       ← Topic-filtered news articles partial
│       ├── knowledge_tree.html         ← Knowledge tree node list
│       ├── knowledge_tree_panel.html   ← Right-pane knowledge tree wrapper
│       ├── quiz_section.html           ← Per-section inline quiz cards
│       ├── quiz_inline.html            ← Full inline quiz loaded into #chat-messages
│       ├── fact_check_report.html      ← Gemini fact-check verdict card
│       ├── wall_public.html            ← Public wall card list (HTMX partial)
│       ├── wall_private.html           ← Private/friends feed card list (HTMX partial)
│       ├── share_card.html             ← Single share card: author, votes, comments, preview, import
│       ├── profile_main.html           ← Profile centre pane: avatar, stats, recent shares
│       ├── profile_score.html          ← Profile right pane: star rating, vote breakdown, scoring rules
│       ├── share_preview_modal.html    ← Full-screen preview overlay: session tree + content panel
│       └── share_session_preview.html  ← Preview content: chat bubbles or ephemeral MCQ (previewQuizState)
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
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id              VARCHAR(255) UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    title                  VARCHAR(255),                   -- NULL = auto-generate from content
    session_type           VARCHAR(20) NOT NULL DEFAULT 'regular',
    parent_session_id      UUID REFERENCES chat_sessions(id),
    root_session_id        UUID REFERENCES chat_sessions(id),
    depth_level            INTEGER NOT NULL DEFAULT 0,
    topic                  VARCHAR(500),
    news_article_id        VARCHAR(20),
    linked_attempt_id      UUID,                          -- points to mcq_attempts row for quiz sessions
    source_category        VARCHAR(20),                   -- news tab origin ('health','economy',…) for topic-news fallback
    imported_from_share_id UUID REFERENCES shares(id) ON DELETE SET NULL,  -- set when session is a deep-copy import
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    last_message_at        TIMESTAMPTZ DEFAULT NOW()
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

### 4.4 `shares`, `share_votes`, `share_comments`, `user_follows`

```sql
-- Migration 009_social.sql
CREATE TABLE shares (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    visibility      VARCHAR(10) NOT NULL DEFAULT 'public',  -- 'public' | 'friends'
    description     TEXT,
    source_share_id UUID REFERENCES shares(id) ON DELETE SET NULL,  -- attribution: original share when re-sharing an import
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE share_votes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id   UUID REFERENCES shares(id) ON DELETE CASCADE,
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    vote       SMALLINT NOT NULL CHECK (vote IN (1, -1)),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(share_id, user_id)
);

CREATE TABLE share_comments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id   UUID REFERENCES shares(id) ON DELETE CASCADE,
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_follows (
    follower_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    followed_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    status       VARCHAR(10)  NOT NULL DEFAULT 'accepted',  -- 'pending' | 'accepted'
    requested_at TIMESTAMPTZ           DEFAULT NOW(),
    created_at   TIMESTAMPTZ           DEFAULT NOW(),
    PRIMARY KEY (follower_id, followed_id)
);

-- Migration 011_follow_requests.sql (additive, idempotent)
-- ALTER TABLE user_follows
--     ADD COLUMN IF NOT EXISTS status       VARCHAR(10)  NOT NULL DEFAULT 'accepted',
--     ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ           DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_follows_pending
    ON user_follows(followed_id, status)
    WHERE status = 'pending';
```

**Scoring algorithm** (`service.py::score_to_stars`):
- Each upvote (+1 vote) → **+10 pts**; each downvote (−1 vote) → **−5 pts**
- `score = upvotes × 10 + downvotes × (−5)` (downvotes are stored as `vote = -1`)
- Star thresholds: 50 pts → 1★, 150 pts → 2★, 350 pts → 3★, 600 pts → 4★, 900 pts → 5★

### 4.5 `wall_saves`
```sql
-- Migration 013_wall_saves.sql
CREATE TABLE wall_saves (
    user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    share_id UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, share_id)
);
CREATE INDEX IF NOT EXISTS idx_wall_saves_user ON wall_saves(user_id, saved_at DESC);
```

A lightweight bookmark: the viewer clicks "Save to my wall" on a public wall post → a `wall_saves` row is inserted. The saved post then appears in their private wall (My Wall) alongside their own shares. Deleting the original share (via `ON DELETE CASCADE`) automatically removes all saves of that share.

### 4.6 `news_cache` (DB fallback for Redis)
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

When a user is inside a chat session, the right-pane news panel shows articles semantically relevant to the session topic. Two Redis cache layers keep the hot path fast:

```
Redis keys:
  news:article_embeddings:{model}:{version}      TTL: 1 h   — pre-computed title+summary embeddings for all articles
  news:category_embeddings:{model}:{version}     TTL: 24 h  — one embedding per category label (zero-shot routing)
  news:topic:{sha256(topic)[:10]}:{hours}        TTL: 30 min (hit) / 10 min (miss) — scored+ranked result list
```

**Embedding store** (`news:article_embeddings:…`) is written by the APScheduler `_refresh_all` job each time category feeds are refreshed (every ~1.5 h). Each entry is a full article dict with two extra fields:
- `title_emb`: list[float] — L2-normalised 384-dim embedding of the title
- `summary_emb`: list[float] — L2-normalised 384-dim embedding of the summary

**Topic result cache** (`news:topic:…`) is written by `service.py`'s `get_topic_news()` after the first query for a topic. Subsequent requests within the TTL window are served from this cache (~5 ms) — no feed fetch, no embedding.

Served via `GET /news/topic-partial?topic=<text>&session_id=<id>`. When topic search returns no results, the fallback chain is:

1. **`source_category`** (stored on `chat_sessions` at session creation) — used for `news_discussion` and `learn_more` sessions. The originating tab category is a known fact; no inference needed.
2. **Embedding-based category routing** — used for `regular` sessions. The topic is embedded and compared against pre-computed `CATEGORY_LABELS` embeddings (one per category, 24 h Redis TTL). The closest category is selected via cosine similarity — zero-shot classification, no hardcoded keywords.

**`_age_hours` handling:** `_age_hours` is re-computed from the stored `published` timestamp each time embeddings are loaded from Redis, so values do not grow stale between the embed job and the query. The field is stripped before writing to the topic result cache (both in `cache.py`'s `set_cache()` and in `service.py`'s `get_topic_news()`).

### 6.3 Topic-News Ranking Pipeline

`fetch_topic_news()` in `backend/api/news/cache.py` runs a multi-stage pipeline on every cache miss:

```
Redis hit?
  ├── YES → load articles_with_embs (pre-computed)
  └── NO  → fetch ALL_FEEDS → embed_articles() (fallback, slower)
        │
        ▼
  Re-compute _age_hours from published timestamp
        │
        ▼
  Filter to requested age window (default 7 d; relax to 30 d if empty)
        │
        ▼
  Embed topic (1 vector, ~2 ms)
        │
        ▼
  Weighted cosine similarity per article
    score = 0.7 × cos_sim(topic, title_emb)
          + 0.3 × cos_sim(topic, summary_emb)
        │
        ▼
  Adaptive threshold = max(0.15, top_score × 0.6)
        │
        ▼
  Maximal Marginal Relevance re-ranking (λ = 0.6)
  → top-15 articles, semantically diverse
        │
        ▼
  Strip embedding vectors before returning
```

**Why each stage:**
- **Weighted scoring** — titles are denser signal than summaries (boilerplate, datelines). `0.7 / 0.3` split reflects this.
- **Adaptive threshold** — a fixed threshold fails for niche topics (nothing passes) or very broad queries (everything passes). Scaling with `top_score × 0.6` adapts automatically.
- **MMR re-ranking** — prevents 15 articles from the same source or sub-angle. MMR iteratively picks the next article that maximises `λ × relevance − (1−λ) × max_similarity_to_already_selected`.
- **Keyword fallback** — if `fastembed` fails to load (first deploy before model download, OOM), the old keyword-scoring path runs silently. No crash, slightly less accurate.

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

### 7.4 Agent Tools (`backend/agent/tools.py`)

The LangGraph ReAct agent has access to the following tools:

| Tool | Description |
|------|-------------|
| `get_latest_ai_news` | Returns recent AI/ML news headlines from the Redis-cached feed |
| `fetch_url` | Fetches URL content using `requests` + BeautifulSoup4; strips scripts/styles; returns cleaned text (≤ 4000 chars). Enables the agent to read linked articles or documentation pages the user pastes into chat. |

`fetch_url` sanitises the response: `<script>`, `<style>`, and `<nav>` tags are removed; remaining text is joined and truncated. The tool is only invoked when the LangGraph agent decides the content is needed — it is not called on every message.

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

**Option shuffling:** After LLM generation, `_shuffle_options(question)` in `generator.py` randomises the order of the four options using `random.shuffle`. The correct answer is re-located by text identity match and `correct` is updated to the new index. This eliminates LLM position bias (the model tends to place the correct answer in position 1). Both `generate_mcq()` and `generate_mcq_followup()` apply this transform before returning.

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

The left sidebar has **three bottom-nav tabs** (Root / Wall / Profile) controlled by `activeTab` in `appState()`. The default is `'root'`.

```
┌──────────────┬──┬───────────────────────────┬──┬──────────────┐
│  LEFT PANE   │▌ │       CENTRE PANE         │▌ │  RIGHT PANE  │
│  resizable   │  │  flex-1, min-w-0          │  │  resizable   │
│              │  │                           │  │              │
│ [Root tab]   │  │  activeTab=root:          │  │  activeTab=root:    │
│ ● New Chat   │  │    Message thread         │  │    AI News 6-tabs   │
│ Session list │  │    Inline quiz            │  │                     │
│ (HTMX load)  │  │  activeTab=wall:          │  │  activeTab=wall:    │
│ ↗ badge on   │  │    🌍 Public Wall         │  │    🔒 Your Feed     │
│ imported sess│  │    (HTMX partial)         │  │    (HTMX partial)   │
│              │  │  activeTab=profile:       │  │  activeTab=profile: │
│ ─────────    │  │    Profile card           │  │    ⭐ Your Score     │
│ [Root][Wall] │  │    (HTMX partial)         │  │    (HTMX partial)   │
│ [Profile]    │  │                           │  │                     │
│              │  │  [🧠 Check Knowledge]     │  │  Loading overlay    │
│              │  │  (root tab only)          │  │                     │
└──────────────┴──┴───────────────────────────┴──┴──────────────┘
           resize handles
```

**Bottom nav** (`switchTab(tab)` in `appState()`):
- `activeTab = 'root'` — shows session list, chat interface, news pane (default)
- `activeTab = 'wall'` — centre: `GET /wall/public/partial` → `wall_public.html`; right: `GET /wall/private/partial` → `wall_private.html`
- `activeTab = 'profile'` — centre: `GET /wall/profile/partial` → `profile_main.html`; right: `GET /wall/score/partial` → `profile_score.html`

**Left pane** — `partials/session_list.html` (HTMX-loaded):
- Groups sessions by: Today / Yesterday / This Week / Older.
- Session item: title (auto or user-set) + relative timestamp.
- Hierarchical: `news_discussion` roots are collapsible; `learn_more` children indented.
- **Green dot active indicator**: a `.knr-dot` `<span>` inside each session row `<a data-session-id="...">`. `window._reapplyActiveDot()` highlights the active row. When a parent is collapsed and the active session is a hidden descendant, the dot appears on the nearest visible ancestor row (softer shade). Triggered by `setActiveSession()`, HTMX `afterSettle` on `#session-list`, and collapse-toggle clicks.
- **Share button** (📤): shown on root sessions (`parent_session_id IS NULL`); calls `shareSession(id)` to open the share modal.
- **Import badge** (↗): shown on sessions with `imported_from_share_id IS NOT NULL` to indicate an imported root.
- **Tree auto-expand**: when a new sub-session is created, `session_list_partial()` computes `open_ids` — the full ancestor chain from the new session to the tree root — and passes it to Jinja2. All ancestors render with `details[open]`. The `htmx:configRequest` hook in `app.js` injects `expand=_activeSessionId` into every session-list request that lacks an explicit `expand` param, so the active path stays open after any sidebar refresh (chat reply, delete, regenerate, etc.).
- Skeleton placeholder rendered server-side while loading.

**Centre pane** — messages + input bar:
- `[🧠 Check Knowledge]` strip shown only when a session is active and `activeTab === 'root'`.
- Quiz loads **inline** into `#chat-messages` (no new tab).
- Button label toggles: "🧠 Check Knowledge" → "🧠 Follow-up Quiz" after a quiz is submitted.
- Button disabled via `:disabled="quizLoading || chatLoading || contentBusy || (quizViewState && !quizViewState.submitted)"`.
- **`contentBusy`** — single Alpine boolean set `true` during content-loading operations that occupy the centre pane (chat send, quiz generation, section Explore, section quiz, sidebar session switch, learn-more creation). Both Send and Check Knowledge buttons bind to it. News card Explore (`discussArticle()`) intentionally does **not** set `contentBusy` — the session is created in the background and appears in the sidebar without interrupting the current chat view.

**Right pane** — `partials/news_panel.html` (HTMX-loaded when `activeTab === 'root'`):
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
| Active sidebar tab       | Alpine `activeTab` in `appState()` — `'root'` / `'wall'` / `'profile'` |
| Pending follow requests  | Alpine `pendingFollowCount` integer in `appState()` — fetched from `GET /wall/follow-requests/count` when Profile tab is activated; drives red notification badge on Profile tab button |
| Share modal              | Alpine `shareModal` object in `appState()` — `{open, sessionId, visibility, description}` |
| Share preview            | `wallOpenPreview(shareId)` fetches `GET /wall/shares/<id>/preview/partial` and injects into `#share-preview-portal` |
| Ephemeral quiz preview   | `previewQuizState()` Alpine component — reads questions from `<script type="application/json" id="preview-qdata">` data-island; scores client-side; no server write |
| UI state                 | Alpine.js `x-data` per component (toggles, dropdowns)                 |

**`quizViewState` event flow:** `quiz.js`'s `quizState()` component dispatches `quiz-view-changed` on `init()` and after `submitQuiz()`. `appState().init()` listens for this event and stores `{isQuiz, attemptId, quizSessionId, parentSessionId, submitted, score}` in `quizViewState`. The `htmx:afterSettle` handler clears `quizViewState` when `#chat-messages` no longer contains a `.knr-quiz-root` element.

**JS module rule:** All JavaScript lives in `backend/static/*.js`. No inline `<script>` with logic in templates. HTMX handles server requests; Alpine.js handles client reactivity. Templates may only contain `x-data`, `x-bind`, `@click` attribute bindings — never `<script>` blocks with function definitions.

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
| POST   | `/news/fact-check`               | Session | Gemini fact-check (Google Search grounding) — returns verdict card HTML |

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

### Wall

| Method | Path                                          | Auth    | Description                                                    |
|--------|-----------------------------------------------|---------|----------------------------------------------------------------|
| GET    | `/wall/public/partial`                        | Session | HTMX partial — public wall card list                           |
| GET    | `/wall/private/partial`                       | Session | HTMX partial — private/friends feed card list                  |
| GET    | `/wall/profile/partial`                       | Session | HTMX partial — profile centre pane                             |
| GET    | `/wall/score/partial`                         | Session | HTMX partial — profile score / star rating right pane          |
| POST   | `/wall/shares`                                | Session | Create share (body: `{session_id, visibility, description}`)   |
| DELETE | `/wall/shares/<id>`                           | Session | Delete own share                                               |
| GET    | `/wall/shares/<id>/preview/partial`           | Session | HTMX partial — full-screen preview modal HTML                  |
| GET    | `/wall/shares/<id>/sessions/<sid>/preview/partial` | Session | HTMX partial — preview content for one session (messages or ephemeral quiz) |
| POST   | `/wall/shares/<id>/vote`                      | Session | Cast or change vote (`{vote: 1}` or `{vote: -1}`)              |
| POST   | `/wall/shares/<id>/import`                    | Session | Deep-copy shared session tree to own Root section              |
| GET    | `/wall/shares/<id>/comments`                  | Session | List comments for a share (JSON)                               |
| POST   | `/wall/shares/<id>/comments`                  | Session | Add comment (body: `{body}`)                                   |
| DELETE | `/wall/shares/<id>/comments/<cid>`            | Session | Delete own comment                                             |
| POST   | `/wall/shares/<id>/save`                      | Session | Bookmark a public share to My Wall (204); idempotent           |
| DELETE | `/wall/shares/<id>/save`                      | Session | Remove bookmark from My Wall (204)                             |
| POST   | `/wall/follow/<uid>`                          | Session | Send follow request; returns `{status: "pending"|"accepted"|"self"}` (200) |
| DELETE | `/wall/follow/<uid>`                          | Session | Cancel pending request or unfollow accepted follower (204)     |
| POST   | `/wall/follow-requests/<uid>/accept`          | Session | Accept an incoming follow request (204)                        |
| POST   | `/wall/follow-requests/<uid>/reject`          | Session | Reject / decline an incoming follow request (204)              |
| GET    | `/wall/follow-requests/count`                 | Session | Number of pending incoming requests (JSON: `{count: N}`)       |

### SSE (Real-time Events)

| Method | Path             | Auth    | Description |
|--------|------------------|---------|-------------|
| GET    | `/events/stream` | Session | Long-lived SSE stream for the current user. Returns `text/event-stream`. |

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
      - FACT_CHECK_MODEL=${FACT_CHECK_MODEL:-gemini-2.0-flash}  # Gemini model for fact-check (Layer 5)
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

The right-side news panel is a six-tab group:

| Tab | Category key | Purpose |
|-----|-------------|---------|
| AI | `ai` | AI/ML research, industry news, model releases |
| Dev | `programming` | Software engineering, tools, languages, infrastructure |
| World | `political` | World affairs, policy, governance |
| Bio | `biology` | Biology research journals, preprints, life-science news |
| Econ | `economy` | Economics, finance, markets, business |
| Health | `health` | Health, medicine, wellness, beauty |

### 16.2 RSS Feeds per Category

Source of truth is `backend/api/news/feeds.py`. Current feeds per category:

| Category | Sources |
|---|---|
| `ai` | TechCrunch AI, VentureBeat AI, The Verge AI, ArXiv AI, HuggingFace Blog, Reuters Tech, BBC Technology |
| `programming` | Hacker News, Dev.to, Stack Overflow Blog, InfoQ, GitHub Blog |
| `political` | Reuters World, BBC World, CNN, AP News, Al Jazeera, NPR News |
| `biology` | bioRxiv, PLOS Biology, eLife, Science Daily, STAT News, The Scientist, New Scientist |
| `economy` | Reuters Business, BBC Business, The Economist, MarketWatch, Financial Times, Bloomberg, CNBC |
| `health` | BBC Health, Reuters Health, Medical News Today, WHO News, Science Daily Health, Healthline, Allure |

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

`GET /news/partial?category=<tab>` — clients pass the active tab's category key. All six categories are pre-warmed by the APScheduler `_refresh_all` job on each cycle.

### 16.4 Updated NewsPanel Layout

```
┌──────────────────────────────────────────┐
│  [AI] [Dev] [World] [Bio] [Econ] [Health]│  ← tab group
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
- `[Fact Check]` — triggers Layer 5 (`POST /news/fact-check`); single Gemini call with Google Search grounding renders a verdict card in-place (verified / disputed / unverifiable claims with source links). Hidden for research/preprint sources.

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
│  feedparser → 5 articles per source; up to 35 cached/category   │
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
│  Tools:                                                          │
│    get_latest_ai_news — reads Redis cache mid-conversation       │
│    fetch_url          — fetches public URL content via HTTP      │
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
│  Layer 5: Gemini Fact-Check Pipeline (google-genai, on-demand)  │
│  backend/agent/pipeline.py — single Gemini API call with        │
│  native Google Search grounding (GoogleSearch tool)             │
│  Gemini searches Google automatically during generation,        │
│  then rates each claim verified/disputed/unverifiable + JSON    │
│  Triggered ONLY by [Fact Check] button on news article cards    │
│  Hidden for research/preprint sources (ArXiv, bioRxiv, etc.)   │
│  Requires GOOGLE_API_KEY; gracefully returns error card if unset│
│  Completely separate from chat / discuss flow                   │
└─────────────────────────────────────────────────────────────────┘
```

### 25.1 Layer 1 — Hourly RSS Cache + Embedding Pre-compute (no AI)

`feedparser` pulls **5 articles per source** across all feeds. Three APScheduler jobs run on a 1–1.5 h cycle:

| Job | Purpose |
|-----|---------|
| `news_cache_promote` | Merges the previous hour's Redis cache into the day cache (hourly) |
| `news_cache_refresh` | Fetches fresh RSS articles per category, runs Layer 2 curation, writes to Redis (every 1.5 h ± 300 s jitter). At the end of each refresh cycle, calls `refresh_article_embeddings()` to rebuild the embedding store. |

Redis keys written:
- `news:hour:{YYYY-MM-DD-HH}:{category}` — TTL 1 h (category news panel)
- `news:day:{YYYY-MM-DD}:{category}` — TTL 24 h (category news panel)
- `news:article_embeddings:all-MiniLM-L6-v2:v1` — TTL 1 h (topic-news semantic search)
- `news:category_embeddings:all-MiniLM-L6-v2:v1` — TTL 24 h (zero-shot category routing fallback)
- `news:topic:{sha256[:10]}:{hours}` — TTL 30 min / 10 min (per-topic result cache)

### 25.2 Layer 2 — AI News Curation

After each RSS fetch, `curate_with_ai()` in `backend/api/news/cache.py` calls DeepSeek with `NEWS_CURATION_PROMPT`. The model selects up to 10 of the most important articles for a general educated audience and returns them first; the remainder are sorted newest-first and appended. AI-selected articles are tagged `_curated: True` (only when there is a non-curated remainder — if all articles are selected, no badge is shown). The `/news/partial` route slices the cached list to **15 articles** before passing to the template, so the sidebar never shows more than 15 cards. If the LLM call fails, the original RSS order is preserved (no service interruption).

### 25.3 Layer 3 — LangGraph ReAct Agent

The chat agent in `backend/agent/graph.py` is a single `StateGraph` with two nodes:

| Node | Role |
|------|------|
| `agent` | Calls DeepSeek with the conversation history + system prompt |
| `tools` | LangGraph `ToolNode` that executes any tool calls returned by the agent |

A conditional edge routes from `agent` → `tools` when the model requests a tool, then back to `agent`. Two tools are registered:

| Tool | Purpose |
|------|---------|
| `get_latest_ai_news` | Reads the Redis news cache (Layer 1) so the agent can reference current headlines mid-conversation |
| `fetch_url` | Fetches the plain-text content of any publicly accessible URL the user pastes. Uses `requests` + `BeautifulSoup4` — strips nav/footer/scripts, extracts `<main>` or `<article>` content, truncates to 4 000 chars. Falls back gracefully on timeouts, HTTP errors, or paywalled pages. |

`fetch_url` follows the standard ReAct pattern: the agent detects a URL in the user message, calls the tool, receives page text, then generates the structured educational response using that content as grounding. No third-party reader service is used — plain HTTP only.

**State persistence:** all conversation history is stored via `PostgresSaver` (LangGraph's PostgreSQL checkpointer). Sessions survive server restarts; the checkpointer is keyed by `thread_id`, which equals the `chat_sessions.id` row.

**News injection:** when a session has no prior messages, the first `system` message includes the top 5 cached AI headlines so the agent has fresh context without needing to call the tool.

This layer powers `POST /chat` and any follow-up turns inside a `news_discussion` session.

### 25.4 Layer 4 — Direct LLM Pipeline (Explore / Learn More)

The Explore and Learn More flows do **not** go through LangGraph. `_run_discussion_pipeline()` in `backend/api/discuss/service.py` makes a direct DeepSeek call with the appropriate prompt:

- `DISCUSSION_PROMPT` — for `POST /news/discuss` (Explore button on a news card)
- `LEARN_MORE_PROMPT` — for `POST /sessions/<id>/learn-more` (Explore on a section card)

Both prompts return **structured sectioned JSON** (intro, 3–5 sections, outro — see §18). After the call, the response is validated and the first exchange is written into the LangGraph checkpoint via `update_state` so subsequent turns in the session can use Layer 3 with the full history. There is no second LLM call to persist the message — the direct call's output is the stored content.

### 25.5 Layer 5 — Gemini Fact-Check Pipeline (on-demand)

`backend/agent/pipeline.py` makes a **single synchronous `google-genai` API call** with the native `GoogleSearch` grounding tool enabled. Gemini performs web searches automatically during generation — no separate search agent or async orchestration needed.

| Step | What happens |
|------|-------------|
| Build prompt | Article title + summary formatted into `FACT_CHECK_PROMPT` |
| `client.models.generate_content()` | Gemini searches Google for each claim and generates verdict JSON in one call |
| `_merge_grounding_sources()` | Source URLs pulled from `grounding_metadata.grounding_chunks` and attached to claims that didn't include URLs |

The response is parsed as JSON with keys `overall_verdict`, `claims[]` (each with `claim`, `verdict`, `evidence`, `sources`), and `summary`.

**Source filtering:** the `[Fact Check]` button is hidden server-side (Jinja2 `{% if not is_research %}`) for research/preprint sources: ArXiv AI, ArXiv ML, HuggingFace Blog, GitHub Blog, bioRxiv, PLOS Biology, eLife. It appears only on news sources where web-verifiable claims exist.

Triggered **only** by the `[Fact Check]` button (`POST /news/fact-check`). Requires `GOOGLE_API_KEY`; returns a graceful error card if unset. Completely isolated from chat/discuss — never writes to `chat_sessions` or LangGraph state.

### 25.6 Agent Package Structure

```
backend/agent/
├── graph.py         ← LangGraph StateGraph (Layer 3 — chat agent + checkpointer)
├── pipeline.py      ← Gemini + Google Search grounding (Layer 5 — fact-check)
├── prompts.py       ← All prompt constants:
│                       SYSTEM_PROMPT (Layer 3 chat)
│                       AUTO_TITLE_PROMPT
│                       NEWS_CURATION_PROMPT (Layer 2)
│                       DISCUSSION_PROMPT (Layer 4 — Explore)
│                       LEARN_MORE_PROMPT (Layer 4 — Learn More)
│                       MCQ_GENERATION_PROMPT
│                       MCQ_FOLLOWUP_PROMPT  ← follow-up quiz targeting weak areas
│                       RELEARN_PROMPT
│                       FACT_CHECK_PROMPT (Layer 5 — inline in pipeline.py)
└── tools.py         ← LangChain @tool: get_latest_ai_news
```

> Note: `FACT_CHECK_PROMPT` is defined as a module-level constant in `pipeline.py` (not in `prompts.py`) since it is only ever used there.

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
│                  │  │  Message thread               │  │[AI] [Dev]   │
│  [+ New Chat]    │  │  (HTMX append)                │  │[World][Bio] │
│                  │  │                               │  │[Econ][Health]│
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

## 26. Dependencies

Full `requirements.txt`:

```
flask>=3.0
flask-session>=0.8
pydantic>=2.0
flask-limiter[redis]>=3.5
langgraph>=0.2
langgraph-checkpoint-postgres>=2.0
psycopg[binary]>=3.2
psycopg-pool>=3.2
langchain-openai>=0.2
langchain-core>=0.3
feedparser>=6.0
python-dotenv>=1.0
gunicorn>=22.0
redis>=5.0
apscheduler>=3.10
bcrypt>=4.1
google-genai>=1.0
fastembed>=0.3
```

**Notable packages:**
- `google-genai` — current Google GenAI Python SDK (replaces the deprecated `google-generativeai`). Provides `google.genai.Client` and `types.Tool(google_search=types.GoogleSearch())` grounding for Layer 5. No ADK, no `litellm`.
- `fastembed` — ONNX-runtime-based embedding library (~60 MB install, no PyTorch). Loads `sentence-transformers/all-MiniLM-L6-v2` (384-dim) for topic-news semantic search. Model is downloaded on first use and cached by the library. `numpy` is a transitive dependency. No GPU required — CPU inference takes ~150 ms for a batch of 150 articles. Chosen over `sentence-transformers` to avoid the ~1.5 GB PyTorch Docker layer.

---

## 27. Learning Platform Prompt Design

The platform has four distinct AI interaction scenarios. Each maps to a learner's cognitive mode and uses a purpose-built prompt in `backend/agent/prompts.py`.

### 27.1 The Four Scenarios

| # | Trigger | Cognitive Mode | Goal | Prompt used |
|---|---------|---------------|------|-------------|
| 1 | User types a question in chat | Orientation or drilling, depending on question breadth | Show the complete concept map at the level asked — every major pillar covered | `SYSTEM_PROMPT` |
| 2 | Explore button on a news card | Orientation anchored to a current event | Extract every conceptual pillar this news article touches — complete for its context, not the full domain | `DISCUSSION_PROMPT` |
| 3 | Explore button on a response section | Drilling — user chose their path | Go exactly one level deeper into the clicked concept; cover ALL sub-components at that level | `LEARN_MORE_PROMPT` |
| 4 | Quiz / Check Knowledge button | Assessment | Test retention of what was learned; no new teaching content | `MCQ_GENERATION_PROMPT` / `MCQ_FOLLOWUP_PROMPT` |

### 27.2 The Completeness Mandate

The single most important rule across all teaching prompts (1, 2, 3): **cover every major pillar at the current level**. A learner must be able to see the complete shape of the subject from one response. Missing a significant concept is treated as a prompt failure.

This is what distinguishes the platform from a generic chatbot: a chatbot picks interesting points; a learning platform guarantees the map is complete.

### 27.3 When to Give a Full Domain Map vs. Targeted Depth

- **Broad question** ("explain machine learning", "what is the Roman Empire") → give the full domain map — all major areas covered at the top level
- **Specific question** ("how does backpropagation work?", "what is RLHF?") → stay at that level but be exhaustive — cover ALL components of the specific concept asked
- **News Explore** (Scenario 2) → stay at news-relevant level — cover all conceptual pillars this event touches, not the full domain
- **Section Explore** (Scenario 3) → go one level deeper into the clicked concept only — do not revisit siblings from the parent response

The rule: **match the abstraction level the user asked at, but be complete at that level.**

### 27.4 Section Structure (`sectioned` response type)

Every section in a teaching response carries these fields:

| Field | Purpose |
|---|---|
| `id` | Unique section identifier (`"s1"`, `"s2"`, …) |
| `title` | Name of the concept or component |
| `content` | 2–3 sentence plain-English explanation — how it works and why it matters |
| `key_points` | 3 concrete, testable learning points — specific facts, trade-offs, or mechanisms (not restatements of the title) |
| `misconception` | The single most common wrong assumption about this concept — one sentence; prevents bad mental models from forming |
| `learn_more_topic` | Specific sub-topic string for a deeper Explore follow-up session |

### 27.5 Learning Progression Rule

Sections within a response are always ordered:
1. **Foundational concept** — what this thing is and why it exists
2. **Core mechanism** — how it works internally
3. **Application layer** — how it is used in practice
4. **Advanced / edge cases** — nuance, trade-offs, limitations

This ordering lets a user who reads top-to-bottom build understanding progressively. A user who wants depth first can skip ahead via Explore.

### 27.6 Scenario 1 — `SYSTEM_PROMPT` (Manual Chat)

Domain: **any topic** — technology, science, history, economics, biology, politics, mathematics. The domain lock to AI/ML that existed in earlier versions is removed. The right-side news panel covers AI/Dev/World/Bio/Econ/Health; the chat window should match that breadth.

Key rules specific to this prompt:
- `intro` must state what background knowledge is assumed (or "No prior knowledge needed")
- Section count is adaptive: 4–6 typically, up to 7 for complex multi-pillar subjects; minimum 3
- `outro` must give a concrete recommended exploration order: which section to explore first and why

### 27.7 Scenario 2 — `DISCUSSION_PROMPT` (News Explore)

The news article is the anchor. The response radiates outward from the event, not from the full domain.

Key rules specific to this prompt:
- `intro` states what areas of knowledge the news event touches and why they matter now
- Sections cover concepts the event exposes — not the full field those concepts belong to
- Do not discuss: people's personal actions, political opinions, specific dates/names as the main subject
- Do write about: underlying laws, frameworks, mechanisms, historical/technical context

### 27.8 Scenario 3 — `LEARN_MORE_PROMPT` (Section Explore)

The user explicitly chose this sub-topic. They want depth, not breadth.

Key rules specific to this prompt:
- `intro` must include a one-sentence breadcrumb: "This is a deep-dive into [topic], a sub-component of [parent concept]." This prevents learners from getting lost after multiple Explore clicks.
- Every sub-section must go exactly one level deeper than the parent topic — never restating the parent
- `learn_more_topic` on each sub-section must be more specific than the section title

### 27.9 Scenario 4 — MCQ Prompts (Assessment)

Assessment prompts are intentionally separate from learning prompts. They never explain or teach — they only test and adapt.

- `MCQ_GENERATION_PROMPT` — generates 8 questions from the current conversation; tests technical concepts, trade-offs, mechanisms
- `MCQ_FOLLOWUP_PROMPT` — generates 8 adaptive questions after a previous attempt; prioritises wrong answers at a deeper level
- `RELEARN_PROMPT` — per-question explanation triggered when a user gets a question wrong; 3–4 sentences of grounded explanation
- Questions never ask about: names, dates, organisations, locations, trivia — only testable concepts

### 27.10 Placeholder Text

The chat input placeholder reflects the platform's domain breadth:
> "Ask anything — science, history, technology, economics…"

This replaces the old "Ask anything about AI, ML, or software…" which implied a domain restriction that no longer exists in the AI layer.

---

## 28. Social Wall System

### 28.1 Overview

Users can share any **root session** (their knowledge root, a discussion tree) publicly or with followers only. Shared roots appear as **share cards** on the wall. Other users can vote, comment, preview content, and import the tree to their own Root section.

### 28.2 Share Lifecycle

```
User clicks 📤 (share button on root session in sidebar)
  │
  ├─ Share modal opens (Alpine shareModal state)
  │   Fields: visibility (public/friends), description
  │
  └─ POST /wall/shares → creates shares row
       │
       ├─ Source attribution: if session.imported_from_share_id IS NOT NULL
       │   the new share's source_share_id = the original share (attribution chain)
       │
       └─ Share card appears on public wall / private feed
```

### 28.3 Share Card (`partials/share_card.html`)

Each card shows:
- Author avatar (initials), star rating, score, `@username`, timestamp
- Attribution line: "↗ Based on @original_author's root" (when `source_share_id IS NOT NULL`)
- Session title + visibility badge (Public / Friends only)
- Collapsible session tree (depth-indented, all sessions in the shared root)
- Action row: 👍 upvote / 👎 downvote, **Preview** button, context-sensitive action button
- Collapsible comments section (lazy-loaded via `GET /wall/shares/<id>/comments`)

The template receives a `wall_context` variable that controls which action buttons render:

| `wall_context` | Own card (top-right) | Others' card (top-right) | Action row button |
|----------------|---------------------|--------------------------|-------------------|
| `'public'`     | Delete (trash icon) | Follow / Requested / Following | **Save** (bookmark icon) — saves to My Wall |
| `'private'`    | Delete (trash icon) | Unsave (bookmark icon)   | **Import to Root** — deep-copies session tree |
| `'profile'`    | Delete (trash icon) | Follow / Requested / Following | *(none)* |

Alpine per-card state: `{ savedToWall, followStatus, myVote, upvotes, downvotes, importDone, importLoading }`

**Import button visibility:** The Import button renders unconditionally (no `x-show`) so it is always visible on first load. Post-import, Alpine's `:class="importDone ? 'hidden' : ''"` hides it. The "✓ Imported" confirmation span and the loading "…" span carry `style="display:none"` as pre-Alpine defaults so they stay hidden until Alpine sets them.

### 28.4 Voting and Scoring

**Vote mechanics:**
- `POST /wall/shares/<id>/vote` with `{vote: 1}` (upvote) or `{vote: -1}` (downvote)
- Implemented as `INSERT … ON CONFLICT (share_id, user_id) DO UPDATE SET vote = excluded.vote`
- A user can change their vote (upsert) or cast opposite to retract

**Score formula:**
```
score = SUM(vote * weight) WHERE weight = 10 if vote=1 else 5
     = upvote_count × 10 + downvote_count × (-5)
```

**Star thresholds:**
| Score | Stars |
|-------|-------|
| < 50  | 0 ★   |
| 50    | 1 ★   |
| 150   | 2 ★   |
| 350   | 3 ★   |
| 600   | 4 ★   |
| 900   | 5 ★   |

Score and stars are computed by `score_to_stars(score)` in `backend/api/wall/service.py` and hydrated into every share card and profile pane via `_hydrate_share_rows()`.

### 28.5 Preview Modal (`partials/share_preview_modal.html`)

Full-screen overlay (`z-50`). Opened by `wallOpenPreview(shareId)` which GETs `/wall/shares/<id>/preview/partial` and injects HTML into `#share-preview-portal`.

Layout:
```
┌──────────────────────────────────────────────────────────────┐
│  [✕ Close]   Preview: <session title>                        │
├──────────────┬───────────────────────────────────────────────┤
│  Session tree│  Content pane (#preview-content)             │
│  (left panel)│  ← initial content loaded inline             │
│              │                                               │
│  Click node  │  Chat bubbles (user=indigo right,            │
│  → HTMX GET  │   assistant=gray left)                       │
│  /preview/   │  OR                                           │
│  sessions/id │  Ephemeral MCQ (previewQuizState Alpine       │
│              │   component — no DB writes)                   │
└──────────────┴───────────────────────────────────────────────┘
```

**Ephemeral quiz (`partials/share_session_preview.html`):**
- Questions JSON embedded in `<script type="application/json" id="preview-qdata">` data-island
- `previewQuizState()` Alpine component reads the island on `init()`, tracks `selected[]`, computes score client-side after submit
- Shows correct/incorrect highlighting + score summary; "Try Again" resets state
- No `fetch()` call on submit — nothing is written to the DB

### 28.6 Import Flow

`POST /wall/shares/<id>/import` triggers a deep copy:
1. Fetch all `chat_sessions` rows in the shared root (ordered by `depth_level`)
2. For each session (within `conn.transaction()` for atomicity):
   - Create new `chat_sessions` row owned by the importer
   - Map old UUID → new UUID in `id_map`
   - Set `parent_session_id` using `id_map` (depth-ordered insert preserves FK validity)
   - Set `imported_from_share_id = share.id` on all imported sessions
   - For non-quiz sessions: copy `session_messages` rows verbatim (message history)
   - For quiz sessions: copy session row only (no message history — attempts belong to original owner)
3. Return the new root session id; sidebar triggers `sessionListRefresh`

**Attribution when re-sharing:**
If the importer later shares their imported root (`POST /wall/shares`), `create_share()` checks `session.imported_from_share_id → share.source_share_id` and sets `source_share_id` on the new share. `_hydrate_share_rows` batch-fetches `source_attribution` (original author name + share id) for all shares that have `source_share_id IS NOT NULL`.

### 28.7 Private Wall (My Wall)

The private wall (right pane) shows two categories of posts for the viewer:

1. **Own shares** — sessions the viewer personally shared from the sidebar share button. Delete button visible; no import.
2. **Saved shares** — posts the viewer bookmarked from the public wall via "Save to my wall." Import button visible; unsave (bookmark icon) button visible.

`list_private_shares()` query:
```sql
SELECT s.*, (s.user_id = %(viewer)s) AS is_own,
            (ws.user_id IS NOT NULL)  AS is_saved
FROM shares s
JOIN chat_sessions cs ON cs.id = s.session_id
LEFT JOIN wall_saves ws ON ws.share_id = s.id AND ws.user_id = %(viewer)s
WHERE s.user_id = %(viewer)s OR ws.user_id = %(viewer)s
ORDER BY s.created_at DESC
```

**Workflow — Save → Import:**
```
Public wall → click "Save" on any post
  └─ POST /wall/shares/<id>/save → wall_saves row inserted
       └─ Post now appears in My Wall (right pane)
            └─ Click "Import to Root" → session tree deep-copied to user's Root section
                 └─ Auto-unsave: DELETE /wall/shares/<id>/save (already in Root, no need to keep bookmark)
```

When the original owner deletes their share, the `wall_saves` row is cascade-deleted automatically (`ON DELETE CASCADE` on `wall_saves.share_id`). The saved post silently disappears from all private walls.

### 28.8 Profile View

| Pane | Template | Content |
|------|----------|---------|
| Centre | `profile_main.html` | Avatar (initials), full name, @username, email, member since, stats grid (Shares / Following / Followers), recent 5 shares |
| Right | `profile_score.html` | Star rating card (gradient), vote breakdown (upvotes / downvotes / share count), scoring rules legend |

### 28.9 `_hydrate_share_rows` — N+1 Prevention

Hydration is batched over a page of share rows. For each batch:
1. One query: vote tallies + `my_vote` for viewer per `share_id`
2. One query: comment counts per `share_id`
3. One query: author scores (from `share_votes`) per `user_id` set
4. One query: `source_attribution` for shares with `source_share_id IS NOT NULL`
5. One query: viewer's follow status (`null` / `'pending'` / `'accepted'`) for each share's author — sets `share["follow_status"]`
6. One query: viewer's `wall_saves` entries — sets `share["saved_to_wall"]` (bool) used by Alpine per-card state

All results are keyed by share id or user id and merged into the share dicts before template rendering. No per-card queries.

### 28.10 Follow Request Approval Flow

Following uses a **request → approve** model (like Instagram private accounts). Every follow action goes through pending first:

```
Viewer clicks Follow on a share card
  │
  └─ POST /wall/follow/<uid>
       │
       ├─ Returns {status: "pending"}  ← inserted with status='pending'
       │   Card button: Follow → Requested (can cancel)
       │
       └─ Target opens Profile tab
            │
            ├─ pendingFollowCount badge shows on Profile tab button
            │   (fetched from GET /wall/follow-requests/count)
            │
            └─ Follow Requests section in profile_main.html
                 │
                 ├─ Accept → POST /wall/follow-requests/<uid>/accept
                 │   status='accepted'; follower now sees friend feed
                 │
                 └─ Decline → POST /wall/follow-requests/<uid>/reject
                     Record deleted; requester can follow again later
```

**Rejection design:** rejected requests are deleted (not stored as `status='rejected'`). This allows the requester to retry and keeps the schema simple — the absence of a row means "not following."

**Schema summary** (`011_follow_requests.sql`):
```sql
ALTER TABLE user_follows
    ADD COLUMN IF NOT EXISTS status       VARCHAR(10)  NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ           DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_follows_pending
    ON user_follows(followed_id, status)
    WHERE status = 'pending';
```

### 28.11 Priority Feed Sorting

`list_public_shares()` promotes posts from accepted follows to the top of the public wall:

```sql
LEFT JOIN user_follows uf
    ON uf.follower_id = %(viewer)s
   AND uf.followed_id = s.user_id
   AND uf.status = 'accepted'
ORDER BY (uf.follower_id IS NOT NULL) DESC,
         s.created_at DESC
```

Posts from people the viewer follows sort first; all remaining posts sort newest-first. No separate "following" feed needed — the public wall itself is priority-personalised.

`list_private_shares()` filters `status = 'accepted'` in its subquery so pending-only connections do not grant feed access:
```sql
WHERE follower_id = %(viewer)s AND status = 'accepted'
```

### 28.12 Follow Button States in Share Cards

Each share card carries `follow_status` (set by `_hydrate_share_rows`). Alpine per-card state tracks this reactively:

| `followStatus` value | Button shown | Action on click |
|----------------------|-------------|-----------------|
| `null`               | **Follow** (indigo outline) | `POST /wall/follow/<uid>` → set `followStatus = 'pending'` |
| `'pending'`          | **Requested** (gray, strikethrough hover) | `DELETE /wall/follow/<uid>` → set `followStatus = null` |
| `'accepted'`         | **Following** (green, hover turns red) | `DELETE /wall/follow/<uid>` → set `followStatus = null` |

Own cards show neither button (server sets `follow_status = 'self'`, filtered in template). All state transitions happen client-side after a `fetch()` — no HTMX reload needed for follow button UX.

---

## 29. Real-time Events (Server-Sent Events)

### 29.1 Design Goal

Deliver live updates — new comments, incoming follow requests, follow acceptances — to the browser without polling or page refresh. The pattern mirrors Facebook's architecture at a scale appropriate for this stack: a **per-user pub/sub channel in Redis** fanned out to a **persistent SSE connection** in the browser.

### 29.2 Transport Choice: SSE

| Option | Chosen? | Reason |
|--------|---------|--------|
| Polling (`setInterval` + fetch) | ✗ | Wastes bandwidth; acceptable only for very low-frequency events |
| **Server-Sent Events (SSE)** | ✓ | One-directional server→client push; works natively with Flask; browser auto-reconnects; no extra infra beyond Redis (already in stack) |
| WebSockets | ✗ | Bidirectional — unnecessary here; requires async server changes |

### 29.3 Architecture

```
Browser (EventSource)
        │  GET /events/stream (keep-alive, text/event-stream)
        │
  Flask SSE endpoint
  (backend/api/events/routes.py)
        │  Redis SUBSCRIBE user:<user_id>
        │
  Redis Pub/Sub
        ▲
  Publisher helpers
  (backend/core/sse.py)
        ▲
  Called by existing wall routes on every write:
    add_comment()           → publishes comment_added
    follow_user()           → publishes follow_request_received
    accept_follow_request() → publishes follow_accepted
```

### 29.4 Redis Channel Convention

Each user has one dedicated channel: `sse:user:<user_id>`.

All events for that user (regardless of type) are published to that single channel. The browser dispatches on `event.type` client-side.

### 29.5 Event Envelope

Every message published to Redis is a JSON string. The SSE endpoint forwards it as:

```
event: <event_type>
data: <json_payload>

```

| `event` type              | Payload fields | Who publishes |
|---------------------------|----------------|---------------|
| `comment_added`           | `share_id`, `comment` (full object incl. `parent_comment_id`) | `add_comment()` — fans out to all online users |
| `comment_deleted`         | `share_id`, `comment_id` | `delete_comment()` — fans out; client removes comment + its replies and decrements count |
| `vote_updated`            | `share_id`, `upvotes`, `downvotes`, `voter_user_id`, `my_vote` | `cast_vote()` — fans out; client syncs `myVote` only for the voter's own cards |
| `share_created`           | `share_id`, `user_id`, `author_name`, `author_username` | `create_share()` — fans out to all online users; own posts excluded from notification banner client-side |
| `follow_request_received` | `requester` (`{id, full_name, username}`) | `follow_user()` — targets the followed user |
| `follow_accepted`         | `accepted_by` (`{id, full_name, username}`) | `accept_follow_request()` — targets the requester |

### 29.6 SSE Endpoint (`GET /events/stream`)

The generator uses `get_message(timeout=KEEPALIVE_INTERVAL)` rather than the blocking `pubsub.listen()` iterator. This lets the loop wake up periodically even when no events arrive, so it can send a keepalive comment and renew the presence TTL:

```python
@bp.get("/events/stream")
@require_auth
def event_stream():
    user_id = g.user_id

    def generate():
        register_user(user_id)
        pubsub = get_redis().pubsub()
        try:
            pubsub.subscribe(f"sse:user:{user_id}")
            while True:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=KEEPALIVE_INTERVAL,   # 20 s
                )
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"])
                        yield f"event: {data['event']}\ndata: {data['payload']}\n\n"
                    except (ValueError, KeyError, TypeError) as exc:
                        logger.warning("sse.stream invalid message: %s", exc)
                else:
                    # Idle tick — keep proxy alive and renew TTL
                    yield ": keepalive\n\n"
                    renew_user_ttl(user_id)
        finally:
            pubsub.unsubscribe()
            pubsub.close()
            unregister_user(user_id)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

The SSE comment line `": keepalive\n\n"` is invisible to browser `EventSource` listeners but prevents proxies and load-balancers from closing an idle connection.

### 29.7 Publisher Helper (`backend/core/sse.py`)

Presence is tracked with per-user TTL keys (`sse:online:<user_id>`) rather than a Redis SET. A key is created on connect (`setex`), renewed every keepalive tick (`expire`), and deleted on clean disconnect. A crashed process simply lets its key expire within `PRESENCE_TTL` seconds — no stale entries accumulate.

```python
PRESENCE_TTL = 30          # seconds until a presence key expires
KEEPALIVE_INTERVAL = 20.0  # seconds between idle ticks in the SSE generator

def register_user(user_id: str) -> None:
    get_redis().setex(f"sse:online:{user_id}", PRESENCE_TTL, "1")

def renew_user_ttl(user_id: str) -> None:
    get_redis().expire(f"sse:online:{user_id}", PRESENCE_TTL)

def unregister_user(user_id: str) -> None:
    get_redis().delete(f"sse:online:{user_id}")

def publish_event(user_id: str, event: str, payload: dict) -> None:
    """Publish an SSE event to a single user's channel. Fire-and-forget."""
    get_redis().publish(
        f"sse:user:{user_id}",
        json.dumps({"event": event, "payload": json.dumps(payload)}),
    )

def broadcast_event(event: str, payload: dict) -> None:
    """Publish to every user with an active presence key."""
    redis = get_redis()
    msg = json.dumps({"event": event, "payload": json.dumps(payload)})
    for key in redis.scan_iter("sse:online:*"):
        uid = (key.decode() if isinstance(key, bytes) else key).split(":", 2)[-1]
        redis.publish(f"sse:user:{uid}", msg)
```

All Redis calls are wrapped in `try/except` — publish failures are logged and never raised to the caller.

### 29.8 Client Integration (`app.js`)

`wallInitSSE()` is called when the user switches to the Wall tab. It creates an `EventSource` and registers handlers:

```js
window.wallInitSSE = function () {
  if (window._wallSSE) return;          // already connected
  var es = new EventSource('/events/stream');

  es.addEventListener('comment_added', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleNewComment && window.wallHandleNewComment(data);
  });

  es.addEventListener('follow_request_received', function (e) {
    var appData = window._getAppData && window._getAppData();
    if (appData) appData.pendingFollowCount += 1;
  });

  es.addEventListener('follow_accepted', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleFollowAccepted && window.wallHandleFollowAccepted(data.accepted_by.id);
  });

  es.onerror = function () { es.close(); window._wallSSE = null; };
  window._wallSSE = es;
};

window.wallDestroySSE = function () {
  if (window._wallSSE) { window._wallSSE.close(); window._wallSSE = null; }
};
```

`switchTab('wall')` calls `wallInitSSE()`. `switchTab` away from wall calls `wallDestroySSE()`.

**Accessing Alpine component state** — card components are reached via the public Alpine v3 API `Alpine.$data(element)`, never the internal `_x_dataStack[0]`:

```js
window.wallHandleNewComment = function (data) {
  document.querySelectorAll('[data-share-id="' + data.share_id + '"]').forEach(function (card) {
    var component = window.Alpine && window.Alpine.$data(card);
    if (!component) return;
    // Deduplicate: the poster already incremented optimistically
    var alreadyPresent = component.comments.some(function (c) { return c.id === data.comment.id; });
    if (alreadyPresent) return;
    component.commentCount = (component.commentCount || 0) + 1;
    if (component.commentsOpen) {
      component.comments.push(data.comment);
    }
  });
};
```

The `alreadyPresent` guard prevents double-counting when the SSE event arrives for the user who posted the comment (whose client already incremented the count optimistically).

### 29.9 `comment_added` Fan-out Strategy

The public wall shows posts from all users. When user A posts a comment, every viewer currently on the wall should see it. Options:

| Strategy | Description | Chosen |
|----------|-------------|--------|
| **Broadcast to all online users** | `broadcast_event` publishes to every active SSE session | ✓ Simple; Redis pub/sub handles fan-out; active connections are limited |
| Track "who is viewing which share" | Server-side session registry | ✗ Complex; stateful; not worth it at this scale |

Implementation: `add_comment()` calls `broadcast_event("comment_added", ...)`, which scans for all `sse:online:*` TTL keys and publishes to each user's channel. Because the presence keys have a 30-second TTL (renewed every 20 s by the keepalive tick), only live connections receive events — stale entries from crashed processes expire automatically and are never included in the scan.

### 29.10 Flask Threading Requirement

Flask's built-in dev server must run with `threaded=True` (default in Flask ≥ 1.0) so each SSE connection holds its own thread. In production (gunicorn), use `--worker-class gevent` or `--threads N` to support concurrent streaming responses.

No changes to `docker-compose.yml` are needed — the existing `web` service already starts with threading.

### 29.11 `x-accel-buffering` Header

Nginx (and most reverse proxies) buffer upstream responses by default, which breaks SSE. The `X-Accel-Buffering: no` response header disables this. The endpoint always sends this header.

---

## 30. Live New-Post Notification (share_created)

### 30.1 Pattern

When a user publishes a new share, `create_share()` broadcasts a `share_created` SSE event to all online users. The browser does **not** auto-inject the new card (which would cause scroll-jump) — instead it shows a "N new posts — click to refresh" banner at the top of the public wall, matching the Facebook/Twitter UX pattern.

### 30.2 Own-Post Exclusion

`window._currentUserId` is set at page-load from the Jinja `user_id` context variable:

```html
<script>window._currentUserId = "{{ user_id }}";</script>
```

The `share_created` SSE handler skips incrementing the banner counter if `data.user_id === window._currentUserId`. Instead, `submitShare()` reloads both walls directly on success, so the poster sees their new post immediately without the banner.

### 30.3 Banner Reset

- Switching to the wall tab resets `newWallPosts = 0` (re-loads the wall fresh).
- Clicking the banner resets `newWallPosts = 0` and reloads the public wall partial.

---

## 31. Nested Comments (Replies)

### 31.1 Design

Two levels only (no infinite nesting) — the standard for social platforms at this scale. Top-level comments appear directly on the post. Replies appear indented under their parent comment.

### 31.2 Schema

```sql
ALTER TABLE share_comments
    ADD COLUMN IF NOT EXISTS parent_comment_id UUID
        REFERENCES share_comments(id) ON DELETE CASCADE;
```

`parent_comment_id` is `NULL` for top-level comments, set to the parent's `id` for replies.

### 31.3 Service

`add_comment(user_id, share_id, content, parent_comment_id=None)` — validates that the parent belongs to the same share before inserting. `list_comments` returns a flat list ordered by `created_at ASC`; the client groups into parent/reply buckets.

### 31.4 Client Rendering

`comments` in Alpine state is a flat array. The template uses filter expressions in `x-for` to group:

```html
<!-- Top-level -->
<template x-for="c in comments.filter(c => !c.parent_comment_id)" :key="c.id">
  ...
  <!-- Replies under this comment -->
  <template x-for="r in comments.filter(r => r.parent_comment_id === c.id)" :key="r.id">
    ...
  </template>
  <!-- Inline reply form -->
</template>
```

`replyingTo` (comment ID or `null`) controls which inline reply form is visible. `wallPostComment(shareId, content, component, parentCommentId?)` sends `parent_comment_id` in the request body when replying.

### 31.5 SSE

The existing `comment_added` event payload includes `parent_comment_id`. `wallHandleNewComment` pushes the comment into the flat `comments` array regardless of level — the template filter places it correctly.

---

## 32. UI Modernization & Client-Side JS Modules

### 32.1 Static JS Module Registry

All client-side JavaScript lives in `backend/static/` as self-contained IIFE modules. Each file is included in `backend/templates/base.html` in load order:

| File | Purpose |
|---|---|
| `toast.js` | Non-blocking toast notification system |
| `confirm.js` | `window.KnrConfirm(msg)` — promise-based custom confirm dialog |
| `time.js` | Client-side timezone-aware timestamp formatter |
| `app.js` | Main Alpine.js `appState()` component + all UI orchestration |
| `quiz.js` | Quiz-specific Alpine component and MCQ interaction logic |

### 32.2 Custom Confirm Dialog (`confirm.js`)

`window.KnrConfirm(message)` returns a `Promise<boolean>`. It injects a modal overlay, wires up Confirm/Cancel buttons, resolves the promise, and self-destructs. Callers use `await KnrConfirm(...)` to replace native `window.confirm()`.

**Usage sites:** delete-session button in the sidebar, delete-share modal in the Wall.

### 32.3 Timezone-Aware Timestamps (`time.js`)

**Problem:** The server-side `pub_date` Jinja filter rendered dates in UTC, so users in UTC+N timezones saw the wrong calendar date on news cards (e.g., "May 9" when their local time was already May 10).

**Solution (industry standard):** Store timestamps as UTC (already done). Emit a `<time datetime="ISO_UTC" data-knr-time>` element with the server-rendered fallback as text content. After page load, `time.js` replaces all matching elements with browser-local formatted strings using `new Date(isoStr)`, which the browser parses as UTC and converts to the local timezone automatically.

**Format produced:**

| Age | Example |
|---|---|
| < 1 min | `just now` |
| < 1 hour | `May 10 · 4m ago` |
| < 1 day | `May 10 · 3h ago` |
| 1 day | `May 9 · Yesterday` |
| 2–6 days | `May 8 · 2d ago` |
| ≥ 7 days | `May 3` |
| Different year | `Dec 31, 2025` |

**Three trigger points:**
1. `DOMContentLoaded` — initial page load
2. `htmx:afterSwap` — after any HTMX partial replaces content
3. `setInterval(updateAll, 60000)` — updates relative labels every minute without a page reload

**Template pattern (news_panel.html, topic_news_panel.html, share_card.html):**

```html
<time
  class="text-xs text-gray-400"
  datetime="{{ article.get('published', '') }}"
  data-knr-time
>{{ article.get('published', '') | pub_date }}</time>
```

The `pub_date` filter value is the no-JS fallback; JavaScript overwrites it on load.

---

## 33. Panel Toggle System & Mobile-Responsive Layout

### 33.1 Sub-Toggle Buttons

A sub-toggle row sits above the main bottom nav in the left sidebar. It shows context-specific panel toggle buttons depending on the active tab:

| Active Tab | Left toggle | Right toggle |
|---|---|---|
| Root | Chat | News |
| Wall | Public | My Wall |
| Profile | Profile | Score |

Both buttons are indigo (active/selected) by default. Clicking a button toggles that panel's visibility. The button turns gray when the panel is hidden. The row is always visible — both on desktop and mobile — regardless of sidebar width.

### 33.2 New `appState()` State Variables

```javascript
// Panel visibility (always resets to default on page refresh — no localStorage)
showChat: true,
showNews: true,
showWallPublic: true,
showWallPrivate: true,
showProfileMain: true,
showProfileScore: true,
isMobile: window.innerWidth < 768,
```

`isMobile` is updated via a `resize` event listener added in `init()`.

### 33.3 Panel Visibility Methods

```javascript
centerPanelVisible() {
  if (this.activeTab === 'root')    return this.showChat;
  if (this.activeTab === 'wall')    return this.showWallPublic;
  if (this.activeTab === 'profile') return this.showProfileMain;
  return true;
},

rightPanelVisible() {
  if (this.activeTab === 'root')    return this.showNews;
  if (this.activeTab === 'wall')    return this.showWallPrivate;
  if (this.activeTab === 'profile') return this.showProfileScore;
  return true;
},

togglePanel(panel) { this[panel] = !this[panel]; },
```

### 33.4 Panel Width & Fill Logic

The right `<aside>` uses a conditional `:style` binding:

```html
:style="!isMobile
  ? (centerPanelVisible()
      ? `width:${rightPanelWidth}px;min-width:200px`
      : 'flex:1 1 auto')
  : ''"
```

When the center panel is hidden (`display:none` via `x-show`), the right panel expands to fill the full content area with `flex:1 1 auto`. When both are visible, it respects the user-dragged `rightPanelWidth`. On mobile, no inline width is applied — Tailwind responsive classes govern layout instead.

### 33.5 Mobile Layout

The content wrapper changed from an implicit row to:

```html
<div class="flex-1 min-w-0 overflow-hidden flex flex-col md:flex-row">
```

On screens narrower than `md` (768 px), the three panels stack vertically:
1. Left sidebar (toggled via hamburger — unchanged)
2. Center panel (`<main>`) — takes available height
3. Right panel (`<aside>`) — fixed `h-64` on mobile, `md:h-auto` on desktop

The resize handle between center and right is `hidden md:block` — it only appears on desktop where drag-to-resize is meaningful.

### 33.6 Bottom Nav Wrapping

The main bottom nav uses `flex flex-wrap` and each button carries `min-w-[80px]`:

```html
<nav class="flex flex-wrap items-stretch border-t border-gray-700">
  <button class="flex-1 min-w-[80px] ...">Root</button>
  <button class="flex-1 min-w-[80px] ...">Wall</button>
  <button class="flex-1 min-w-[80px] ...">Profile</button>
</nav>
```

When the sidebar is narrower than 240 px (user-resized), the Profile button wraps to a second row instead of being clipped off-screen.

### 33.7 Updated State Management Summary

| State key | Type | Default | Persisted |
|---|---|---|---|
| `showChat` | bool | `true` | No |
| `showNews` | bool | `true` | No |
| `showWallPublic` | bool | `true` | No |
| `showWallPrivate` | bool | `true` | No |
| `showProfileMain` | bool | `true` | No |
| `showProfileScore` | bool | `true` | No |
| `isMobile` | bool | `window.innerWidth < 768` | No (live) |

---

## 34. Mobile Panel Height Fix

The right `<aside>` mobile height was reduced from `h-64` (256 px) to `h-40` (160 px). On a typical phone viewport (~610 px after the top nav), the previous 256 px strip left only ~354 px for the center panel — after subtracting the chat input bar (~60 px) and the "Check Knowledge" toolbar (~46 px), the scrollable messages area was only ~248 px. With `h-40` the center panel gets ~450 px, giving the messages area ~344 px — a 38 % increase.

The fix applies uniformly across all three tabs (Root / Wall / Profile) because all tabs share the single `<aside>` element. On desktop, `md:h-auto` overrides the fixed height so desktop layout is unchanged.

---

## 35. Upvote-Based Star Rating

Stars are now computed from **total upvotes received** on a user's own shares, not from the weighted point score. This separates "popularity" (stars, based on positive community signals) from "activity score" (points, which also includes downvote deductions and share bonus events).

### 35.1 Thresholds

| Upvotes received | Stars |
|---|---|
| 0 – 999 | 0 ★ |
| 1,000 – 9,999 | 1 ★ |
| 10,000 – 99,999 | 2 ★ |
| 100,000 – 999,999 | 3 ★ |
| 1,000,000 – 9,999,999 | 4 ★ |
| ≥ 10,000,000 | 5 ★ |

### 35.2 Implementation

`upvotes_to_stars(upvotes: int) -> float` in `backend/api/wall/service.py` iterates `SCORING["star_thresholds"]`. Both `get_user_score` (direct profile query) and the batch author query in `_hydrate_share_rows` (wall card author badges) pass the `upvotes` column, not the `score` column, to this function.

---

## 36. Share Score Events System

### 36.1 Design Goals

- All scoring rules live in one place (`SCORING` dict) — changing a threshold or point value requires editing a single constant.
- Business logic is isolated in a pure function (`_evaluate_reshare_events`) with no DB calls — fully unit-testable.
- Historical events are immutable snapshots — future vote changes never retroactively alter previously awarded or deducted points.

### 36.2 Centralized `SCORING` Configuration

```python
SCORING: dict = {
    "upvote_pts":         10,   # points per upvote received on own shares
    "downvote_pts":        -5,  # points per downvote received on own shares
    "reshare_bonus_pts":    5,  # first-time reshare of another user's post
    "toxic_threshold_dv":  50,  # min downvotes on source post → penalty
    "toxic_penalty_pts":  -10,  # points deducted per toxic reshare
    "star_thresholds": [1_000, 10_000, 100_000, 1_000_000, 10_000_000],
}
```

The profile score route passes this dict to the template as `scoring`, so the UI always reflects the live config values without a separate update.

### 36.3 Scoring Rules

| Rule | Condition | Amount | Dedup |
|---|---|---|---|
| Reshare bonus | First time resharing another user's post | +5 pts | Once per `(user, source_post)` — DB unique index |
| Toxic-post penalty | Source post had ≥ 50 downvotes at share time | −10 pts | None — fires every reshare |

**Not applicable:**
- Resharing your own post never earns the bonus.
- Resharing the same post a second time earns no bonus (but can still incur the penalty each time if the source remains toxic).
- Vote counts are snapshotted at share time; future votes on the source post do not affect past events.

### 36.4 Pure Evaluator Function

```python
def _evaluate_reshare_events(
    sharer_id, source_owner_id,
    snapshot_upvotes, snapshot_downvotes,
    already_has_bonus,
) -> list[dict]:
```

Returns a list of `{points, reason, snapshot_upvotes, snapshot_downvotes}` dicts. No DB calls — the caller pre-fetches all inputs. To add a new scoring rule, add a block inside this function and a new key to `SCORING`.

### 36.5 `share_score_events` Table

```sql
CREATE TABLE share_score_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    share_id            UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    source_share_id     UUID          REFERENCES shares(id) ON DELETE SET NULL,
    points              INT  NOT NULL,
    reason              VARCHAR(40) NOT NULL,  -- 'reshare_bonus' | 'toxic_penalty'
    snapshot_upvotes    INT,
    snapshot_downvotes  INT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Prevents double-awarding the reshare bonus for the same source post.
CREATE UNIQUE INDEX uq_reshare_bonus_once
    ON share_score_events (user_id, source_share_id)
    WHERE reason = 'reshare_bonus';
```

Migration: `backend/migrations/015_share_score_events.sql`.

### 36.6 Score Calculation

`get_user_score` adds a correlated subquery to the existing vote-points aggregate:

```sql
COALESCE(SUM(CASE WHEN sv.vote = 1 THEN 10 WHEN sv.vote = -1 THEN -5 ELSE 0 END), 0)
+ COALESCE((SELECT SUM(sse.points) FROM share_score_events sse WHERE sse.user_id = u.id), 0)
AS score
```

The same pattern is applied to the batch author score query in `_hydrate_share_rows` so wall card author badges also reflect event points.

### 36.7 Profile Score Modal

`backend/templates/partials/profile_score.html` was restructured:

- The "How scoring works" detail block was removed from the always-visible card.
- The card now contains a single button that opens a full modal (`x-data="{ showScoringModal: false }"`).
- The modal renders all four sections (votes, reshare bonus, toxic penalty, star milestones) using `{{ scoring.* }}` template variables sourced from the `SCORING` dict — changes to the config are reflected in the UI automatically.
