# Implementation Plan — Knowledge Root

> Companion to `ARCHITECTURE.md`. Each phase maps to one Git branch, merged to `main` via PR after passing all automated reviews and tests.
>
> **Stack:** Flask (Python) · PostgreSQL · Redis · LangGraph · OpenRouter LLM · Jinja2 + HTMX + Alpine.js · Playwright E2E · pytest

---

## Backend File Path Convention

All Python server code lives in the `backend/` package. When this plan refers to backend files, use this mapping:

| Logical name | Actual path |
|---|---|
| Flask app factory | `backend/app.py` |
| Config classes | `backend/config.py` |
| Extension singletons | `backend/extensions.py` |
| User domain model | `backend/domain/user.py` |
| User repository | `backend/repositories/user_repository.py` |
| Auth routes | `backend/api/auth/routes.py` |
| Auth service | `backend/api/auth/service.py` |
| Auth request schemas | `backend/api/auth/schemas.py` |
| Sessions routes | `backend/api/sessions/routes.py` |
| Sessions service | `backend/api/sessions/service.py` |
| Chat routes | `backend/api/chat/routes.py` |
| Chat service | `backend/api/chat/service.py` |
| News routes | `backend/api/news/routes.py` |
| News service | `backend/api/news/service.py` |
| News cache | `backend/api/news/cache.py` |
| News feeds | `backend/api/news/feeds.py` |
| Discuss routes | `backend/api/discuss/routes.py` |
| Discuss service | `backend/api/discuss/service.py` |
| Quiz routes | `backend/api/quiz/routes.py` |
| Quiz service | `backend/api/quiz/service.py` |
| MCQ generator | `backend/api/quiz/generator.py` |
| Wall routes | `backend/api/wall/routes.py` |
| Wall service | `backend/api/wall/service.py` |
| LangGraph graph | `backend/agent/graph.py` |
| Agent prompts | `backend/agent/prompts.py` |
| Agent tools | `backend/agent/tools.py` |
| Auth middleware | `backend/core/auth.py` |
| DB helpers | `backend/core/db.py` |
| LLM client factory | `backend/core/llm.py` |
| Error handlers | `backend/core/errors.py` |
| APScheduler setup | `backend/core/scheduler.py` |
| Migrations | `backend/migrations/00N_*.sql` |
| Gunicorn entry point | `wsgi.py` (project root) |
| Unit tests | `tests/unit/test_*.py` (project root) |

The Dockerfile runs: `gunicorn "wsgi:app" --bind 0.0.0.0:5000 --workers 4`

---

## Branch Strategy

```
main
 ├── feature/auth                    Phase 1
 ├── feature/session-management      Phase 2
 ├── feature/smart-news-cache        Phase 3
 ├── feature/knowledge-check         Phase 4
 ├── feature/polish                  Phase 5
 └── feature/news-discuss-learn      Phase 6
```

Each branch is opened as a PR against `main`. Automated GitHub Actions run on every PR open/sync:
- `code-review.yml` — code quality + patterns
- `security-review.yml` — OWASP + AI-specific risks
- `architecture-review.yml` — drift from `ARCHITECTURE.md`
- `ci.yml` — lint, unit tests, E2E smoke

Merge only after all checks green and PR description references affected `PROGRESS.md` items.

---

## Test Strategy

| Layer           | Tool                  | Location              | When runs          |
|-----------------|-----------------------|-----------------------|--------------------|
| Backend unit    | pytest + pytest-flask | `tests/unit/`         | `ci.yml` on PR     |
| Template/view   | pytest + Flask client | `tests/unit/test_pages.py` | `ci.yml` on PR |
| E2E             | Playwright            | `e2e/*.spec.ts`       | `ci.yml` on PR     |
| Static analysis | flake8 + mypy         | `backend/`            | `ci.yml` on PR     |

No frontend unit tests (no React component logic to isolate). Template rendering is tested via the Flask test client in pytest (assert HTML response codes, content, redirects).

**Backend test structure:**
```
tests/
  conftest.py          ← pytest fixtures: test app, test DB, test Redis, auth helpers
  unit/
    test_auth.py       ← register/login/logout routes + service logic
    test_pages.py      ← page routes: status codes, redirects, auth guards
    test_sessions.py
    test_news.py
    test_quiz.py
  integration/         ← optional, hits real DB in CI
```

**E2E structure:**
```
e2e/
  fixtures.ts          ← Playwright fixtures: logged-in page, seeded session
  auth.spec.ts
  sessions.spec.ts
  news.spec.ts
  quiz.spec.ts
  full-flow.spec.ts    ← register → chat → quiz golden path
```

---

## Phase 1 — Authentication (`feature/auth`)

### Goal
Users can register, log in, refresh their session, and log out. All existing routes are protected by JWT middleware.

### New Files
```
backend/app.py                         ← create_app() factory
backend/config.py                      ← Config / DevelopmentConfig / ProductionConfig / TestingConfig
backend/extensions.py                  ← db_pool, redis_client, limiter, session singletons
backend/domain/__init__.py
backend/domain/user.py                 ← User frozen dataclass + to_profile() method
backend/repositories/__init__.py
backend/repositories/user_repository.py  ← UserRepository class + user_repo module-level singleton
backend/api/__init__.py
backend/api/auth/__init__.py
backend/api/auth/routes.py             ← Blueprint('/auth'): register, login, logout, me
backend/api/auth/schemas.py            ← Pydantic v2: RegisterRequest, LoginRequest
backend/api/auth/service.py            ← register_user(), login_user(), get_user() — uses user_repo
backend/api/pages/__init__.py
backend/api/pages/routes.py            ← Blueprint('pages'): /, /login, /register, /app, /quiz/<id>, /learn/<id>
backend/core/__init__.py
backend/core/auth.py                   ← require_auth (page redirect), require_api_auth (401 JSON)
backend/core/db.py                     ← query(), query_one(), execute(), run_migrations()
backend/core/errors.py                 ← AppError hierarchy, register_error_handlers(app)
backend/core/llm.py                    ← build_llm_client() factory
backend/migrations/001_users.sql       ← users table DDL
backend/templates/base.html            ← HTML shell: CDN links (HTMX, Alpine.js, Tailwind)
backend/templates/auth/login.html      ← Login form (HTMX post, inline error swap)
backend/templates/auth/register.html   ← Register form
wsgi.py                                ← from backend.app import create_app; app = create_app()
tests/conftest.py                      ← app fixture (TestingConfig), authed_client fixture (session_transaction)
tests/unit/test_auth.py
tests/unit/test_pages.py               ← page route status codes, redirects, auth guards
e2e/auth.spec.ts
```

### Modified Files
```
requirements.txt       ← add flask-session, bcrypt, flask-limiter; remove PyJWT
docker-compose.yml     ← add SESSION_SECRET_KEY env var; remove frontend service; Dockerfile CMD → gunicorn wsgi:app
Dockerfile             ← CMD: gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 4
Makefile               ← replace package.json scripts with make targets
```

### Backend Tasks

#### 1.1 DB Migration — `migrations/001_users.sql`
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
CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
```
Run migration in `app.py` startup (same pattern as `PostgresSaver.setup()`).

#### 1.2 `backend/domain/user.py`, `backend/repositories/user_repository.py`, `backend/api/auth/schemas.py`, `backend/api/auth/service.py`, `backend/api/auth/routes.py`

**Domain model (`domain/user.py`):**
- `User` is a frozen `@dataclass` — no Flask, no DB imports.
- Fields: `id`, `username`, `email`, `full_name`, `created_at`, `phone` (optional).
- `to_profile()` returns a dict safe for JSON serialisation (no password hash).

**Repository (`repositories/user_repository.py`):**
- `UserRepository` encapsulates all SQL; returns `User` objects, never raw dicts.
- Methods: `find_by_id()`, `find_for_auth()` (returns `(User, hash)` or `None`), `exists_by_username()`, `exists_by_email()`, `create()`.
- Module-level singleton: `user_repo = UserRepository()`.

**Pydantic schemas (`api/auth/schemas.py`):**
- `RegisterRequest` — validates username (3–50, `^[a-zA-Z0-9_]+$`), email (RFC 5322), phone (E.164 optional), full_name, password (≥ 8 chars, ≥ 1 digit, ≥ 1 letter) via `@model_validator(mode='after')`.
- `LoginRequest` — validates `identifier` and `password` are non-empty.
- On failure: `@model_validator` raises `ValueError(dict)` → route `_parse()` converts to `UnprocessableError(fields={...})`.

**`POST /auth/register`**
- Route calls `_parse(RegisterRequest, _get_data())`, then `auth_service.register_user(username, email, full_name, password, phone)`.
- Service checks `user_repo.exists_by_username()` / `exists_by_email()` — raises `ConflictError` on conflict.
- `bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))` in service, then `user_repo.create(...)`.
- `session['user_id'] = user.id`, `session.permanent = True`. HTMX: 204 + `HX-Redirect`. Browser: 302.

**`POST /auth/login`**
- Route calls `_parse(LoginRequest, _get_data())`, then `auth_service.login_user(identifier, password)`.
- Service calls `user_repo.find_for_auth(identifier)` (tries username then email), `bcrypt.checkpw()`.
- On success: set session, redirect. On failure: raise `UnauthorizedError`.

**`POST /auth/logout`**
- `session.clear()` — deletes the server-side session from Redis. Redirect to `/login`.

**`GET /auth/me`** (requires `@require_api_auth`)
- Return `auth_service.get_user(g.user_id).to_profile()` as JSON.

#### 1.3 `backend/core/auth.py`
```python
def require_auth(f):
    # Page routes: redirect to /login if session missing
    # Sets g.user_id = session['user_id']

def require_api_auth(f):
    # HTMX/JSON endpoints: return 401 JSON if session missing
```
Rate limit `/auth/login` and `/auth/register` via `limiter` from `backend/extensions.py`.

### Template Tasks

#### 1.4 Page Routes (`backend/api/pages/routes.py`)
```python
GET /       → redirect to /app if session active, else /login
GET /login  → render auth/login.html
GET /register → render auth/register.html
GET /app    → render app/index.html  [require_auth]
```

#### 1.5 `backend/templates/base.html`
Include in `<head>`:
```html
<script src="https://unpkg.com/htmx.org@2/dist/htmx.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
<link rel="stylesheet" href="https://cdn.tailwindcss.com">
```
Layout: nav bar with username + logout button (if session active), `{% block content %}`.

#### 1.6 `backend/templates/auth/login.html`
Fields: identifier (label: "Username or Email"), password (Alpine.js show/hide toggle).
```html
<form hx-post="/auth/login" hx-target="#form-error" hx-swap="innerHTML">
  <div id="form-error"></div>
  ...
</form>
```
On success: server sends `HX-Redirect: /app`. On failure: server returns error HTML fragment.

#### 1.7 `backend/templates/auth/register.html`
Fields: full_name, username, email, phone (optional), password + confirm_password (both with show/hide).
Client-side password-match validation via Alpine.js before HTMX submit.
On success: server sets session, sends `HX-Redirect: /app`.

### Unit Tests

#### Backend — `tests/unit/test_auth.py`
```python
# Key fixtures in conftest.py:
#   client: Flask test client (TestingConfig — no Redis session, cookie session)
#   authed_client: client with session['user_id'] pre-set via session_transaction()
#   valid_user_payload: dict with all required registration fields
#
# Mocking pattern — patch the repository singleton, NOT raw DB helpers:
#   REPO = 'backend.repositories.user_repository.user_repo'
#   mocker.patch(f'{REPO}.exists_by_username', return_value=False)
#   mocker.patch(f'{REPO}.create', return_value=_USER)  # _USER is a User domain object

def test_register_success_redirects(client, valid_user_payload, mocker): ...          # 302
def test_register_success_sets_session(client, valid_user_payload, mocker): ...        # sess['user_id']
def test_register_htmx_returns_204_with_hx_redirect(client, valid_user_payload, mocker): ...
def test_register_duplicate_username_returns_409(client, valid_user_payload, mocker): ...
def test_register_duplicate_email_returns_409(client, valid_user_payload, mocker): ...
def test_register_weak_password_returns_422(client): ...
def test_register_invalid_email_returns_422(client): ...
def test_register_invalid_username_returns_422(client): ...
def test_register_invalid_phone_returns_422(client): ...
def test_register_missing_full_name_returns_422(client): ...
def test_login_success_redirects(client, mocker): ...
def test_login_success_sets_session(client, mocker): ...
def test_login_htmx_returns_204_with_hx_redirect(client, mocker): ...
def test_login_by_email_succeeds(client, mocker): ...
def test_login_wrong_password_returns_401(client, mocker): ...
def test_login_unknown_user_returns_401(client, mocker): ...
def test_login_missing_fields_returns_422(client): ...
def test_logout_clears_session(authed_client): ...
def test_logout_without_session_still_redirects(client): ...
def test_logout_htmx_returns_204_with_hx_redirect(authed_client): ...
def test_me_without_session_returns_401(client): ...
def test_me_with_session_returns_profile(authed_client, mocker): ...
def test_me_user_not_found_returns_401(authed_client, mocker): ...
def test_rate_limit_on_login(client): ...
```

#### Page Routes — `tests/unit/test_pages.py`
```python
def test_index_redirects_unauthenticated_to_login(client): ...
def test_index_renders_for_authenticated_user(authed_client): ...
def test_login_page_returns_200(client): ...
def test_register_page_returns_200(client): ...
def test_app_page_requires_auth_redirects_to_login(client): ...
def test_app_page_returns_200_when_authenticated(authed_client): ...
def test_login_page_redirects_already_authenticated(authed_client): ...
def test_register_page_redirects_already_authenticated(authed_client): ...
```

### E2E Tests — `e2e/auth.spec.ts`
```ts
test('user can register with valid data and is redirected to /app')
test('register with existing username shows inline error')
test('user can log in with username')
test('user can log in with email')
test('wrong password shows inline error')
test('unauthenticated user redirected from /app to /login')
test('user can log out and cannot access /app')
test('session cookie persists across page reloads')
```

---

## Phase 2 — Session Management (`feature/session-management`)

### Goal
Authenticated users have a persistent left-pane chat history. Sessions are created, auto-titled, renamed, and deleted. The `/chat` endpoint is scoped to sessions owned by the requesting user.

### New Files
```
backend/api/sessions/__init__.py
backend/api/sessions/routes.py         ← Blueprint('/sessions'): CRUD + messages
backend/api/sessions/service.py        ← create_session(), list_sessions(), rename(), delete(), get_messages()
backend/api/chat/__init__.py
backend/api/chat/routes.py             ← Blueprint('/chat'): POST /chat
backend/api/chat/service.py            ← send_message(), auto_title(), extract_suggested_topics()
backend/migrations/002_chat_sessions.sql
tests/unit/test_sessions.py
tests/unit/test_chat.py
frontend/src/components/ChatSidebar.tsx
frontend/src/components/SessionItem.tsx
frontend/src/hooks/useSessions.ts
frontend/src/api/sessions.ts
frontend/src/components/ChatSidebar.test.tsx
frontend/src/components/SessionItem.test.tsx
frontend/src/hooks/useSessions.test.ts
e2e/sessions.spec.ts
```

### Modified Files
```
backend/app.py              ← register sessions + chat blueprints
backend/agent/graph.py      ← auto-title generation after first reply
backend/agent/prompts.py    ← add SUGGESTED_TOPICS_PROMPT, AUTO_TITLE_PROMPT constants
frontend/src/App.tsx        ← add ChatSidebar to left pane
frontend/src/hooks/useChat.ts ← accept session_id, pass to API; handle suggested_topics in response
frontend/src/types/index.ts ← add suggested_topics to ChatResponse type
```

### Backend Tasks

#### 2.1 DB Migration — `migrations/002_chat_sessions.sql`
```sql
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id       VARCHAR(255) UNIQUE NOT NULL,
    title           VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sessions_user_last ON chat_sessions(user_id, last_message_at DESC);
```

#### 2.2 `sessions.py` Endpoints

**`POST /sessions`** — creates session, returns `{id, thread_id, title: null, created_at}`.
**`GET /sessions`** — list user's sessions ordered by `last_message_at DESC`, returns `[{id, title, last_message_at, created_at}]`.
**`PATCH /sessions/{id}`** — rename: body `{title}`. Verify `user_id` ownership or return `403`.
**`DELETE /sessions/{id}`** — delete session row + LangGraph checkpoint deletion. Verify ownership.

#### 2.3 Update `POST /chat`
- Require `session_id` in request body.
- Verify `chat_sessions.user_id = g.user_id` (ownership check).
- Use session's `thread_id` as LangGraph config key.
- After first assistant reply: trigger auto-title if `title IS NULL`.
- Update `last_message_at = NOW()` on each message.
- Return `title` in response (may be newly generated).

#### 2.4 Auto-Title Generation (`agent.py`)
After first AI reply, call LLM with:
```
Generate a 4-6 word technical chat title. No punctuation or filler words.
User said: "{first_user_message}"
AI replied: "{first_100_chars_of_reply}"
Reply ONLY with the title.
```
Store result in `chat_sessions.title`. If LLM call fails, fall back to first 40 chars of user message.

#### 2.5 `GET /sessions/{id}/messages`
Replay full message history from LangGraph state for the session's thread_id. Return `[{role, content, timestamp}]`.

### Frontend Tasks

#### 2.6 Layout Update (`App.tsx`)
```
┌──────────────────┬──────────────────────────┬───────────┐
│  ChatSidebar     │   Chat (centre)           │  News     │
│  w-60 xl:w-72    │   flex-1                 │  w-80     │
│  border-r        │                           │  border-l │
└──────────────────┴──────────────────────────┴───────────┘
```
ChatSidebar hidden on mobile (slide-in drawer on hamburger).

#### 2.7 `ChatSidebar.tsx`
- Header: "Chats" title + "New Chat" button (+ icon).
- Groups: Today / Yesterday / This Week / Older (derive from `last_message_at`).
- Each `SessionItem`: title (truncated 32 chars), relative time, hover reveals rename (pencil) + delete (trash) icons.
- Active session highlighted.
- Loading: 5 skeleton lines on first load.
- Empty state: "No chats yet. Start a new conversation."

#### 2.8 `useSessions.ts`
Wraps React Query:
- `sessions` list (auto-refetch on window focus).
- `createSession()` → optimistic insert.
- `renameSession(id, title)` → optimistic update.
- `deleteSession(id)` → optimistic remove.
- Exposes `activeSessionId` and `setActiveSession(id)`.

### Unit Tests

#### Backend — `tests/unit/test_sessions.py`
```python
def test_create_session_returns_201(auth_client): ...
def test_list_sessions_returns_user_only(auth_client, other_user_client): ...
def test_rename_session_success(auth_client, session_id): ...
def test_rename_other_users_session_returns_403(auth_client, other_session_id): ...
def test_delete_session_success(auth_client, session_id): ...
def test_delete_other_users_session_returns_403(auth_client, other_session_id): ...
def test_chat_without_session_returns_400(auth_client): ...
def test_chat_with_valid_session_succeeds(auth_client, session_id): ...
def test_chat_with_other_users_session_returns_403(auth_client, other_session_id): ...
def test_auto_title_set_after_first_reply(auth_client, session_id): ...
def test_get_messages_for_session(auth_client, session_with_messages): ...
```

#### Frontend — `src/components/ChatSidebar.test.tsx`
```ts
test('renders session list grouped by date')
test('shows skeleton on loading')
test('shows empty state when no sessions')
test('new chat button calls createSession')
test('clicking session sets it active')
test('rename icon shows inline input')
test('delete icon shows confirmation then removes session')
test('only shows sessions for current user')
```

#### Frontend — `src/hooks/useSessions.test.ts`
```ts
test('fetches sessions on mount')
test('createSession optimistically adds to list')
test('renameSession updates title optimistically')
test('deleteSession removes from list optimistically')
test('active session id persists across renders')
```

### E2E Tests — `e2e/sessions.spec.ts`
```ts
test('new chat creates a session in the sidebar')
test('session gets auto-title after first message')
test('user can rename a session')
test('user can delete a session')
test('deleted session is no longer in sidebar')
test('switching sessions loads correct message history')
test('sessions from other users are not visible')
```

---

## Phase 3 — Smart News Cache (`feature/smart-news-cache`)

### Goal
Replace the single in-memory 30-minute cache with a Redis-backed day/hour split cache. Older articles come from the stable day cache; current-hour articles are fetched fresh. A background job promotes hourly cache into the day cache.

### New Files
```
backend/api/news/__init__.py
backend/api/news/routes.py          ← Blueprint('/news'): GET /news?category=
backend/api/news/service.py         ← get_news(category, force)
backend/api/news/cache.py           ← Redis day/hour cache, DB fallback, promote_hour_to_day()
backend/api/news/feeds.py           ← NEWS_FEEDS dict keyed by 'ai'|'programming'|'political'
backend/core/scheduler.py           ← init_scheduler(app) + promote job
backend/migrations/003_news_cache.sql
tests/unit/test_news.py
frontend/src/components/NewsPanel.test.tsx
```

### Modified Files
```
backend/app.py              ← register news blueprint, init APScheduler via core/scheduler.py
backend/extensions.py       ← add redis_client + scheduler instances
docker-compose.yml          ← add Redis service, REDIS_URL env var
requirements.txt            ← add redis, APScheduler, fakeredis (test dep)
frontend/src/components/NewsPanel.tsx ← article timestamps, per-source grouping
frontend/src/hooks/useNews.ts         ← updated response type
frontend/src/types/index.ts           ← NewsArticle type
```

### Backend Tasks

#### 3.1 Redis Service (docker-compose.yml)
```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
  volumes:
    - redisdata:/data
```

#### 3.2 DB Migration — `migrations/003_news_cache.sql`
```sql
CREATE TABLE news_cache (
    cache_key  VARCHAR(20) PRIMARY KEY,
    articles   JSONB       NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

#### 3.3 `cache/news.py` — Cache Algorithm

```python
DAY_TTL  = seconds_until_midnight_utc()
HOUR_TTL = 3600

def get_news() -> list[Article]:
    today   = utc_now().strftime("%Y-%m-%d")
    cur_hour = utc_now().strftime("%Y-%m-%d-%H")

    hour_key = f"news:hour:{cur_hour}"
    day_key  = f"news:day:{today}"

    # 1. Try hour cache (Redis → DB fallback)
    hour_articles = redis_get(hour_key) or db_get(hour_key)
    if hour_articles is None:
        hour_articles = fetch_from_rss(since=start_of_current_hour())
        redis_set(hour_key, hour_articles, ex=HOUR_TTL)
        db_upsert(hour_key, hour_articles, ttl=HOUR_TTL)

    # 2. Try day cache (Redis → DB fallback)
    day_articles = redis_get(day_key) or db_get(day_key)
    if day_articles is None:
        day_articles = []
        redis_set(day_key, day_articles, ex=DAY_TTL)

    # 3. Merge: day (stable older) + hour (fresh current)
    return merge_dedupe(day_articles, hour_articles, key="link")[:20]

def promote_hour_to_day():
    """APScheduler job — runs at :00 of each hour."""
    prev_hour = (utc_now() - timedelta(hours=1)).strftime("%Y-%m-%d-%H")
    today     = utc_now().strftime("%Y-%m-%d")
    prev_articles = redis_get(f"news:hour:{prev_hour}") or db_get(f"news:hour:{prev_hour}")
    if prev_articles:
        day_articles = redis_get(f"news:day:{today}") or []
        merged = merge_dedupe(day_articles, prev_articles, key="link")
        redis_set(f"news:day:{today}", merged, ex=seconds_until_midnight_utc())
        db_upsert(f"news:day:{today}", merged, ttl=seconds_until_midnight_utc())
```

#### 3.4 Article Schema
```python
@dataclass
class Article:
    id:        str   # sha256(link)[:12]
    source:    str
    title:     str
    link:      str
    summary:   str
    published: str   # ISO 8601
    hour_slot: str   # "2026-05-04-09"
```

#### 3.5 APScheduler Setup (`app.py`)
```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(promote_hour_to_day, 'cron', minute=0)
scheduler.start()
```

#### 3.6 `GET /news` Updates
- Optional `?force=true` query param bypasses hour cache (for manual refresh button).
- Returns `{articles: [...], cache_hit: bool, fetched_at: str}`.

### Frontend Tasks

#### 3.7 `NewsArticle` Type (`types/index.ts`)
```ts
export interface NewsArticle {
  id:        string
  source:    string
  title:     string
  link:      string
  summary:   string
  published: string
  hour_slot: string
}
```

#### 3.8 Updated `NewsPanel.tsx`
- Group articles by `source` with collapsible sections.
- Each article: title (link), summary (2 lines truncated), relative time ("2h ago").
- "Refresh" button calls `GET /news?force=true`.
- Badge: "Updated X min ago" based on `fetched_at` from API.
- Skeleton cards (3 per source) while loading.

### Unit Tests

#### Backend — `tests/unit/test_news.py`
```python
def test_get_news_returns_articles(mock_redis, mock_rss): ...
def test_hour_cache_hit_skips_rss_fetch(mock_redis_with_hour_cache, mock_rss): ...
def test_day_cache_used_for_older_articles(mock_redis): ...
def test_force_true_bypasses_hour_cache(mock_redis): ...
def test_promote_hour_to_day_merges_correctly(mock_redis): ...
def test_deduplication_by_link(mock_redis): ...
def test_db_fallback_when_redis_unavailable(mock_redis_down, mock_db): ...
def test_empty_feed_returns_gracefully(mock_empty_rss): ...
def test_article_id_is_stable_hash_of_link(): ...
```

#### Frontend — `src/components/NewsPanel.test.tsx`
```ts
test('renders articles grouped by source')
test('shows relative timestamps')
test('shows skeleton while loading')
test('refresh button triggers force fetch')
test('shows error state on fetch failure')
test('truncates long summaries to 2 lines')
test('article title is a link to original URL')
```

### E2E Tests — `e2e/news.spec.ts`
```ts
test('news panel loads on app open')
test('articles are grouped by source')
test('refresh button loads updated news')
test('news persists across page navigation within session')
```

---

## Phase 4 — Knowledge Check (`feature/knowledge-check`)

### Goal
Users can generate technical MCQs from any chat session, answer them in a new tab, auto-save progress, and retry.

### New Files
```
backend/api/quiz/__init__.py
backend/api/quiz/routes.py         ← Blueprint('/quiz'): all quiz endpoints
backend/api/quiz/service.py        ← attempt lifecycle: generate, save, submit, retry, relearn
backend/api/quiz/generator.py      ← MCQ LLM prompt + validation; relearn prompt + caching
backend/migrations/004_mcq_attempts.sql
tests/unit/test_quiz.py
frontend/src/pages/QuizPage.tsx
frontend/src/components/MCQCard.tsx
frontend/src/components/QuizResult.tsx
frontend/src/hooks/useQuiz.ts
frontend/src/api/quiz.ts
frontend/src/pages/QuizPage.test.tsx
frontend/src/components/MCQCard.test.tsx
frontend/src/hooks/useQuiz.test.ts
e2e/quiz.spec.ts
```

### Modified Files
```
backend/app.py                        ← register quiz blueprint
backend/agent/prompts.py              ← add MCQ_GENERATION_PROMPT constant
frontend/src/App.tsx                  ← add /quiz/:attemptId route
frontend/src/components/InputBar.tsx  ← add "Check Knowledge" button (detects session type)
```

### Backend Tasks

#### 4.1 DB Migration — `migrations/004_mcq_attempts.sql`
```sql
CREATE TABLE mcq_attempts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id   UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    questions    JSONB NOT NULL,
    answers      JSONB,
    score        SMALLINT,
    attempted_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_mcq_session ON mcq_attempts(session_id);
```

#### 4.2 `quiz.py` Endpoints

**`POST /quiz/generate`** — body: `{session_id}`
1. Verify session ownership.
2. Load conversation from LangGraph state (thread_id of session).
3. Filter out small-talk turns (skip turns < 30 chars from user).
4. Call LLM with the MCQ generation prompt (see ARCHITECTURE.md §8.3).
5. Parse and validate JSON response (8 questions, each with 4 options, `correct` 0–3).
6. Insert into `mcq_attempts` with `answers=null`, `score=null`. Return `attempt_id` + questions WITHOUT `correct` field.

**`GET /quiz/attempt/{id}`** — load saved state
- Verify ownership.
- Return `{attempt_id, questions (without correct), answers, score, completed_at}`.
- If `completed_at IS NOT NULL`, include `correct` fields so user can review answers.

**`PUT /quiz/attempt/{id}`** — auto-save answers
- Body: `{answers: {q_01: 1, ...}}`.
- Verify ownership.
- Upsert `answers` in DB.
- If body includes `completed: true`: compute score, set `completed_at`, return full questions WITH `correct`.

**`POST /quiz/retry`** — body: `{session_id}`
- Find latest `mcq_attempts` row for this session.
- Create NEW row with same `questions`, `answers=null`, `score=null`.
- Return new `attempt_id`.

**`GET /quiz/attempts`** — query: `?session_id=uuid`
- Return list of attempts for session (score, attempted_at, completed_at) for history display.

#### 4.3 MCQ Validation
After LLM response, validate:
- Exactly 8 questions.
- Each question has `id`, `text`, `options` (exactly 4), `correct` (0–3 int).
- No question text is shorter than 15 chars.
- No duplicate question IDs.
- If validation fails: retry LLM call once; if still invalid, return `503`.

### Frontend Tasks

#### 4.4 "Check Knowledge" Button (`InputBar.tsx` or below `MessageList`)
- Renders only when active session has ≥ 3 assistant messages.
- On click: POST to `/quiz/generate`, then `window.open('/quiz/{attempt_id}', '_blank')`.
- Button state: idle / generating (spinner) / error (try again).

#### 4.5 `/quiz/:attemptId` Page (`Quiz.tsx`)

**Layout:**
```
┌────────────────────────────────────────────────────┐
│ Knowledge Check · {session title}                  │
│ {score} / 8          [Submit]   [Back to Chat]     │
├────────────────────────────────────────────────────┤
│ Q1 card                                            │
│ Q2 card                                            │
│ ...                                                │
├────────────────────────────────────────────────────┤
│ [Retry]                                            │
└────────────────────────────────────────────────────┘
```

**Behaviour:**
- On mount: fetch attempt from `GET /quiz/attempt/{id}` to restore any saved answers.
- If `completed_at` is set: render in review mode (correct/wrong highlighted, no editing).
- Otherwise: render in active mode (selectable options).
- Each selection: update local state + debounced 500ms auto-save `PUT /quiz/attempt/{id}`.
- Submit: PUT with `{answers, completed: true}`, transition to review mode, show score.
- Retry: POST `/quiz/retry`, `window.location.href = '/quiz/{new_attempt_id}'`.

#### 4.6 `MCQCard.tsx`
Props: `question`, `selectedOption`, `onSelect`, `mode: 'active' | 'review'`, `correctOption?`
- Active mode: radio-style selectable options.
- Review mode: green for correct, red for wrong selection, green outline for correct if user was wrong.

#### 4.7 `useQuiz.ts`
- Loads attempt on mount.
- `selectAnswer(questionId, optionIndex)` → updates local + triggers debounced save.
- `submitQuiz()` → PUT with `completed: true`.
- `isCompleted`, `score` derived state.

### Unit Tests

#### Backend — `tests/unit/test_quiz.py`
```python
def test_generate_quiz_returns_8_questions(auth_client, session_with_messages): ...
def test_generate_quiz_questions_have_no_correct_field(auth_client, session): ...
def test_generate_quiz_for_other_users_session_returns_403(auth_client): ...
def test_get_attempt_returns_saved_answers(auth_client, attempt_with_answers): ...
def test_get_completed_attempt_includes_correct_field(auth_client, completed_attempt): ...
def test_autosave_updates_answers(auth_client, open_attempt): ...
def test_submit_scores_correctly(auth_client, open_attempt): ...
def test_submit_sets_completed_at(auth_client, open_attempt): ...
def test_retry_creates_new_attempt_same_questions(auth_client, completed_attempt): ...
def test_get_attempts_returns_history(auth_client, session_with_attempts): ...
def test_mcq_validation_rejects_less_than_8_questions(mock_llm_bad_response): ...
def test_ownership_check_on_put_attempt(other_user_client, attempt_id): ...
```

#### Frontend — `src/pages/Quiz.test.tsx`
```ts
test('loads saved answers on mount')
test('renders review mode for completed attempt')
test('each option click updates selection')
test('answer is auto-saved after 500ms debounce')
test('submit transitions to review mode')
test('score is displayed after submit')
test('retry opens new attempt URL')
test('back to chat button navigates to /app')
```

#### Frontend — `src/components/MCQCard.test.tsx`
```ts
test('renders question text and 4 options')
test('clicking option calls onSelect with index')
test('selected option is highlighted')
test('review mode correct option is green')
test('review mode wrong selection is red with correct shown green')
test('review mode options are not clickable')
```

#### Frontend — `src/hooks/useQuiz.test.ts`
```ts
test('fetches attempt on mount')
test('selectAnswer updates answers state')
test('selectAnswer triggers debounced PUT after 500ms')
test('submitQuiz calls PUT with completed: true')
test('score computed from correct answers after submit')
test('isCompleted is true for completed attempt')
```

### E2E Tests — `e2e/quiz.spec.ts`
```ts
test('check knowledge button appears after 3 AI replies')
test('clicking check knowledge opens quiz in new tab')
test('quiz loads with 8 questions')
test('selecting an answer saves it (visible on reload)')
test('submitting quiz shows score and highlights answers')
test('correct answer is green, wrong answer is red in review')
test('retry creates fresh attempt with same questions')
test('quiz page shows session title in header')
```

---

## Phase 5 — Polish & Hardening (`feature/polish`)

### Goal
Rate limiting on auth, refresh token rotation with Redis blocklist, mobile-responsive layout, error boundaries, toast notifications, and the golden-path E2E covering the full user journey.

### Tasks

#### 5.1 Security Hardening
- `flask-limiter`: 5 req/min per IP on `/auth/login`; 3 req/min on `/auth/register`.
- Refresh token rotation already done in Phase 1 — add `REVOKED_TOKENS` Redis set as double-check.
- Add `Content-Security-Policy` header via Flask `after_request`.
- Ensure no stack traces in error responses when `FLASK_ENV=production`.

#### 5.2 Mobile Layout
- ChatSidebar: slide-in drawer behind hamburger menu (≤ lg breakpoint).
- NewsPanel: bottom sheet on mobile (swipe-up drawer).
- Quiz page: full-screen, single-column card layout on mobile.

#### 5.3 Error Boundaries
- React `ErrorBoundary` wrapper around ChatSidebar, NewsPanel, Quiz page.
- Fallback UI: "Something went wrong. Reload the page."

#### 5.4 Toast Notifications
- Use `sonner` (lightweight, no heavy dependency).
- Events: session renamed, session deleted, quiz submitted, auto-save failed (warning).

#### 5.5 Additional Unit Tests
```python
# tests/unit/test_rate_limiting.py
def test_login_rate_limit_after_5_requests(): ...
def test_register_rate_limit_after_3_requests(): ...
```

### E2E Tests — `e2e/full-flow.spec.ts`
```ts
test('golden path: register → chat → receive auto-title → check knowledge → answer → submit → score')
test('returning user: login → see previous session → resume chat → retry quiz')
test('news panel loads and refreshes without breaking chat')
test('mobile: hamburger opens sidebar, session selected, sidebar closes')
```

---

---

## Phase 6 — News Tabs, Discuss & Learning Tree (`feature/news-discuss-learn`)

### Goal
Transform the right-side news panel into a three-tab group (AI / Programming / Political). Add a **Discuss** button on each article that opens a new learning chat in the main pane with sectioned AI responses. Each section has a **[Learn More →]** button that opens a dedicated `/learn/:id` tab with a knowledge tree in the right pane. The learning chain can go arbitrarily deep. **[Check Knowledge]** at any depth generates MCQs covering the whole ancestry path, with per-question Relearn explanations for wrong answers and **[Explore deeper]** for correct answers.

### New Files
```
backend/api/discuss/__init__.py
backend/api/discuss/routes.py      ← Blueprint('/') for /news/discuss + /sessions/{id}/learn-more + /sessions/{id}/tree
backend/api/discuss/service.py     ← news_discuss(), create_learn_more_session(), get_tree()
backend/migrations/005_session_hierarchy.sql
tests/unit/test_discuss.py
tests/unit/test_news_categories.py
tests/unit/test_hierarchical_quiz.py

frontend/src/pages/LearnPage.tsx           ← /learn/:sessionId route
frontend/src/components/NewsTabs.tsx       ← tab group wrapper
frontend/src/components/NewsArticleCard.tsx← article card + Discuss button
frontend/src/components/SectionedMessage.tsx ← sectioned AI response renderer
frontend/src/components/KnowledgeTree.tsx  ← right pane hierarchy tree
frontend/src/components/TreeNode.tsx       ← single tree node
frontend/src/components/RelearPanel.tsx    ← wrong-answer relearn card
frontend/src/hooks/useDiscuss.ts
frontend/src/hooks/useLearnMore.ts
frontend/src/hooks/useSessionTree.ts
frontend/src/hooks/useHierarchicalQuiz.ts

frontend/src/components/NewsTabs.test.tsx
frontend/src/components/NewsArticleCard.test.tsx
frontend/src/components/SectionedMessage.test.tsx
frontend/src/components/KnowledgeTree.test.tsx
frontend/src/components/RelearPanel.test.tsx
frontend/src/hooks/useDiscuss.test.ts
frontend/src/hooks/useLearnMore.test.ts
frontend/src/hooks/useSessionTree.test.ts
frontend/src/hooks/useHierarchicalQuiz.test.ts
e2e/discuss.spec.ts
e2e/learn-more.spec.ts
e2e/hierarchical-quiz.spec.ts
```

### Modified Files
```
backend/api/news/cache.py           ← add category param + category-keyed cache keys
backend/api/news/feeds.py           ← add programming + political feed lists
backend/api/news/service.py         ← get_news(category, force) — extend signature
backend/api/quiz/service.py         ← add generate_hierarchical(), relearn() methods
backend/api/quiz/generator.py       ← add HIERARCHICAL_MCQ_PROMPT, RELEARN_PROMPT constants
backend/api/sessions/service.py     ← update list_sessions() to include new session_type columns
backend/app.py                      ← register discuss blueprint
backend/agent/prompts.py            ← add DISCUSSION_PROMPT, LEARN_MORE_PROMPT constants
frontend/src/App.tsx                ← add /learn/:sessionId route
frontend/src/components/ChatSidebar.tsx  ← nested tree rendering
frontend/src/components/NewsPanel.tsx    ← replaced by NewsTabs wrapper
frontend/src/types/index.ts             ← new types: Section, SectionedResponse, TreeNode, SessionType
```

### Backend Tasks

#### 6.1 DB Migration — `migrations/005_session_hierarchy.sql`
```sql
ALTER TABLE chat_sessions
    ADD COLUMN session_type      VARCHAR(20) NOT NULL DEFAULT 'regular',
    ADD COLUMN parent_session_id UUID        REFERENCES chat_sessions(id),
    ADD COLUMN root_session_id   UUID        REFERENCES chat_sessions(id),
    ADD COLUMN depth_level       INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN topic             VARCHAR(500),
    ADD COLUMN news_article_id   VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_sessions_parent ON chat_sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_root   ON chat_sessions(root_session_id);

ALTER TABLE mcq_attempts
    ADD COLUMN scope_sessions JSONB,
    ADD COLUMN relearn_cache  JSONB DEFAULT '{}';
```

#### 6.2 News Category Extension (`cache/news.py`)
- Add `NEWS_FEEDS` dict keyed by `'ai'`, `'programming'`, `'political'` (see ARCHITECTURE.md §16.2).
- `get_news(category: str = 'ai', force: bool = False)` — update cache key to `news:day:{date}:{category}` and `news:hour:{date-hour}:{category}`.
- `promote_hour_to_day()` APScheduler job now iterates all three categories.
- `GET /news?category=ai` defaults to `ai`; accepts `programming` or `political`.
- Pre-warm all three categories at startup.

#### 6.3 `backend/api/discuss/service.py` — `news_discuss()` + `routes.py` — `POST /news/discuss`
1. Validate `article_id`, `article_title`, `article_summary`, `article_link` in body.
2. Create `chat_sessions` row: `session_type='news_discussion'`, `news_article_id=article_id`, `root_session_id=self.id`, `depth_level=0`, `title=article_title[:80]`.
3. Call LangGraph with discussion system prompt + article content.
4. Parse and validate sectioned JSON response (see ARCHITECTURE.md §18.1). Retry once on failure.
5. Store first AI response in LangGraph checkpoint.
6. Return `{session_id, thread_id, title, first_response}`.

#### 6.4 `backend/api/discuss/service.py` — `create_learn_more_session()`
1. Verify ownership of session `id`.
2. Validate `topic` (1–500 chars) in body.
3. Create new `chat_sessions`: `session_type='learn_more'`, `parent_session_id=id`, `root_session_id=parent.root_session_id`, `depth_level=parent.depth_level+1`, `topic=request.topic`.
4. Call LangGraph with learn_more system prompt + topic.
5. Parse and validate sectioned response. Retry once on failure.
6. Return `{session_id, thread_id, title}`. Frontend opens `/learn/{session_id}` in new tab.

#### 6.5 `backend/api/discuss/service.py` — `get_tree()`
1. Verify ownership.
2. Walk `parent_session_id` chain: start at `id`, follow `parent_session_id` until NULL.
3. Collect `{session_id, title, topic, depth_level, session_type, news_article_id, is_current}` for each node.
4. Return array ordered root → current.

#### 6.6 `backend/api/quiz/generator.py` + `service.py` — `generate_hierarchical()`
1. Verify session ownership.
2. Call `GET /sessions/{id}/tree` internally.
3. For each node in the tree, load LangGraph state and extract conversation text.
4. Build MCQ prompt: include all topics and conversation excerpts, oldest to newest.
5. Instruct LLM to generate 8 questions spanning all topics; each question must include `topic` and `source_depth` fields.
6. Validate response (same rules as regular MCQ + `topic` ≥ 5 chars + `source_depth` 0–N).
7. Store in `mcq_attempts` with `scope_sessions=[session_id for each node]`.
8. Return questions without `correct` field.

#### 6.7 `backend/api/quiz/generator.py` + `service.py` — `get_relearn_explanation()`
1. Verify attempt ownership.
2. Check `attempt.relearn_cache[question_id]` — return cached explanation if present.
3. Build relearn prompt: "In 3–4 sentences, explain why the correct answer is correct and why the distractors are wrong. Question: {text}. Correct: {options[correct]}. Topic: {topic}."
4. Call LLM (lightweight call — no conversation history needed).
5. Store result in `relearn_cache[question_id]` via UPDATE.
6. Return `{explanation: str}`.

#### 6.8 Updated `backend/api/sessions/service.py` — `list_sessions()`
Add to returned fields: `session_type`, `parent_session_id`, `root_session_id`, `depth_level`, `topic`, `news_article_id`.

### Frontend Tasks

#### 6.9 `NewsTabs.tsx`
- Three tab buttons: AI / Programming / Political. Active tab stored in local state.
- On tab switch: React Query key changes to `['news', category]`.
- Each tab renders a list of `NewsArticleCard` components.

#### 6.10 `NewsArticleCard.tsx`
Props: `article: NewsArticle`, `onDiscuss: (article) => void`
- Title (link to source), 2-line summary, relative timestamp.
- `[↗ Source]` → `window.open(article.link, '_blank', 'noopener,noreferrer')`.
- `[Discuss]` → calls `onDiscuss(article)`.
  - Button state: idle → loading (spinner) → done (disabled, "Opened").
  - On success: navigate main pane to the new `news_discussion` session.

#### 6.11 `useDiscuss.ts`
- `discuss(article)` → `POST /news/discuss`, sets active session in `useSessions`, renders `first_response` immediately in chat.
- Returns `{isLoading, error, discuss}`.

#### 6.12 `SectionedMessage.tsx`
Props: `content: MessageContent`, `currentSessionId: string`
- If `content.type === 'plain'`: render markdown (existing `Message` component).
- If `content.type === 'sectioned'`:
  - Render `intro` as plain paragraph.
  - For each section: card with title, content, `[Learn More →]` button.
  - Render `outro` as plain paragraph.
- Learn More button state per section: `idle | loading | opened`.
- On click: `useLearnMore(currentSessionId, section.learn_more_topic)` → disable button → show checkmark.

#### 6.13 `useLearnMore.ts`
- `learnMore(parentSessionId, topic)` → `POST /sessions/{parentSessionId}/learn-more` → `window.open('/learn/{session_id}', '_blank', 'noopener,noreferrer')`.
- Returns `{isLoading, error, learnMore}`.

#### 6.14 `LearnPage.tsx` (`/learn/:sessionId`)
- Same three-pane layout as `/app`.
- Left pane: `ChatSidebar` (same component, shows full hierarchy).
- Centre pane: `ChatInterface` for the learn_more session. Shows `[Check Knowledge]` button at bottom; clicking calls `POST /quiz/generate-hierarchical`.
- Right pane: `KnowledgeTree` (instead of `NewsPanel`).
- On mount: fetch session, verify it's a `learn_more` session, load tree.

#### 6.15 `KnowledgeTree.tsx`
Props: `sessionId: string`
- Fetches `GET /sessions/{sessionId}/tree` via `useSessionTree`.
- Renders nodes top-to-bottom with connecting vertical lines.
- Root node: `📰` icon + article title + source.
- Sub-nodes: `⚡` icon + topic + indented.
- Current node: highlighted with left border.
- Navigation: `[↩ Back to root]` → `window.open('/learn/{root_session_id}', '_blank')`.

#### 6.16 `ChatSidebar.tsx` (updated — nested tree)
- `GET /sessions` now returns full hierarchy data.
- Build tree client-side: group all `learn_more` sessions under their `parent_session_id`.
- Render `news_discussion` sessions with a collapse toggle; `learn_more` children indented below.
- Icons: `📰` for `news_discussion`, `⚡` for `learn_more`, no icon for `regular`.

#### 6.17 Hierarchical Quiz Page (updated `Quiz.tsx`)
After submit, for each **wrong** answer:
- Lazy-load `GET /quiz/attempt/{id}/relearn/{q_id}` when wrong-answer panel first opens.
- Render `RelearPanel` with explanation text.
- `[Explore deeper: {topic} →]` button → `useLearnMore(attempt.session_id, question.topic)`.

After submit, for each **correct** answer:
- Render green `✅ Correct!` badge.
- `[Explore deeper: {topic} →]` button → same `useLearnMore` call.

The `[Check Knowledge]` button in `ChatInterface` now detects session type:
- `regular` → `POST /quiz/generate` (existing flat MCQ)
- `news_discussion` or `learn_more` → `POST /quiz/generate-hierarchical`

### Unit Tests

#### Backend — `tests/unit/test_discuss.py`
```python
def test_discuss_creates_news_discussion_session(auth_client, article_payload): ...
def test_discuss_returns_sectioned_first_response(auth_client, article_payload): ...
def test_discuss_retries_on_invalid_llm_format(auth_client, mock_bad_then_good_llm): ...
def test_discuss_returns_503_after_two_llm_failures(auth_client, mock_always_bad_llm): ...
def test_learn_more_creates_child_session(auth_client, discuss_session_id): ...
def test_learn_more_increments_depth_level(auth_client, learn_more_session_id): ...
def test_learn_more_sets_correct_root_session_id(auth_client, nested_sessions): ...
def test_learn_more_on_other_users_session_returns_403(auth_client, other_session_id): ...
def test_get_tree_returns_full_ancestry(auth_client, three_level_session_id): ...
def test_get_tree_ordered_root_to_current(auth_client, three_level_session_id): ...
def test_get_tree_marks_current_node(auth_client, session_id): ...
def test_get_tree_for_other_users_session_returns_403(auth_client): ...
```

#### Backend — `tests/unit/test_news_categories.py`
```python
def test_get_news_ai_category_returns_ai_feeds(mock_redis, mock_rss): ...
def test_get_news_programming_category_returns_programming_feeds(mock_redis, mock_rss): ...
def test_get_news_political_category_returns_political_feeds(mock_redis, mock_rss): ...
def test_category_cache_keys_are_isolated(mock_redis): ...
def test_promote_hour_to_day_runs_for_all_categories(mock_redis): ...
def test_invalid_category_returns_400(): ...
def test_default_category_is_ai(app_client): ...
```

#### Backend — `tests/unit/test_hierarchical_quiz.py`
```python
def test_generate_hierarchical_spans_full_tree(auth_client, three_level_session): ...
def test_generate_hierarchical_questions_have_source_depth(auth_client, session): ...
def test_generate_hierarchical_questions_have_topic_field(auth_client, session): ...
def test_relearn_returns_explanation_for_wrong_answer(auth_client, submitted_attempt): ...
def test_relearn_is_cached_on_second_call(auth_client, submitted_attempt): ...
def test_relearn_on_correct_answer_returns_400(auth_client, submitted_attempt): ...
def test_scope_sessions_stored_in_attempt(auth_client, three_level_session): ...
```

#### Frontend — Unit Tests
```ts
// NewsTabs.test.tsx
test('renders three tabs: AI, Programming, Political')
test('clicking a tab changes active category')
test('active tab fetches news with correct category')

// NewsArticleCard.test.tsx
test('renders title, summary, and relative timestamp')
test('source link opens in new tab')
test('discuss button shows loading state while creating session')
test('discuss button becomes disabled after session created')
test('discuss button calls onDiscuss with article data')

// SectionedMessage.test.tsx
test('renders intro, sections, and outro for sectioned type')
test('renders plain markdown for plain type')
test('each section has Learn More button')
test('Learn More button shows loading spinner during API call')
test('Learn More button shows checkmark after opening new tab')
test('Learn More button does not call API again after it was clicked')

// KnowledgeTree.test.tsx
test('renders all nodes from root to current')
test('current node is visually highlighted')
test('root node shows news source label')
test('back to root button is present')
test('depth counter shows correct level number')
test('clicking a non-current node opens that session')

// RelearPanel.test.tsx
test('shows loading skeleton while fetching explanation')
test('renders explanation text after fetch')
test('explore deeper button calls useLearnMore with question topic')
test('explore deeper button disabled after click')

// useDiscuss.test.ts
test('discuss calls POST /news/discuss with article data')
test('discuss returns session data on success')
test('discuss exposes loading state during request')
test('discuss exposes error on failure')

// useLearnMore.test.ts
test('learnMore calls POST /sessions/{id}/learn-more with topic')
test('learnMore opens new tab on success')
test('learnMore returns loading and error state')

// useSessionTree.test.ts
test('fetches tree on mount')
test('tree is ordered root to current')
test('current node has is_current: true')

// useHierarchicalQuiz.test.ts
test('generate calls POST /quiz/generate-hierarchical for learn_more sessions')
test('generate calls POST /quiz/generate for regular sessions')
test('relearn fetches explanation for wrong answer')
test('relearn is not re-fetched when already cached in local state')
```

### E2E Tests

#### `e2e/discuss.spec.ts`
```ts
test('news panel shows three tabs: AI, Programming, Political')
test('switching tabs loads different news sources')
test('each article card has a Discuss button')
test('clicking Discuss creates a new session in the sidebar')
test('first response is sectioned with Learn More buttons')
test('user can type follow-up questions in the discuss thread')
test('discuss session appears as 📰 in left sidebar')
```

#### `e2e/learn-more.spec.ts`
```ts
test('clicking Learn More on a section opens a new tab')
test('new tab URL is /learn/:sessionId')
test('right pane in /learn tab shows knowledge tree, not news')
test('knowledge tree shows root article and current topic')
test('current node is highlighted in the tree')
test('learn_more session appears indented under parent in sidebar')
test('clicking Learn More again goes one level deeper with extended tree')
test('back to root button navigates to root session')
test('user can ask questions in learn_more chat thread')
```

#### `e2e/hierarchical-quiz.spec.ts`
```ts
test('Check Knowledge in /learn tab generates hierarchical MCQs')
test('MCQs span multiple depth levels (source_depth present)')
test('wrong answer shows relearn explanation panel')
test('relearn panel has Explore deeper button')
test('correct answer shows green success badge')
test('correct answer has Explore deeper button')
test('Explore deeper on correct answer opens new /learn tab')
test('Explore deeper on wrong answer opens new /learn tab for that topic')
test('retry quiz resets all answers and relearn panels')
```

---

## Phase 14 — Social Wall (`feature/auth`)

### Goal

Users can share knowledge roots publicly or with followers, vote on shared content, preview full session trees (with ephemeral quiz answering), import trees to their own Root section, and view a profile with star-rating score. The session tree auto-expands to the active path after content generation. MCQ options are post-shuffled to remove LLM position bias.

### New Files

```
backend/api/wall/__init__.py
backend/api/wall/routes.py               ← Blueprint('/wall'): all wall/profile/social endpoints
backend/api/wall/service.py              ← share, vote, comment, follow, profile, preview, import service logic
backend/migrations/009_social.sql        ← shares, share_votes, share_comments, user_follows
backend/migrations/010_import.sql        ← chat_sessions.imported_from_share_id + shares.source_share_id
backend/migrations/011_follow_requests.sql ← adds status + requested_at to user_follows; partial index
backend/migrations/012_cascade_reshare.sql ← changes source_share_id FK to ON DELETE CASCADE
backend/migrations/013_wall_saves.sql      ← wall_saves: bookmark a public share to private wall
backend/templates/partials/wall_public.html
backend/templates/partials/wall_private.html
backend/templates/partials/share_card.html
backend/templates/partials/profile_main.html
backend/templates/partials/profile_score.html
backend/templates/partials/share_preview_modal.html
backend/templates/partials/share_session_preview.html
```

### Modified Files

```
backend/app.py                           ← register wall_bp
backend/api/sessions/routes.py          ← open_ids ancestor-chain expand; htmx:configRequest hook
backend/api/sessions/service.py         ← list_sessions SELECT includes imported_from_share_id
backend/api/quiz/generator.py           ← add _shuffle_options(); wire into generate_mcq() + generate_mcq_followup()
backend/templates/app/index.html        ← bottom nav (Root/Wall/Profile); activeTab x-show guards; share modal; preview portal
backend/templates/partials/session_list.html ← starts_open via open_ids set; share button; ↗ badge
backend/templates/partials/quiz_inline.html  ← fix Explore button :disabled ternary
backend/static/app.js                   ← activeTab, switchTab(), shareModal, shareSession(), wallVote(), wallOpenPreview(), wallImport(), previewQuizState(), htmx:configRequest expand hook
```

### Backend Tasks

#### 7.1 DB Migrations

**`009_social.sql`**
```sql
CREATE TABLE shares (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    visibility      VARCHAR(10) NOT NULL DEFAULT 'public',
    description     TEXT,
    source_share_id UUID REFERENCES shares(id) ON DELETE SET NULL,
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
    follower_id UUID REFERENCES users(id) ON DELETE CASCADE,
    followed_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (follower_id, followed_id)
);
```

**`010_import.sql`**
```sql
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS imported_from_share_id UUID REFERENCES shares(id) ON DELETE SET NULL;
ALTER TABLE shares
    ADD COLUMN IF NOT EXISTS source_share_id UUID REFERENCES shares(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_imported ON chat_sessions(imported_from_share_id)
    WHERE imported_from_share_id IS NOT NULL;
```

**`011_follow_requests.sql`**
```sql
ALTER TABLE user_follows
    ADD COLUMN IF NOT EXISTS status       VARCHAR(10)  NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ           DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_follows_pending
    ON user_follows(followed_id, status)
    WHERE status = 'pending';
```

**`012_cascade_reshare.sql`**
```sql
ALTER TABLE shares DROP CONSTRAINT IF EXISTS shares_source_share_id_fkey;
ALTER TABLE shares ADD CONSTRAINT shares_source_share_id_fkey
    FOREIGN KEY (source_share_id) REFERENCES shares(id) ON DELETE CASCADE;
```

**`013_wall_saves.sql`**
```sql
CREATE TABLE IF NOT EXISTS wall_saves (
    user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    share_id UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, share_id)
);
CREATE INDEX IF NOT EXISTS idx_wall_saves_user ON wall_saves(user_id, saved_at DESC);
```

#### 7.2 `backend/api/wall/service.py`

Key functions:

| Function | Responsibility |
|----------|---------------|
| `score_to_stars(score)` | Threshold lookup: 50/150/350/600/900 → 0–5 stars |
| `get_user_score(user_id)` | Batched SUM of weighted votes across all user's shares |
| `create_share(user_id, session_id, visibility, description)` | Validates ownership; checks `imported_from_share_id` for attribution; inserts with `source_share_id` if applicable |
| `delete_share(user_id, share_id)` | Ownership check then DELETE |
| `_hydrate_share_rows(rows, viewer_user_id)` | Batch fetch: tallies, my_vote, comment counts, author scores, source attribution, follow status, saved_to_wall — no per-card queries |
| `list_public_shares(viewer_user_id, limit, offset)` | SELECTs all public shares; LEFT JOIN accepted follows to sort followed-authors' posts first, then newest-first |
| `list_private_shares(viewer_user_id, limit, offset)` | Viewer's own shares + wall_saves entries; LEFT JOIN wall_saves; returns is_own + is_saved flags |
| `save_to_wall(user_id, share_id)` | INSERT INTO wall_saves ON CONFLICT DO NOTHING; rejects own shares |
| `unsave_from_wall(user_id, share_id)` | DELETE FROM wall_saves; idempotent |
| `cast_vote(voter_user_id, share_id, vote)` | UPSERT ON CONFLICT; returns new tallies + updated author score |
| `add_comment` / `list_comments` / `delete_comment` | Standard CRUD with ownership check on delete |
| `follow_user(follower_id, followed_id)` | INSERT with `status='pending'`; returns `{status: "pending"\|"accepted"\|"self"}` |
| `cancel_follow(follower_id, followed_id)` | DELETE record regardless of status (cancels pending or accepted) |
| `accept_follow_request(current_user_id, requester_id)` | UPDATE status='accepted' on the matching pending row |
| `reject_follow_request(current_user_id, requester_id)` | DELETE the pending row (requester can re-request later) |
| `get_pending_requests(user_id)` | Returns list of requesters with pending `status` rows for `followed_id = user_id` |
| `get_profile(user_id, viewer_id)` | is_following (status='accepted' only), is_self, follow_request_sent flags; pending_requests list (own profile only); recent_shares; score + stars |
| `get_share_preview(share_id)` | Session tree + initial content for first session |
| `get_session_preview_content(share_session_id, session_id)` | Messages (with roles) or quiz questions without `correct` field |
| `import_share(user_id, share_id)` | Deep copy within `conn.transaction()`: id_map old→new UUID, depth-ordered INSERT, message copy for non-quiz sessions, `imported_from_share_id` set on all new sessions |

#### 7.3 Session Tree Auto-Expand

**`backend/api/sessions/routes.py` — `session_list_partial()`:**
```python
expand_id = request.args.get('expand') or request.args.get('expand_id')
open_ids: set[str] = set()
if expand_id:
    parent_map = {s['id']: s.get('parent_session_id') for s in sessions}
    cur: str | None = expand_id
    while cur:
        open_ids.add(cur)
        cur = parent_map.get(cur)
return render_template("partials/session_list.html", sessions=sessions, expand_id=expand_id, open_ids=open_ids)
```

**`backend/static/app.js` — `htmx:configRequest` hook:**
```js
document.body.addEventListener('htmx:configRequest', e => {
    const path = e.detail.path || '';
    if (path.includes('/sessions/partial') && !e.detail.parameters.expand && _activeSessionId) {
        e.detail.parameters.expand = _activeSessionId;
    }
});
```

This ensures the active session's full ancestor path stays open after any sidebar refresh (chat reply, delete, session switch).

#### 7.4 MCQ Option Shuffle

**`backend/api/quiz/generator.py`:**
```python
def _shuffle_options(question: dict) -> dict:
    correct_text = question['options'][question['correct']]
    random.shuffle(question['options'])
    question['correct'] = question['options'].index(correct_text)
    return question

# Applied in both generation functions:
return [_shuffle_options(q) for q in questions[:n_questions]]
```

This eliminates LLM position bias (model tends to place correct answer in option B).

#### 7.5 Wall Routes (`backend/api/wall/routes.py`)

**HTMX partials:**
- `GET /wall/public/partial` → `wall_public.html`
- `GET /wall/private/partial` → `wall_private.html`
- `GET /wall/profile/partial` → `profile_main.html`
- `GET /wall/score/partial` → `profile_score.html`
- `GET /wall/shares/<id>/preview/partial` → `share_preview_modal.html`
- `GET /wall/shares/<id>/sessions/<sid>/preview/partial` → `share_session_preview.html`

**JSON APIs:**
- `POST /wall/shares` — create; body: `{session_id, visibility, description}`
- `DELETE /wall/shares/<id>` — delete own share
- `POST /wall/shares/<id>/vote` — body: `{vote: 1|-1}`
- `POST /wall/shares/<id>/import` — deep copy
- `GET /wall/shares/<id>/comments` — list
- `POST /wall/shares/<id>/comments` — add; body: `{body}`
- `DELETE /wall/shares/<id>/comments/<cid>` — delete own comment
- `POST /wall/shares/<id>/save` — save to My Wall (204); idempotent
- `DELETE /wall/shares/<id>/save` — unsave from My Wall (204)
- `POST /wall/follow/<uid>` — send follow request; returns `{status: "pending"|"accepted"|"self"}`
- `DELETE /wall/follow/<uid>` — cancel pending request or unfollow accepted follower
- `POST /wall/follow-requests/<uid>/accept` — accept incoming follow request (204)
- `POST /wall/follow-requests/<uid>/reject` — decline incoming follow request (204)
- `GET /wall/follow-requests/count` — number of pending incoming requests (JSON)

### Frontend Tasks

#### 7.6 Bottom Nav + `activeTab` (`app/index.html` + `app.js`)

Three buttons at the bottom of the left sidebar:
- `[Root]` → `switchTab('root')` — shows session list, chat, news pane
- `[Wall]` → `switchTab('wall')` — loads public + private wall partials
- `[Profile]` → `switchTab('profile')` — fetches `GET /wall/follow-requests/count` to update `pendingFollowCount`, then loads profile + score partials

`x-show="activeTab === 'root'"` gates the session list, `+` button, chat input, and Check Knowledge bar.

The Profile tab button shows a red notification badge when `pendingFollowCount > 0`:
```html
<span x-show="pendingFollowCount > 0" x-cloak
      class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
  <span x-text="pendingFollowCount > 9 ? '9+' : pendingFollowCount"></span>
</span>
```

#### 7.7 Share Modal (`app/index.html` + `app.js`)

Alpine `shareModal` object in `appState()`:
```js
shareModal: { open: false, sessionId: null, visibility: 'public', description: '' }
```
`shareSession(id)` sets `shareModal.open = true`, `shareModal.sessionId = id`.
`submitShare()` calls `POST /wall/shares`, closes modal, fires `htmx.trigger` on `#wall-public-pane`.

#### 7.8 Share Card (`partials/share_card.html`)

Alpine `x-data` per card: `{treeOpen, commentsOpen, comments, myVote, upvotes, downvotes, importDone, importLoading, followStatus, savedToWall}`.
- `savedToWall` is initialised from `{{ loop_share.saved_to_wall | tojson }}`
- `followStatus` is initialised from `{{ loop_share.follow_status | tojson }}` (can be `null`, `"pending"`, or `"accepted"`)
- Vote buttons call `wallVote(shareId, 1)` / `wallVote(shareId, -1)`; update counts + my_vote in-place
- Follow buttons call `window.wallFollowAction(userId, action, $data)` which updates `followStatus` in-place
- Preview calls `wallOpenPreview(shareId)` → GET partial → inject into `#share-preview-portal`

Template receives `wall_context` (`'public'` | `'private'` | `'profile'`) to determine which buttons render:

| Context | Own card top-right | Others' card top-right | Action row for others |
|---------|-------------------|----------------------|-----------------------|
| `public` | Delete | Follow/Requested/Following | **Save** button |
| `private` | Delete | Unsave (bookmark) | **Import to Root** button |
| `profile` | Delete | Follow/Requested/Following | *(none)* |

**`window.wallSaveToWall(shareId, component)` in `app.js`:**
- If not saved: `POST /wall/shares/<id>/save` → sets `component.savedToWall = true`, toast "Saved to your wall"; if `activeTab === 'wall'` also refreshes private wall partial via HTMX
- If already saved: `DELETE /wall/shares/<id>/save` → sets `component.savedToWall = false`, refreshes private wall partial via HTMX

**`window.wallImport(shareId, component)` in `app.js`:**
- `POST /wall/shares/<id>/import` → deep-copies session tree → sets `component.importDone = true`, refreshes session list
- On success: bookmark is kept — the saved post remains visible on My Wall even after import
- Import button visibility is controlled via Alpine `:class="importDone ? 'hidden' : ''"` (not `x-show`) so it renders immediately on page load and is only hidden after a successful import

**`window.wallFollowAction(userId, action, componentData)` in `app.js`:**
- `action = 'follow'` → `POST /wall/follow/<uid>` → sets `componentData.followStatus = response.status`
- `action = 'cancel'` or `'unfollow'` → `DELETE /wall/follow/<uid>` → sets `componentData.followStatus = null`

**`window.wallRespondToFollowRequest(requesterId, action, btn)` in `app.js`:**
- `action = 'accept'|'reject'` → `POST /wall/follow-requests/<uid>/<action>` (204)
- On success: removes the `#follow-req-<id>` row from DOM, decrements `pendingFollowCount`, reloads profile partial via `htmx.ajax`

#### 7.9 Ephemeral Quiz Preview (`partials/share_session_preview.html`)

```html
<script type="application/json" id="preview-qdata">{{ questions | tojson }}</script>
```

`previewQuizState()` in `app.js`:
```js
function previewQuizState() {
    return {
        questions: JSON.parse(document.getElementById('preview-qdata').textContent),
        selected: {},
        submitted: false,
        score: 0,
        submit() { /* compute score from q.correct, set submitted = true */ },
        reset() { this.selected = {}; this.submitted = false; this.score = 0; }
    }
}
```
No `fetch()` on submit — purely client-side. Not saved to DB.

### Unit Tests (Backend)

```python
# tests/unit/test_wall.py
def test_create_share_returns_201(authed_client, session_id): ...
def test_create_share_for_other_users_session_returns_403(authed_client): ...
def test_delete_own_share_returns_204(authed_client, share_id): ...
def test_delete_other_users_share_returns_403(authed_client): ...
def test_upvote_increments_score(authed_client, share_id): ...
def test_downvote_decrements_score(authed_client, share_id): ...
def test_changing_vote_updates_score(authed_client, share_id): ...
def test_own_shares_appear_in_private_feed(authed_client): ...
def test_followed_users_shares_appear_in_private_feed(authed_client): ...
def test_import_creates_deep_copy(authed_client, share_id): ...
def test_import_sets_imported_from_share_id(authed_client, share_id): ...
def test_resharing_import_sets_source_share_id(authed_client, imported_session_id): ...
def test_score_to_stars_thresholds(): ...  # 0,50,150,350,600,900
# Follow request tests
def test_follow_creates_pending_request(authed_client, other_user_id): ...
def test_follow_returns_pending_status(authed_client, other_user_id): ...
def test_follow_self_returns_self_status(authed_client): ...
def test_duplicate_follow_returns_existing_status(authed_client, other_user_id): ...
def test_cancel_pending_request_returns_204(authed_client, other_user_id): ...
def test_accept_follow_request_sets_accepted(authed_client, requester_id): ...
def test_accept_nonexistent_request_returns_404(authed_client): ...
def test_reject_follow_request_deletes_row(authed_client, requester_id): ...
def test_pending_user_not_in_private_feed(authed_client, other_user_id): ...
def test_accepted_user_appears_in_private_feed(authed_client, other_user_id): ...
def test_followed_posts_sort_first_in_public_wall(authed_client): ...
def test_follow_request_count_returns_count(authed_client, requester_id): ...
```

### E2E Tests

```ts
// e2e/wall.spec.ts
test('root tab shows session list and chat by default')
test('wall tab loads public wall and private feed')
test('profile tab loads profile card and score pane')
test('sharing a root session creates a card on public wall')
test('upvoting a card updates the vote count')
test('own share appears in private feed')
test('preview modal shows session tree and chat messages')
test('preview quiz can be answered without saving')
test('import copies session tree to Root section')
test('imported session shows ↗ badge in sidebar')
test('resharing an imported root tags original owner')
test('sidebar tree stays expanded after chat reply')
// Follow request E2E
test('clicking Follow on a card shows Requested state immediately')
test('pending-only user posts do not appear in private feed')
test('Profile tab shows notification badge when follow requests exist')
test('accepting follow request removes it from pending list')
test('declining follow request removes it from pending list')
test('accepting follow request causes accepted user posts to appear in private feed')
```

---

## Phase 15 — Real-time Events via SSE (`feature/auth`)

### Goal

Deliver live updates to the browser without polling or page refresh. Three event types: new comments, incoming follow requests, follow acceptances. Transport: Server-Sent Events over a per-user Redis pub/sub channel.

### New Files

| File | Purpose |
|------|---------|
| `backend/api/events/__init__.py` | Blueprint package |
| `backend/api/events/routes.py` | `GET /events/stream` SSE endpoint |
| `backend/core/sse.py` | `publish_event`, `broadcast_event`, TTL-based presence helpers (`register_user`, `renew_user_ttl`, `unregister_user`) |

### Modified Files

| File | Change |
|------|--------|
| `backend/api/wall/service.py` | Call `publish_event` in `add_comment`, `follow_user`, `accept_follow_request` |
| `backend/app.py` | Register `events` blueprint |
| `backend/static/app.js` | `wallInitSSE`, `wallDestroySSE`, `wallHandleNewComment`, `wallHandleFollowAccepted` |
| `backend/templates/app/index.html` | Call `wallInitSSE()` / `wallDestroySSE()` on tab switch |

### Backend Tasks

#### 15.1 `backend/core/sse.py`

Presence uses per-user TTL keys (`sse:online:<user_id>`) instead of a persistent Redis SET. A crashed process leaves a key that auto-expires within `PRESENCE_TTL` seconds — no stale entries accumulate.

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
    get_redis().publish(
        f"sse:user:{user_id}",
        json.dumps({"event": event, "payload": json.dumps(payload)}),
    )

def broadcast_event(event: str, payload: dict) -> None:
    """Publish to every user with an active presence key (scan_iter, not smembers)."""
    redis = get_redis()
    msg = json.dumps({"event": event, "payload": json.dumps(payload)})
    for key in redis.scan_iter("sse:online:*"):
        uid = (key.decode() if isinstance(key, bytes) else key).split(":", 2)[-1]
        redis.publish(f"sse:user:{uid}", msg)
```

All Redis calls are wrapped in `try/except` — failures are logged and never raised.

#### 15.2 `backend/api/events/routes.py`

Uses `get_message(timeout=KEEPALIVE_INTERVAL)` instead of the blocking `pubsub.listen()` iterator, so the loop wakes up every 20 s to send a keepalive comment and renew the presence TTL:

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
                    timeout=KEEPALIVE_INTERVAL,
                )
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    yield f"event: {data['event']}\ndata: {data['payload']}\n\n"
                else:
                    yield ": keepalive\n\n"   # SSE comment — invisible to EventSource
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

#### 15.3 Wall service publishers

Three hooks in `backend/api/wall/service.py`:

| Function | Event | Target |
|----------|-------|--------|
| `add_comment()` | `comment_added` + full comment object | `broadcast_event` (all active users) |
| `follow_user()` | `follow_request_received` + requester profile | `publish_event` to followed user |
| `accept_follow_request()` | `follow_accepted` + accepter profile | `publish_event` to requester |

#### 15.4 Blueprint registration (`app.py`)

```python
from backend.api.events.routes import bp as events_bp
app.register_blueprint(events_bp)
```

### Frontend Tasks

#### 15.5 `wallInitSSE` / `wallDestroySSE` (app.js)

- Create `EventSource('/events/stream')` on wall tab open; store as `window._wallSSE`
- `onerror`: close and null the reference (browser will not auto-retry after explicit close)
- `wallDestroySSE`: called when leaving wall tab — closes the connection cleanly

#### 15.6 Event handlers (app.js)

| Event | Handler | Effect |
|-------|---------|--------|
| `comment_added` | `wallHandleNewComment(data)` | Find all cards for `data.share_id`; use `Alpine.$data(card)` to reach Alpine state; deduplicate by `comment.id` before incrementing `commentCount` (prevents double-count for the poster who already incremented optimistically); push to `comments` only if panel is open |
| `vote_updated` | `wallHandleVoteUpdated(data)` | Find all cards for `data.share_id`; overwrite `component.upvotes` and `component.downvotes` with server-authoritative values; no dedup needed — overwriting is idempotent |
| `follow_request_received` | inline | `appData.pendingFollowCount += 1` |
| `follow_accepted` | `wallHandleFollowAccepted(userId)` | Find all share cards for that `userId` (via `data-author-id` attr); set `Alpine.$data(card).followStatus = 'accepted'` |

Alpine component state is accessed via the public v3 API `Alpine.$data(element)`, not the internal `_x_dataStack[0]`.

#### 15.7 `data-` attributes on share card

Add two `data-*` attributes to the share card `<div>` to enable DOM lookup:
- `data-share-id="{{ loop_share.id }}"`
- `data-author-id="{{ loop_share.user_id }}"`

#### 15.8 Tab switch wiring (`index.html` / `app.js`)

In `switchTab()`:
```js
if (tab === 'wall') {
    window.wallInitSSE && window.wallInitSSE();
} else {
    window.wallDestroySSE && window.wallDestroySSE();
}
```

### Unit Tests (Backend)

```python
# tests/unit/test_sse.py
def test_publish_event_sends_to_redis_channel(): ...
def test_broadcast_event_sends_to_all_active_users(): ...
def test_register_unregister_user(): ...
def test_add_comment_triggers_broadcast(): ...
def test_follow_user_publishes_to_followed_user(): ...
def test_accept_follow_request_publishes_to_requester(): ...
```

### E2E Tests

```js
// e2e/sse.spec.ts
test('comment posted by user A appears live on user B wall without refresh')
test('follow request badge increments live when user A follows user B')
test('follow accepted updates button state live for the requester')
```

---

## CI Workflow Summary

Every PR triggers `.github/workflows/ci.yml`:

```
┌─────────────────────────────────────────────────────────┐
│  CI Pipeline                                            │
│                                                         │
│  lint-backend  ──────────────────────────────┐         │
│  (flake8, mypy)                               │         │
│                                               ▼         │
│  test-backend  ──────────────────────────► all-pass?   │
│  (pytest --cov=backend --cov-fail-under=80)   │         │
│                                               │         │
│  e2e           ──────────────────────────────┘         │
│  (playwright, docker-compose up, run specs)             │
└─────────────────────────────────────────────────────────┘
```

No separate frontend lint or test jobs — Flask/Python linting covers all application code. Tailwind, HTMX, and Alpine.js are CDN-loaded and have no local build artefacts to lint.

Coverage threshold: **80% line coverage** for backend (agent, LLM, and unimplemented blueprint code is excluded via `.coveragerc`).

---

## Phase 7 — 3-Pane UI + Sessions + Chat + News + Discuss / Learn More (`feature/three-pane-ui`)

> **Status:** ✅ shipped — but with a different architecture than originally planned.
>
> **Original plan:** Every AI response would pass through a Google ADK `SequentialAgent` with three sub-agents (Research → Fact Check → Editor) before reaching the user.
>
> **What actually shipped:** the unified ADK pipeline was abandoned in favour of a simpler, more direct architecture (see `ARCHITECTURE.md §25`). Each surface now has its own purpose-built layer:
>
> | Surface | Implementation |
> |---------|---------------|
> | Chat (`POST /chat`) | LangGraph ReAct agent — single `StateGraph` with `agent` + `tools` nodes (DeepSeek via OpenRouter) |
> | Explore / Learn More (`POST /news/discuss`, `POST /sessions/<id>/learn-more`) | Direct DeepSeek call in `_run_discussion_pipeline()` — no LangGraph traversal; first exchange written into checkpoint via `update_state` |
> | Hourly news curation | DeepSeek call in `curate_with_ai()` — re-orders RSS articles by importance |
> | Fact-Check button | Single `google-genai` call with native `GoogleSearch` grounding — Gemini searches Google and produces the verdict JSON in one call; completely separate from chat/discuss |
>
> **Why the change:**
> - LangGraph reverted to a single ReAct agent for chat — the multi-agent pipeline was overkill for conversational replies and added latency without quality wins.
> - The "fact-check" idea moved out of the chat hot-path and into a user-initiated `[Fact Check]` button on news cards, where Google's native `google_search` tool + Gemini gives genuinely verifiable claims with sources.
> - Sectioned responses for Explore / Learn More are produced by a single direct LLM call — the structured-JSON validation already prevents malformed output, and a multi-stage editor pass was not necessary in practice.

### Goal
Deliver the full working application: collapsible sidebar with hierarchical session tree, AI chat in the centre pane (always-visible input — auto-creates session on first message), and a news panel on the right with three-tab categories and per-card `[Read article]`, `[Explore]`, `[Fact Check]` buttons.

### Current State (start of Phase 7)
- ✅ Phase 1 (auth) complete — register, login, logout, E2E green
- ✅ `backend/api/chat/service.py` — `send_message()`, `get_or_create_session()`, `auto_title_session()` implemented
- ✅ `backend/api/news/` — service, cache, feeds all implemented
- ✅ `backend/agent/prompts.py` — DISCUSSION_PROMPT, LEARN_MORE_PROMPT, MCQ_GENERATION_PROMPT all defined
- ❌ DB migrations 002–005 missing
- ❌ `backend/api/sessions/routes.py` + `service.py` — stubs only
- ❌ `backend/api/discuss/routes.py` + `service.py` — stubs only
- ❌ `backend/api/quiz/routes.py` + `service.py` + `generator.py` — stubs only
- ❌ `backend/agent/pipeline.py` (Google ADK fact-check) — does not exist
- ❌ All templates — placeholder dashboard only, no 3-pane layout

### New Files

#### Backend
```
backend/migrations/002_chat_sessions.sql
backend/migrations/003_news_cache.sql
backend/migrations/004_mcq_attempts.sql
backend/migrations/005_session_hierarchy.sql
backend/api/sessions/routes.py
backend/api/sessions/service.py
backend/api/discuss/routes.py
backend/api/discuss/service.py
backend/api/quiz/routes.py
backend/api/quiz/service.py
backend/api/quiz/generator.py
backend/agent/pipeline.py
backend/agent/quiz_agent.py
```

#### Templates & Static
```
backend/templates/app/index.html          ← full 3-pane layout (replaces placeholder)
backend/templates/learn/session.html      ← /learn/<id> with knowledge tree right pane
backend/templates/partials/session_list.html
backend/templates/partials/message.html
backend/templates/partials/sectioned_message.html
backend/templates/partials/news_panel.html
backend/templates/partials/knowledge_tree.html
backend/templates/partials/quiz_section.html
backend/static/app.js                     ← extended with sidebar toggle, chat, quiz logic
```

### Backend Implementation Tasks

#### 7.1 DB Migrations

**002_chat_sessions.sql**
```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id       VARCHAR(255) UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    title           VARCHAR(255),
    session_type    VARCHAR(20) NOT NULL DEFAULT 'regular',
    parent_session_id UUID REFERENCES chat_sessions(id),
    root_session_id   UUID REFERENCES chat_sessions(id),
    depth_level       INTEGER NOT NULL DEFAULT 0,
    topic             VARCHAR(500),
    news_article_id   VARCHAR(20),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_last ON chat_sessions(user_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_parent    ON chat_sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_root      ON chat_sessions(root_session_id);
```

**003_news_cache.sql** — news_cache table (existing design from §4.4)

**004_mcq_attempts.sql** — mcq_attempts with scope_sessions + relearn_cache (§21)

**005_session_hierarchy.sql** — no-op (already merged into 002 above)

#### 7.2 Sessions API (`backend/api/sessions/`)

**service.py**
- `create_session(user_id, session_type, parent_id, topic, news_article_id) → dict`
- `list_sessions(user_id) → list[dict]` — includes hierarchy columns
- `get_session(user_id, session_id) → dict | None`
- `rename_session(user_id, session_id, title) → None` — 403 on not-owned
- `delete_session(user_id, session_id) → None` — 403 on not-owned
- `get_messages(user_id, session_id) → list[dict]` — replays LangGraph state

**routes.py** — Blueprint('/sessions')
```
POST   /sessions                    → create_session()
GET    /sessions                    → list_sessions()
PATCH  /sessions/<id>               → rename_session()
DELETE /sessions/<id>               → delete_session()
GET    /sessions/<id>/messages      → get_messages()
GET    /sessions/partial            → render partials/session_list.html (HTMX)
GET    /sessions/<id>/messages/partial → render partials/message.html list (HTMX)
GET    /sessions/<id>/tree          → get_tree() JSON
```

#### 7.3 Discuss API (`backend/api/discuss/`)

**service.py**
- `news_discuss(user_id, article_id, title, summary, link) → dict`
  1. Create `news_discussion` session row (set root_session_id = self.id)
  2. Run pipeline with article context → parse sectioned JSON
  3. Store first message in LangGraph checkpoint
  4. Return `{session_id, title, first_response}`
- `create_learn_more(user_id, parent_session_id, topic) → dict`
  1. Verify ownership + load parent row
  2. Create `learn_more` session (depth + 1)
  3. Run pipeline with topic → sectioned JSON first response
  4. Return `{session_id, title}`
- `get_tree(user_id, session_id) → list[dict]`

**routes.py** — register on main Blueprint
```
POST  /news/discuss                       → news_discuss()
POST  /sessions/<id>/learn-more           → create_learn_more()
GET   /sessions/<id>/tree                 → get_tree()
GET   /sessions/<id>/tree/partial         → render partials/knowledge_tree.html (HTMX)
```

#### 7.4 Chat Service (`backend/api/chat/`)  ✅ shipped

`send_message()` flow (no ADK pipeline — direct LangGraph call):
- Always invokes the LangGraph ReAct agent (`backend/agent/graph.py`)
- For a brand-new session, the system prompt includes the top 5 cached AI headlines so the agent has fresh context
- The agent may call `get_latest_ai_news` mid-conversation via the `tools` node
- Plain markdown response is returned and appended via HTMX `beforeend` swap on `#messages`
- Always-visible chat input bar — sending a message with no `session_id` auto-creates a `regular` session before delivering the first turn

Routes:
```
POST /chat                              → send_message() — returns rendered message partial
GET  /sessions/<id>/messages/partial    → renders partial HTML message list
```

#### 7.5 Discuss Service (`backend/api/discuss/`)  ✅ shipped — direct LLM, not ADK

`_run_discussion_pipeline()` in `backend/api/discuss/service.py` makes a **direct DeepSeek call** (no LangGraph graph traversal). The flow:
1. Build the prompt — `DISCUSSION_PROMPT` (Explore from a news article) or `LEARN_MORE_PROMPT` (Learn More from a section topic)
2. Single DeepSeek call via `build_llm_client()`
3. Validate the returned sectioned JSON (`type=sectioned`, `intro`, `sections[]`, `outro`)
4. Write the first user message + AI response into the LangGraph checkpoint via `update_state` so subsequent turns can use Layer 3 (the chat ReAct agent) with full history
5. Return `{session_id, title, first_response}`

Routes:
```
POST /news/discuss                       → news_discuss() — sectioned first response from article
POST /sessions/<id>/learn-more           → create_learn_more() — sectioned first response from topic
GET  /sessions/<id>/tree                 → get_tree()
```

#### 7.6 Gemini Fact-Check Pipeline (`backend/agent/pipeline.py`)  ✅ shipped (rewritten in Phase 9)

A single `google-genai` API call with native `GoogleSearch` grounding — completely separate from chat/discuss. Gemini searches Google automatically during generation and returns structured verdict JSON in one call. Source URLs are extracted from `grounding_metadata.grounding_chunks` and merged into the claim objects.

Triggered only by `POST /news/fact-check`. Requires `GOOGLE_API_KEY` — without it returns a graceful error card. `[Fact Check]` button is hidden server-side for research/preprint sources (ArXiv, bioRxiv, HuggingFace Blog, etc.) where web-verifiable claims don't exist.

`FACT_CHECK_PROMPT` lives as a module-level constant in `pipeline.py`. `NEWS_CURATION_PROMPT` lives in `backend/agent/prompts.py`.

#### 7.7 Hourly News Curation (`backend/api/news/cache.py`)  ✅ shipped

After each RSS fetch in the `fetch_and_cache` APScheduler job, `curate_with_ai()` calls DeepSeek with `NEWS_CURATION_PROMPT` to select up to 10 important articles for a general educated audience. Selected articles are tagged `_curated: True` and shown first (starred in the UI); the remainder are sorted newest-first and appended. The `_curated` badge is only applied when at least one article was not selected — if all articles are selected (small feed), no badge is shown. The `/news/partial` route caps the list at **15 articles** before rendering. On any LLM failure the original RSS order is preserved — no service interruption.

### Frontend Implementation Tasks

#### 7.7 Three-Pane Layout — `backend/templates/app/index.html`

Full-height layout using Tailwind flex:
```html
<div class="flex h-screen overflow-hidden" x-data="appState()">
  <!-- LEFT SIDEBAR -->
  <aside class="..." :class="sidebarOpen ? 'w-64' : 'w-0'" ...>
    ...sidebar contents (HTMX-loaded session list)...
  </aside>
  
  <!-- CENTRE PANE -->
  <main class="flex flex-col flex-1 min-w-0 overflow-hidden">
    ...chat messages + input bar...
  </main>

  <!-- RIGHT PANE -->
  <aside class="w-80 flex-shrink-0 border-l ...">
    ...news panel (HTMX-loaded)...
  </aside>
</div>
```

Alpine.js `appState()` in `app.js`:
- `sidebarOpen` — persisted in `localStorage`
- `activeSessionId` — currently active chat
- `loadSession(id)` — HTMX-triggered session switch

#### 7.8 Session List Partial — `partials/session_list.html`

Groups by Today / Yesterday / This Week / Older. Renders hierarchy:
- `regular` sessions: plain title
- `news_discussion` sessions: `📰` prefix, collapsible children
- `learn_more` sessions: `⚡` prefix, indented `depth * 16px`

Loaded via `hx-get="/sessions/partial" hx-trigger="load"` from the left sidebar.

#### 7.9 Chat Interface — messages + input bar

Messages loaded: `hx-get="/sessions/{id}/messages/partial" hx-trigger="load"` on session select.

Submit: `hx-post="/chat" hx-target="#messages" hx-swap="beforeend"`

After submit: server returns either:
- `partials/message.html` (plain response)
- `partials/sectioned_message.html` (pipeline response)

#### 7.10 Sectioned Message Partial — `partials/sectioned_message.html`

Each section card rendered with Alpine.js state `{loading: false, opened: false}`:
- **[Explore →]**: `hx-post="/sessions/{id}/learn-more"`, on success `window.open('/learn/{new_id}', '_blank')`, button becomes disabled with ✓
- **[Quiz]**: `hx-post="/chat/quiz-section" hx-target="#quiz-{section_id}" hx-swap="innerHTML"`, inline MCQ cards appear below section

#### 7.11 News Panel Partial — `partials/news_panel.html`

3-tab group (Alpine.js local state `{tab: 'ai'}`). Internal cache keys remain `ai`/`programming`/`political`; UI labels are **AI / Dev / World**:
```html
<div x-data="{tab: 'ai'}">
  <button @click="tab='ai'"          :class="...">AI</button>
  <button @click="tab='programming'" :class="...">Dev</button>
  <button @click="tab='political'"   :class="...">World</button>

  <div x-show="tab==='ai'" hx-get="/news/partial?category=ai" hx-trigger="intersect once"></div>
  ...
</div>
```

Each article card (redesigned layout):
- Header row: source · relative date
- Title (plain text)
- Description (2–3 line summary)
- Action row with three buttons:
  - `[Read article]` — opens article URL in a new tab (`rel="noopener noreferrer"`)
  - `[Explore]` — `hx-post="/news/discuss"`, on success sets active session and renders the sectioned first_response in the chat pane
  - `[Fact Check]` — `hx-post="/news/fact-check"`, runs the ADK Search → Verdict pipeline; verdict card swaps in below the article card

### Phase 7 Completion Criteria
- [x] Sidebar opens/closes with smooth transition; state persists in `localStorage`
- [x] Sidebar shows hierarchical sessions (regular, 📰 news_discussion, ⚡ learn_more) with expand/collapse on `news_discussion` roots
- [x] Always-visible chat input — sending a message with no active session auto-creates a `regular` session
- [x] Chat sends a message and receives a plain markdown response from the LangGraph ReAct agent
- [x] LangGraph agent can call `get_latest_ai_news` mid-conversation; first message of a new session injects top 5 cached headlines into the system prompt
- [x] Right pane shows News panel with 4 working tabs (AI / Dev / World / Bio)
- [x] Each article card has `[Read article]`, `[Explore]`, and `[Fact Check]` buttons — Fact Check hidden for research/preprint sources
- [x] Hourly news curation re-ranks RSS articles by importance via DeepSeek
- [x] `[Explore]` creates a `news_discussion` session and renders the sectioned first response (direct DeepSeek call)
- [x] Sectioned response cards have a working `[Explore]` button that opens `/learn/<id>` in a new tab
- [x] `/learn/<id>` route uses the same 3-pane layout
- [x] `[Fact Check]` calls Gemini with Google Search grounding and renders a verdict card in-place
- [x] `[Fact Check]` returns a graceful error card when `GOOGLE_API_KEY` is unset

---

## Phase 8 — UX Polish, Inline Quiz & Adaptive Follow-up (`feature/auth`)

> **Status:** ✅ shipped on the `feature/auth` branch.

### Goal
Improve loading feedback, prevent double-submission, move the quiz inline, add an adaptive follow-up quiz, and add a visual active-session indicator in the sidebar.

### Features Shipped

#### 8.1 Button Disable During Content Loads

A single Alpine boolean `contentBusy` in `appState()` gates both the **Send** and **🧠 Check Knowledge** buttons. It is set `true`/`false` by:
- HTMX `htmx:beforeRequest` / `htmx:afterRequest` listeners on `document.body` when the target is `#chat-messages` (declarative chat send).
- Manual calls to `window._setContentBusy(true/false)` inside `exploreSection()`, `generateSectionQuiz()`, `generateQuizForSession()`, and sidebar session-switch handlers.

`chatLoading` tracks the chat form spinner separately. Both are OR'd in the `:disabled` binding.

**Note (Phase 13):** News card Explore (`discussArticle()`) was deliberately moved out of the `contentBusy` scope. It runs as a background fetch and only controls its own per-card `exploreLoading` spinner — the Send button is never disabled by a news card action.

#### 8.2 News Panel Loading Overlay

Alpine `newsPanelLoading` boolean; HTMX body listeners detect requests targeting `#right-panel`. An absolutely-positioned overlay (`z-20`, `backdrop-blur`) covers the right pane with a spinner while news is fetching — existing content remains visible.

**Templates changed:** `backend/templates/app/index.html` — added `relative` class on right `<aside>` + loading overlay `<div>`.

#### 8.3 Cache `_age_hours` Fix

`_age_hours` is computed at fetch time and must not be persisted in Redis (the frozen value becomes stale). Fixed in:
- `backend/api/news/cache.py` — `set_cache()` strips the field before `r.setex`.
- `backend/api/news/service.py` — `get_topic_news()` strips the field before both `r.setex` calls (hit and fallback paths).

#### 8.4 Inline Quiz in `#chat-messages`

The quiz no longer opens in a new tab. Clicking **🧠 Check Knowledge**:
1. `POST /quiz/generate {session_id}` → `{attempt_id, quiz_session_id}`
2. `htmx.ajax('GET', '/quiz/{attempt_id}/partial', { target: '#chat-messages', swap: 'innerHTML' })`
3. `partials/quiz_inline.html` is rendered with `x-data="quizStateInline('qdata-{attempt_id}')"`.
4. The outer quiz div gets class `knr-quiz-root` — used by `htmx:afterSettle` to detect whether a quiz is active.

`quiz.js` changes:
- `quizStateInline()` / `quizStateFullPage()` pass `raw.session_id` as new `parentSessionId` param.
- `quizState()` gains `parentSessionId` field.
- `_dispatchViewState()` method dispatches `quiz-view-changed` CustomEvent on init and after submit.
- `retryQuiz()` uses `htmx.ajax(..., { target: '#chat-messages', swap: 'innerHTML' })` for inline retry.

#### 8.5 Quiz View State in `appState()`

`appState().init()` listens for `quiz-view-changed`:
```js
window.addEventListener('quiz-view-changed', (e) => {
  this.quizViewState = e.detail;  // {isQuiz, attemptId, quizSessionId, parentSessionId, submitted, score}
});
```

`htmx:afterSettle` on `#chat-messages` clears `quizViewState` if no `.knr-quiz-root` is present (uses `setTimeout(..., 0)` to let Alpine initialise first).

Check Knowledge button disable rule: `quizViewState && !quizViewState.submitted` — tooltip: "Submit the quiz first".

Button label: "🧠 Check Knowledge" when no quiz or quiz submitted; "🧠 Follow-up Quiz" when `quizViewState?.submitted`.

#### 8.6 Adaptive Follow-up Quiz

**`POST /quiz/generate-followup`** — body: `{attempt_id}`

Service (`backend/api/quiz/service.py` — `generate_quiz_followup()`):
1. Loads completed attempt (`completed_at IS NOT NULL`).
2. Builds attempt summary: `"Q: {text}\n  User: {selected_option} → CORRECT/WRONG (correct: {correct_option})"` per question.
3. Calls `generate_mcq_followup(attempt_summary)` in `generator.py`.
4. Creates new `mcq_attempts` row.
5. Creates sibling `chat_session` (same `parent_session_id` as the source session) with title `"Quiz: {source_title} (follow-up)"`.
6. Returns `{attempt_id, quiz_session_id, questions, session_id}`.

`MCQ_FOLLOWUP_PROMPT` in `backend/agent/prompts.py`:
- 8 new questions; prioritise wrong-answered concepts at deeper level.
- For correct answers: probe related/adjacent ideas.
- No verbatim question reuse. Technical concepts only.

Frontend: `window.generateFollowupQuiz(attemptId, parentSessionId, onLoading, onDone)` in `app.js` — called from `generateQuiz()` when `quizViewState.submitted` is true.

#### 8.7 Sidebar Green Dot Active Indicator

**`partials/session_list.html`** changes:
- Each `<a>` gets `data-session-id="..."`, `class="relative ... pr-5 min-w-0"`.
- A `.knr-dot hidden absolute right-1.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full pointer-events-none` `<span>` is inserted inside each `<a>`.
- Collapse toggle: `@click.stop="open = !open; $nextTick(() => window._reapplyActiveDot && window._reapplyActiveDot())"`.

**`window._reapplyActiveDot()`** in `app.js`:
1. Reset: hide all `.knr-dot` spans; remove `bg-gray-800 text-white` from all session links.
2. Find active link by `data-session-id`.
3. Mark active link with `bg-gray-800 text-white`.
4. If active link is visible (checked via `_isSessionLinkVisible` — walks `node.style.display` up the DOM), place `bg-green-400` dot on it.
5. Otherwise walk `[x-data]` ancestors to find nearest visible parent row; place `bg-green-300` (softer) dot on that.

**`_isSessionLinkVisible(el, container)`** — walks ancestors checking `node.style.display === 'none'` (Alpine `x-show` sets inline style). More reliable than `offsetParent` for Alpine-managed visibility.

Triggered from: `setActiveSession()`, `htmx:afterSettle` on `#session-list`, and collapse-toggle clicks.

### Items Deferred from the Original Phase 7 Plan
The following were specified in the original plan but were **not shipped** — they were superseded by simpler designs or moved to a later phase:

- ❌ Single ADK `SequentialAgent` covering every chat reply (Research → Fact Check → Editor) — replaced by the layered design in `ARCHITECTURE.md §25`. The chat path uses LangGraph; the on-demand `[Fact Check]` button uses a direct `google-genai` call with Google Search grounding (no ADK).
- ❌ Inline per-section `[Quiz]` button on sectioned responses (`POST /chat/quiz-section`, `quiz_agent.py`) — not implemented. MCQ generation remains a separate full-page quiz flow (Phase 4 / hierarchical quiz in Phase 6).
- ❌ `confidence` field on each section, threshold-based section dropping — not implemented. Section validation is structural only (intro / sections / outro / learn_more_topic).

---

## Phase 9 — Embedding-Based Topic News (semantic search upgrade)

**Branch:** `feature/auth` (current)

### 9.1 Motivation

The previous topic-news implementation used keyword matching with a hardcoded `_STOPWORDS` set and a proportional `min_score` threshold. This produced false positives (biology articles in an AI topic, "bug spray" matching a "2026 Manufacturing Roadmap" via year extraction) and missed semantically related articles that used different vocabulary. The root cause was structural — string matching cannot represent meaning.

### 9.2 Architecture Overview

Three components work together:

```
APScheduler (_refresh_all job, every ~1.5 h)
  └─ fetch ALL_FEEDS → embed_articles() → Redis ARTICLE_EMBED_KEY (TTL 1 h)

GET /news/topic-partial
  └─ service.get_topic_news()
       └─ check Redis topic result cache (TTL 30 min / 10 min)
            └─ cache miss → fetch_topic_news()
                 └─ load ARTICLE_EMBED_KEY from Redis (or embed fresh on miss)
                      └─ weighted_scores() → adaptive_threshold() → mmr_rerank()
                           └─ store result in topic result cache → return
```

### 9.3 Files Changed

| File | Change |
|------|--------|
| `backend/api/news/embeddings.py` | Complete rewrite — model loader, `embed_articles()`, `weighted_scores()`, `adaptive_threshold()`, `mmr_rerank()` |
| `backend/api/news/cache.py` | `fetch_topic_news()` rewritten; `refresh_article_embeddings()` added; `_collect_all_articles()` extracted as helper |
| `backend/core/scheduler.py` | `_refresh_all()` now calls `refresh_article_embeddings()` after category feed refresh |
| `requirements.txt` | Added `sentence-transformers>=2.7` |
| `docs/ARCHITECTURE.md` | §3.5, §6.2, §6.3 (new), §25.1, §26 updated |

### 9.4 Improvements Implemented

**1. Pre-computed article embeddings (scheduler)**
- `refresh_article_embeddings()` fetches ALL_FEEDS, embeds all article titles + summaries, stores as `{article + title_emb + summary_emb}` JSON in Redis.
- Called by `_refresh_all()` — no extra RSS fetches on the hot path.
- Topic queries load pre-computed embeddings (~5 ms Redis hit) instead of re-fetching feeds (2–5 s).

**2. Separate title and summary embeddings with weighted scoring**
- `embed_articles()` encodes title and summary independently.
- `weighted_scores()`: `score = 0.7 × cos_sim(topic, title) + 0.3 × cos_sim(topic, summary)`.
- Titles carry more signal; summaries add context without diluting the title match.

**3. Adaptive similarity threshold**
- `adaptive_threshold(scores, floor=0.15)` = `max(0.15, top_score × 0.6)`.
- Replaces the fixed `_MIN_SIMILARITY = 0.25` constant.
- Scales with match quality: strong topic → strict threshold (filters noise); niche topic → relaxed threshold (still surfaces results).

**4. Maximal Marginal Relevance (MMR) re-ranking**
- `mmr_rerank()` in `embeddings.py` implements the standard MMR algorithm.
- Iteratively picks the next article maximising `λ × relevance − (1−λ) × max_sim_to_selected` (λ = 0.6).
- Prevents 15 articles from the same source or sub-angle appearing in results.
- Diversity is computed on a re-normalised weighted combination of title + summary embeddings.

**5. Model version cache invalidation**
- `MODEL_VERSION = "v1"` is embedded in the Redis key: `news:article_embeddings:all-MiniLM-L6-v2:v1`.
- Upgrading the model requires only bumping `MODEL_VERSION` — old keys become unreachable and expire by TTL naturally. No manual cache flush needed.

**6. Age recomputation on cache load**
- `_age_hours` is recomputed from the stored `published` timestamp each time embeddings are loaded from Redis.
- Prevents articles appearing newer than they are when the embedding store is 30–60 min old.

**7. Keyword fallback**
- `_rank_by_keywords()` is retained as a silent fallback.
- Triggered when `sentence-transformers` fails to load (first deploy before model download, OOM, import error).
- No crash, no user-visible error — slightly less accurate results.

### 9.5 Embedding Model

| Property | Value |
|---|---|
| Library | `fastembed` (ONNX runtime — no PyTorch, ~60 MB install) |
| Model | `sentence-transformers/all-MiniLM-L6-v2` (SBERT, via fastembed) |
| Dimensions | 384 |
| Download size | ~80 MB (one-time, cached by library) |
| Inference | CPU; ~150 ms for 150 articles (batch) |
| API key required | No |
| Normalisation | L2-normalised (dot product = cosine similarity) |

### 9.6 Redis Memory Impact

~150 articles × 2 embeddings × 384 floats × 4 bytes ≈ **460 KB** for the embedding store. Well within the `maxmemory 128mb` Docker Compose limit alongside all other keys.

### 9.7 Latency Profile (after warm-up)

| Operation | Before | After |
|---|---|---|
| Topic news (cache hit) | ~5 ms | ~5 ms (unchanged) |
| Topic news (cache miss) | 2–5 s (feed fetch + embed) | ~20 ms (Redis load + 1 embed + MMR) |
| First deploy (model download) | N/A | ~30 s one-time |
| Scheduler embed refresh | N/A | ~2 s added to each `_refresh_all` cycle |

---

## Phase 10 — Economy & Health Tabs + Topic-News Fallback

**Branch:** `feature/auth` (current)

### 10.1 New News Categories

Two new categories added to `backend/api/news/feeds.py` and surfaced as tabs in `news_panel.html`:

| Tab label | Category key | Sources |
|---|---|---|
| Econ | `economy` | Reuters Business, BBC Business, The Economist, MarketWatch, Financial Times, Bloomberg, CNBC |
| Health | `health` | BBC Health, Reuters Health, Medical News Today, WHO News, Science Daily Health, Healthline, Allure |

The tab bar is now six tabs: AI · Dev · World · Bio · Econ · Health. No other code changes required — `NEWS_FEEDS` is the single source of truth for both the scheduler refresh and the ALL_FEEDS embedding store.

### 10.2 Topic-News Fallback — Known Issue & Pending Fix

**Problem observed:** When a user is inside a `news_discussion` session (e.g. a BBC Health article about quintuplets), the right-pane topic news panel shows AI articles instead of health-related content. Root cause: the embedding store is empty on a fresh deploy (scheduler hasn't run yet), the on-the-fly keyword fallback finds no articles matching the specific article title as a query, and `service.get_topic_news()` hard-codes a final fallback to `get_news("ai")`.

**Implemented fallback chain:**

```
fetch_topic_news(topic) → results → return
                        → empty
                             → session has source_category → get_news(source_category)   [Case 1]
                             → no source_category → embed(topic) vs CATEGORY_LABELS → get_news(closest)  [Case 2]
```

**Case 1 — `news_discussion` sessions (data provenance):**
- `POST /news/discuss` now accepts `source_category` from the frontend (the active tab at time of click).
- `news_panel.html` Explore button sends `source_category: category` in `hx-vals`.
- `discuss/service.py` persists it with `UPDATE chat_sessions SET source_category = %s`.
- `learn_more` children inherit `source_category` from their parent — the full session tree stays topically consistent.
- Migration `008_source_category.sql` adds the column (`ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS source_category VARCHAR(20)`).

**Case 2 — `regular` sessions (zero-shot embedding classification):**
- `CATEGORY_LABELS` dict in `embeddings.py` maps each category key to a descriptive label string.
- `get_category_embeddings(redis_client)` computes embeddings for all labels, caches in Redis 24 h under `news:category_embeddings:…` (model + version in key for automatic invalidation on upgrade).
- `_infer_category_by_embedding(topic)` in `service.py` embeds the topic, dot-products against label embeddings, returns highest-similarity category.
- No hardcoded keyword lists. Tuneable by editing `CATEGORY_LABELS` strings only.

---

## Phase 11 — Learning Platform Prompt Redesign

**Branch:** `feature/auth` (current)

### 11.1 Motivation

The existing AI prompts were designed for a **technical assistant** role: answer AI/ML/software questions accurately. As the product evolved into a **general learning platform** anchored in current news, three structural gaps emerged:

1. **Domain lock** — `SYSTEM_PROMPT` restricts to AI, ML, and software. The news panel covers World, Bio, Econ, Health — the AI tutor must match that breadth.
2. **No completeness guarantee** — the AI picks 3–5 sections it finds interesting, potentially missing important conceptual pillars. A learner cannot know what was omitted.
3. **No learning progression** — sections appear in arbitrary order rather than foundational → mechanism → application → advanced.
4. **No misconception field** — common wrong assumptions are not surfaced; learners form bad mental models silently.
5. **Weak intro/outro** — intro does not state prerequisite knowledge; outro does not recommend an exploration order.

See `ARCHITECTURE.md §27` for the full design rationale.

### 11.2 Files Changed

| File | Change |
|------|--------|
| `backend/agent/prompts.py` | All four teaching prompts rewritten; `SYSTEM_PROMPT`, `DISCUSSION_PROMPT`, `LEARN_MORE_PROMPT`, `NEWS_CURATION_PROMPT` |
| `backend/templates/app/index.html` | Chat input placeholder updated to reflect domain breadth |

### 11.3 `SYSTEM_PROMPT` Changes (Scenario 1 — Manual Chat)

**Removed:**
- "specialising in artificial intelligence, machine learning, and related technologies" domain declaration
- Fixed bullet list of AI/ML topics

**Added:**
- Domain: any topic (science, history, technology, economics, biology, politics, mathematics, arts)
- Completeness mandate: "Cover every major pillar at the level asked. A learner must see the complete shape of the subject. Missing a significant concept is a failure."
- Section ordering rule: foundational → mechanism → application → advanced/edge cases
- `misconception` field in every section schema: one sentence — the most common wrong assumption about this concept
- Prerequisite signal in `intro`: state what background is assumed or "No prior knowledge needed"
- Adaptive section count: 4–6 typically, up to 7 for complex multi-pillar subjects; minimum 3
- Outro strengthened: must give concrete recommended exploration order

### 11.4 `DISCUSSION_PROMPT` Changes (Scenario 2 — News Explore)

**Added:**
- Completeness mandate: "Cover every conceptual pillar this news event touches — a reader should be able to see all the concepts this event exposes"
- `misconception` field per section
- Section ordering: foundational → mechanism → application
- `intro` must state which areas of knowledge this news event touches

**Unchanged:**
- Do-not-discuss rules (names, political opinions, dates as subjects)
- News-anchored scope (not full domain — only concepts this event exposes)

### 11.5 `LEARN_MORE_PROMPT` Changes (Scenario 3 — Section Explore)

**Added:**
- Breadcrumb instruction: `intro` must include "This is a deep-dive into [topic], a sub-component of [parent concept]." — prevents learners from getting lost after multiple Explore clicks
- Completeness mandate: cover ALL sub-components of the requested concept
- `misconception` field per section
- Section ordering: same foundational → applied → advanced rule

**Unchanged:**
- Depth-first focus — never revisit sibling concepts from the parent response
- `learn_more_topic` must be more specific than section title

### 11.6 `NEWS_CURATION_PROMPT` Changes

**Changed:** audience description expanded from "AI engineers, ML researchers, software developers" to "a general educated audience" to match the platform's broad topic coverage.

### 11.7 Placeholder Text

`backend/templates/app/index.html` line 148:

```
Before: placeholder="Ask anything about AI, ML, or software..."
After:  placeholder="Ask anything — science, history, technology, economics…"
```

### 11.8 Section Schema After Phase 11

```json
{
  "id": "s1",
  "title": "<concept name>",
  "content": "<2–3 sentence explanation — how it works and why it matters>",
  "key_points": [
    "<concrete, testable learning point>",
    "<second learning point>",
    "<third learning point>"
  ],
  "misconception": "<the single most common wrong assumption about this concept — one sentence>",
  "learn_more_topic": "<specific sub-topic for deeper Explore follow-up>"
}
```

The `misconception` field is new in Phase 11. Backend parsing validates its presence on sectioned responses from Scenarios 1, 2, and 3. It is displayed as a callout card below `key_points` in `sectioned_message.html`.

---

## Phase 12 — URL Fetch Tool (ReAct pattern)

**Branch:** `feature/auth` (current)

### 12.1 Motivation

When a user pastes a public URL in the main chat and asks to explain it, the LangGraph agent previously had no way to read the page — it would respond from training memory only, risking outdated or hallucinated content. Phase 12 adds a `fetch_url` LangGraph tool following the industry-standard ReAct pattern used by ChatGPT browsing, Perplexity, and Claude web search.

No third-party reader service is used. Plain `requests` + `BeautifulSoup4` is sufficient for the common case (news articles, Wikipedia, blog posts, documentation, GitHub READMEs). JS-rendered SPAs without static HTML will return little or no content — this is a known and accepted limitation.

### 12.2 Files Changed

| File | Change |
|------|--------|
| `backend/agent/tools.py` | Added `fetch_url` tool |
| `backend/agent/graph.py` | Added `fetch_url` to tools list |
| `requirements.txt` | Added `requests`, `beautifulsoup4` |

### 12.3 Tool Behaviour

```
User: "explain https://example.com/article"
        │
        ▼
LangGraph agent (DeepSeek) sees URL, calls fetch_url(url)
        │
        ▼
requests.get(url, timeout=8)
BeautifulSoup strips script/style/nav/footer/header/aside
Extracts <main> or <article> or <body> text
Truncates to 4 000 chars
        │
  ┌─────┴─────────────────────────────────┐
  │ success                               │ failure
  ▼                                       ▼
page text returned to agent        descriptive error string
        │                          agent notes failure in response
        ▼
DeepSeek generates sectioned structured response
grounded in actual page content
```

### 12.4 Error Handling

| Failure | Returned string |
|---------|----------------|
| Timeout (>8 s) | "Request timed out — server took too long" |
| HTTP 4xx/5xx | "HTTP {status} error fetching {url}" |
| Paywall / login wall | "<100 chars extracted — page may require login" |
| JS-only page | "<100 chars extracted — page may be JS-rendered" |
| Any other exception | "Could not fetch {url}: {reason}" |

The agent uses the error string as context and tells the user why it couldn't read the page, rather than silently hallucinating content.

---

## Phase 13 — News Panel & Quiz UX Polish

**Branch:** `feature/auth` (current)

### 13.1 Background News Explore (`discussArticle`)

**Problem:** Clicking Explore on a news card fired an HTMX request with `hx-target="#chat-messages"`, which triggered the global `htmx:beforeRequest` → `contentBusy = true` → disabled the Send button for the duration of the LLM call (~5–10 s).

**Fix:** Replaced the HTMX button with a JS `fetch()` call (`window.discussArticle()`). The session is created in the background; `contentBusy` is never set. On success the sidebar refreshes and a toast guides the user. The news card Explore button shows its own per-button spinner (from Alpine `exploreLoading`) without blocking any other interaction.

**Files changed:**
- `backend/static/app.js` — added `discussArticle()`, removed `onDiscussResponse()`
- `backend/templates/partials/news_panel.html` — button converted from HTMX to `@click="discussArticle(...)"`
- `backend/templates/partials/topic_news_panel.html` — same; button also renamed "Discuss" → "Explore"

### 13.2 `newsCardState()` Alpine Component

A named Alpine component (`newsCardState(articleId)`) was extracted to `app.js` and is used by both news panel templates via `x-data="newsCardState('...')"`. It replaces the inline `{exploreLoading: false, factChecking: false}` object and adds:

- `alreadyExplored` — initialised from `localStorage` (`knroot_explored` JSON array, max 500 entries) on component mount
- `markExplored()` — sets `alreadyExplored = true` and saves the article ID to `localStorage`

**Visual indicator:** a small green checkmark icon appears inside the Explore button when `alreadyExplored` is true. The button remains fully clickable — users can explore an article multiple times.

### 13.3 AI Top-Picks Star Badge (`_curated`)

`curate_with_ai()` in `backend/api/news/cache.py` now:

- Uses `n_select = min(len(articles) // 2, 5)` — selects at most 5 articles, always at most half the total, so there is always a meaningful non-curated remainder
- Tags selected articles with `_curated: True` in the returned dict (preserved through `set_cache` since only `_age_hours` is stripped)

The news panel template (`news_panel.html`) shows a gold star SVG icon before the source name and an amber card border when `article.get('_curated')` is truthy. The force-refresh bug in `/news/partial` (query param `force` was ignored — hardcoded `False`) was also fixed in this phase.

### 13.4 Quiz: "Explore this topic" on Correct Answers

**Problem:** Correctly answered quiz questions showed no follow-up action — users who knew an answer had no way to dive deeper without first getting something wrong.

**Fix:** A new footer strip (`x-show="submitted && answers[q.id] === q.correct"`) is added to each question card in `quiz_inline.html`. It shows only the **Explore this topic** button — no explanation text, since the user already knows the answer. The button calls the existing `exploreRelearn(q.id, q.topic)` function and shares the same `relearn[q.id]` state (lazy-initialised by `_panel()`).

| State | Incorrect answer | Correct answer |
|-------|-----------------|----------------|
| After submit | "Why was I wrong?" → explanation → Explore | Explore this topic |
| After Explore clicked | ✓ Loaded badge | ✓ Loaded badge |

**File changed:** `backend/templates/partials/quiz_inline.html` only.
