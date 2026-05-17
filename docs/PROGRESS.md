# Knowledge Root — Implementation Progress

> Updated after each PR merge. Check boxes as tasks complete. See `IMPLEMENTATION_PLAN.md` for full task detail and test specs.
>
> **Legend:** ✅ Done · 🔄 In Progress · ⏳ Not Started · ❌ Blocked

---

## Summary Dashboard

| Phase | Branch | Status | Tests | PR |
|-------|--------|--------|-------|----|
| 1 — Auth | `feature/auth` | ✅ Done | unit ✅ · e2e ✅ | merged |
| 2 — Session Management | `feature/session-management` | ✅ Done | unit ✅ · e2e ✅ | merged |
| 3 — Smart News Cache | `feature/smart-news-cache` | ✅ Done | unit ✅ · e2e ✅ | merged |
| 4 — Knowledge Check | `feature/knowledge-check` | ✅ Done | unit ✅ · e2e ✅ | merged |
| 5 — Polish & Hardening | `feature/polish` | ✅ Done | unit ✅ · e2e ✅ | merged |
| 6 — News Tabs + Discuss + Learning Tree | `feature/news-discuss-learn` | ✅ Done | unit ✅ · e2e ✅ | merged |
| Rich Artifacts | `feat/rich-artifacts` | ✅ Done | unit ✅ · e2e ✅ | in progress |

**Current test counts (2026-05-17):** 404+ unit tests · 119+ e2e tests across 5 files

---

## Phase 1 — Authentication (`feature/auth`)

### Infrastructure
- [x] Add `flask-session`, `pydantic`, `bcrypt`, `flask-limiter` to `requirements.txt` (removed `PyJWT`)
- [x] Add `SESSION_SECRET_KEY` env var to `docker-compose.yml` and `.env-example`
- [x] Create `requirements-unit.txt` for unit test dependencies (fakeredis, pytest-mock, etc.)
- [x] Create `Makefile` with `test-unit`, `up`, `down`, `logs`, `backend`, `shell-db`, `shell-redis` targets
- [x] Create `.coveragerc` to omit agent/LLM/unimplemented blueprints from coverage measurement

### Database
- [x] Write `backend/migrations/001_users.sql` (users table + indexes)
- [ ] Wire migration into `app.py` startup sequence (needs DB connection in dev/prod)

### Domain & Repository Layer
- [x] `backend/domain/user.py` — `User` frozen dataclass + `to_profile()` serialisation helper
- [x] `backend/repositories/user_repository.py` — `UserRepository` class with all user SQL + `user_repo` module-level singleton

### Pydantic Schemas
- [x] `backend/api/auth/schemas.py` — `RegisterRequest`, `LoginRequest` with `@model_validator` cross-field validation

### Backend — Auth Routes & Service
- [x] `backend/api/auth/service.py` — `register_user()`, `login_user()`, `get_user()` — calls `user_repo`, returns `User`
- [x] `POST /auth/register` — Pydantic validation, bcrypt hash, session set, PRG redirect / HTMX 204+HX-Redirect
- [x] `POST /auth/login` — username or email lookup, bcrypt verify, session set, PRG / HTMX
- [x] `POST /auth/logout` — `session.clear()`, redirect to `/login`
- [x] `GET /auth/me` — returns `user.to_profile()` JSON (requires `@require_api_auth`)
- [x] Rate limiting: `3/min` on `/auth/register`, `10/min` on `/auth/login`

### Backend — Auth Middleware
- [x] `backend/core/auth.py` — `require_auth` (page redirect) + `require_api_auth` (401 JSON); sets `g.user_id` from `session['user_id']`

### Backend — Page Routes
- [x] `backend/api/pages/routes.py` — `GET /`, `GET /login`, `GET /register` (redirects if already authed), `GET /app` (requires `@require_auth`)

### Templates & Static
- [x] `backend/templates/base.html` — HTML shell with HTMX, Alpine.js, Tailwind CDN
- [x] `backend/templates/auth/login.html` — HTMX form, Alpine.js password toggle, `HX-Redirect` handler
- [x] `backend/templates/auth/register.html` — HTMX form, Alpine.js password toggle
- [x] `backend/templates/app/index.html` — dashboard with nav and sign-out
- [x] `backend/static/app.js` — HTMX global config + `HX-Redirect` full-navigation handler

### Flask App Factory
- [x] `backend/app.py` — `create_app()` factory with blueprints, extensions, error handlers; Flask-Session skipped when TESTING
- [x] `backend/config.py` — `Config`, `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`
- [x] `backend/extensions.py` — `redis_client`, `limiter`, `init_session()`

### Backend Unit Tests
- [x] `tests/conftest.py` — `client`, `authed_client` (session_transaction), `valid_user_payload`, rate-limit reset fixture
- [x] `test_register_success_redirects` (302)
- [x] `test_register_success_sets_session`
- [x] `test_register_htmx_returns_204_with_hx_redirect`
- [x] `test_register_duplicate_username_returns_409`
- [x] `test_register_duplicate_email_returns_409`
- [x] `test_register_weak_password_returns_422`
- [x] `test_register_invalid_email_returns_422`
- [x] `test_register_invalid_username_returns_422`
- [x] `test_register_invalid_phone_returns_422`
- [x] `test_register_missing_full_name_returns_422`
- [x] `test_login_success_redirects`
- [x] `test_login_success_sets_session`
- [x] `test_login_htmx_returns_204_with_hx_redirect`
- [x] `test_login_by_email_succeeds`
- [x] `test_login_wrong_password_returns_401`
- [x] `test_login_unknown_user_returns_401`
- [x] `test_login_missing_fields_returns_422`
- [x] `test_logout_clears_session`
- [x] `test_logout_without_session_still_redirects`
- [x] `test_logout_htmx_returns_204_with_hx_redirect`
- [x] `test_me_without_session_returns_401`
- [x] `test_me_with_session_returns_profile`
- [x] `test_me_user_not_found_returns_401`
- [x] `test_rate_limit_on_login`
- [x] `tests/unit/test_pages.py` — page route status codes, redirects, auth guards

### E2E Tests (`e2e/test_auth.py` → covered in `e2e/test_app.py`)
- [x] `user can register with valid data and is redirected to /app`
- [x] `register with existing username shows inline error`
- [x] `user can log in with username`
- [x] `user can log in with email`
- [x] `wrong password shows inline error`
- [x] `unauthenticated user redirected from /app to /login`
- [x] `user can log out and cannot access /app`
- [x] `session cookie persists across page reloads`

### Phase 1 Acceptance Criteria
- [x] All unit tests pass — coverage ≥ 80% (`make test-unit`)
- [x] All E2E tests pass (`make test-e2e`)
- [x] No secrets in code or `.env` committed
- [x] Implementation merged to `main`

---

## Phase 2 — Session Management (`feature/session-management`) ✅

### Database
- [x] Write `migrations/002_chat_sessions.sql`
- [x] Wire migration into `app.py` startup

### Backend — Sessions
- [x] `POST /sessions` — create session, return session row
- [x] `GET /sessions` — list user's sessions ordered by `last_message_at DESC`
- [x] `PATCH /sessions/{id}` — rename with ownership check
- [x] `DELETE /sessions/{id}` — delete with ownership check + cascade
- [x] `GET /sessions/{id}/messages` — replay from LangGraph state

### Backend — Chat Integration
- [x] Require `session_id` in request body
- [x] Verify session ownership (`user_id = g.user_id`)
- [x] Use session's `thread_id` as LangGraph config key
- [x] Update `last_message_at` on every message
- [x] Trigger auto-title generation after first reply
- [x] Return `title` in response

### Frontend (Jinja2 + HTMX)
- [x] `session_list.html` partial — sidebar session list with hierarchy
- [x] New Chat button clears session + restores news panel
- [x] Delete session via `window.deleteSession()` + `#knr-confirm` modal

### Backend Unit Tests (`tests/unit/test_sessions.py`) — ✅ complete
- [x] create, list, rename, delete, ownership checks, auto-title, messages

### E2E Tests — covered in `e2e/test_app.py` `TestChat` + `TestSessionManagement`
- [x] new chat creates a session in the sidebar
- [x] session gets auto-title after first message
- [x] user can delete a session
- [x] deleted session is no longer in sidebar
- [x] switching sessions loads correct message history

### Phase 2 Acceptance Criteria
- [x] All unit tests pass with ≥ 80% coverage
- [x] All E2E tests pass
- [x] Implementation merged to `main`

---

## Phase 3 — Smart News Cache (`feature/smart-news-cache`) ✅

### Infrastructure
- [x] `redis`, `APScheduler` in `requirements.txt`
- [x] Redis service in `docker-compose.yml`
- [x] `REDIS_URL` env var configured

### Database
- [x] `migrations/003_news_cache.sql`

### Backend — `backend/api/news/`
- [x] `cache.py` — Redis day/hour cache; `fetch_topic_news()` embedding pipeline
- [x] `service.py` — `get_news(category)` / `get_topic_news(topic)`
- [x] `feeds.py` — 6-category RSS feed dict (ai / programming / political / biology / economy / health)
- [x] `embeddings.py` — MiniLM-based article scoring + MMR reranking
- [x] APScheduler `promote_hour_to_day()` job
- [x] 6-tab news panel (AI / Dev / World / Bio / Econ / Health)
- [x] Explore button on articles → `POST /news/discuss`

### Backend Unit Tests (`tests/unit/test_news.py`) — ✅ complete

### E2E Tests — covered in `e2e/test_app.py` `TestNewsPanel` + `TestNewsDiscuss`
- [x] news panel loads on app open
- [x] tab switching (AI / Dev / World)
- [x] Explore button creates discussion session in sidebar

### Phase 3 Acceptance Criteria
- [x] All unit tests pass with ≥ 80% coverage
- [x] All E2E tests pass
- [x] Implementation merged to `main`

---

## Phase 4 — Knowledge Check (`feature/knowledge-check`) ✅

### Database
- [x] `migrations/004_mcq_attempts.sql`

### Backend — `backend/api/quiz/`
- [x] `POST /quiz/generate` — LLM MCQ generation, 8 questions, validates, strips `correct` field from response
- [x] `GET /quiz/attempt/{id}` — returns state; includes `correct` only when `completed_at IS NOT NULL`
- [x] `PUT /quiz/attempt/{id}` — upsert answers; if `completed: true`, scores + sets `completed_at`
- [x] `POST /quiz/retry` — clones questions into new attempt
- [x] `GET /quiz/attempts?session_id=` — lists attempts
- [x] `GET /quiz/attempt/{id}/relearn/{question_id}` — lazy LLM explanation + cache
- [x] `POST /quiz/generate-followup` — follow-up quiz targeting missed questions
- [x] `GET /quiz/<attempt_id>/partial` — renders inline quiz into `#chat-messages`
- [x] `generator.py` — `_validate()`, `_shuffle_options()`, relearn prompt + cache
- [x] MCQ validator: 8 questions, 4 options each, `correct` 0–3, text ≥ 15 chars
- [x] Quiz inline in chat (`knr-quiz-root` component loaded via HTMX into `#chat-messages`)

### Backend Unit Tests (`tests/unit/test_quiz.py`) — ✅ 50+ tests
- [x] Auth guards for all 6+ routes
- [x] Generate quiz, get attempt (open + completed), save/submit answers, retry, list attempts
- [x] Relearn endpoint returns explanation
- [x] `generate-followup` route: auth, validation, service call
- [x] `/<attempt_id>/partial` route: auth, renders `Knowledge Check` heading + `knr-quiz-root` class
- [x] `_validate()`: rejects too few questions, wrong option count, invalid correct index, short text
- [x] `_shuffle_options()`: preserves correct answer text, all options, non-option fields; doesn't mutate

### E2E Tests — `e2e/test_quiz.py` (12 tests)
- [x] Check Knowledge button appears with active session
- [x] Quiz loads inline into `#chat-messages`
- [x] Quiz shows questions (option buttons present)
- [x] Submit quiz shows score + Retry button
- [x] Retry loads new quiz inline
- [x] "Why was I wrong?" button appears; clicking shows `.bg-amber-50` explanation panel

### Phase 4 Acceptance Criteria
- [x] All unit tests pass with ≥ 80% coverage
- [x] All E2E tests pass
- [x] Implementation merged to `main`

---

## Phase 5 — Polish & Hardening (`feature/polish`) ✅

### Security
- [x] Rate limit `/auth/login`: 10/min per IP via Flask-Limiter
- [x] Rate limit `/auth/register`: 3/min per IP
- [x] No stack traces in production error responses (`register_error_handlers`)
- [x] `.env` in `.gitignore`

### UX & Responsiveness
- [x] Sidebar collapse via `w-0 overflow-hidden` toggle
- [x] Mobile right-panel height fix (`h-40` → `md:h-auto`)
- [x] Toast notifications (`backend/static/toast.js`)
- [x] `#knr-confirm` custom confirmation modal (replaces native `confirm()`)
- [x] 3-pane layout stable across all tabs (Root / Wall / Profile)

### Backend Unit Tests
- [x] Rate limiting tests in `test_auth.py`

### E2E Tests — covered in `e2e/test_app.py`
- [x] Sidebar toggle collapses sidebar
- [x] New Chat button restores news panel
- [x] Session delete via modal confirmation
- [x] Three-pane layout verification

### Phase 5 Acceptance Criteria
- [x] All unit tests pass with ≥ 80% coverage
- [x] All E2E tests pass
- [x] Implementation merged to `main`

---

---

## Phase 6 — News Tabs, Discuss & Learning Tree (`feature/news-discuss-learn`) ✅

### Infrastructure
- [x] 6-category feeds (ai / programming / political / biology / economy / health)
- [x] Category-keyed cache (`news:day:{date}:{category}`)
- [x] APScheduler iterates all categories on promote

### Database
- [x] `migrations/002_chat_sessions.sql` — session hierarchy columns
- [x] `migrations/005_session_messages.sql`, `006_cascade_fk.sql`, `007_quiz_session.sql`, `008_source_category.sql`

### Backend — Discuss + Learn More
- [x] `POST /news/discuss` — creates `news_discussion` session, sectioned LLM response
- [x] `POST /sessions/{id}/learn-more` — creates `learn_more` child, inherits root, increments depth
- [x] `GET /sessions/{id}/tree` — walks `parent_session_id` chain
- [x] Sectioned response validator (type, intro, sections, outro)
- [x] LLM retry on invalid format

### Backend — Quiz (hierarchical)
- [x] `POST /quiz/generate` — works for regular + hierarchical sessions
- [x] `GET /quiz/attempt/{id}/relearn/{question_id}` — lazy explanation + cache
- [x] `POST /quiz/generate-followup` — follow-up quiz targeting weak areas
- [x] `topic` field on MCQ questions

### Frontend (Jinja2 + HTMX + Alpine.js)
- [x] 6-tab news panel: `news_panel.html`
- [x] Sectioned response: `sectioned_message.html` with section cards + Learn More buttons
- [x] Knowledge tree: `knowledge_tree.html` + `knowledge_tree_panel.html`
- [x] Session list with hierarchy (type icons, depth indent, green-dot indicator)
- [x] Quiz: `quiz_inline.html` + `quiz_section.html` + per-question relearn panel (`.bg-amber-50`)

### Backend Unit Tests — ✅ complete
- [x] `tests/unit/test_discuss.py` — sectioned response parsing, learn-more, tree
- [x] `tests/unit/test_news.py` — category feeds, cache, embeddings

### E2E Tests — `e2e/test_knowledge_root.py` + `e2e/test_quiz.py`
- [x] Explore button on news article creates discussion session
- [x] Sectioned response renders sections + Learn More buttons
- [x] Knowledge tree appears in right panel
- [x] Quiz relearn panel appears for wrong answers

### Phase 6 Acceptance Criteria
- [x] All unit tests pass with ≥ 80% coverage
- [x] All E2E tests pass
- [x] Implementation merged to `main`

---

## Rich Artifacts Feature (`feat/rich-artifacts`)

### What was built

| Area | Change |
|------|--------|
| **JSON schema** | `hierarchy_diagram` (Mermaid flowchart TD) added at response root. `artifacts` array added to each section (`formula` / `chart` / `diagram`). Both fields are optional with defaults — fully backward-compatible with stored messages. |
| **Backend normaliser** | `_normalise_sectioned()` in `chat/service.py` and `discuss/service.py` backfills defaults and filters invalid artifact types on every response parse. |
| **Prompts** | `SYSTEM_PROMPT`, `DISCUSSION_PROMPT`, `LEARN_MORE_PROMPT` updated with `hierarchy_diagram` spec, artifact schema, and guidance on when to include visuals. |
| **Frontend libraries** | KaTeX v0.16 (math), Mermaid v11 (diagrams/hierarchy), Chart.js v4 (data charts) added via CDN in `base.html`. |
| **Artifact renderer** | `backend/static/artifacts.js` — shared IIFE module. Idempotent (data-processed guards). Runs on `DOMContentLoaded` + `htmx:afterSettle`. Exposed as `window.initArtifacts(container)` for Alpine lazy-init. |
| **Main chat template** | `sectioned_message.html` — hierarchy chart zone after intro, `data-section-title` on section cards, `katex-render` on content paragraphs, collapsed artifact toggles with lazy init. |
| **Wall preview template** | `share_session_preview.html` — identical additions; artifacts render in the preview modal and in imported sessions without any extra work. |
| **Unit tests** | 15 new tests in `test_chat.py` (parse normalisation + template rendering). 11 new tests in `test_discuss.py` (pure function + pipeline + template). |
| **E2E mock** | `mock_llm_server.py` `_SECTIONED` updated to include `hierarchy_diagram` + formula artifact on s1 + chart artifact on s2. |
| **E2E tests** | 8 new browser tests in `TestArtifactsRendering` (`test_knowledge_root.py`): hierarchy wrapper present, formula/chart toggle buttons visible, panels reveal on click, text changes to "Hide", panel collapses on second click, sections without artifacts show no toggles. |
| **Architecture doc** | Section 3 (tech stack), Section 18 (response format, content shape, rendering layout, artifact renderer) updated. |

### Key architectural decisions

| Decision | Rationale |
|----------|-----------|
| Path A: artifacts in JSON schema, not LangGraph tool calls | Simpler, no latency added, sufficient for all educational content. Tool-call path reserved for computed/dynamic data (future). |
| Collapsed by default with lazy init | Reduces cognitive load; avoids Chart.js sizing issues on hidden canvases. |
| Hierarchy chart: top-down flowchart, section titles only | Matches sequential foundation→advanced ordering; clean map not a cluttered outline. |
| Click-scroll via DOM traversal (not URL anchors) | Works inside both main chat and wall preview modal's scroll container; no duplicate-ID risk. |
| `textContent` for Mermaid, `data-latex` attr for KaTeX, `data-chart-spec` attr for Chart.js | Prevents XSS from LLM-generated definitions flowing through `innerHTML`. |

---

## Notes & Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-04 | Architecture document created | Baseline before implementation |
| 2026-05-04 | Implementation plan created | Defines all tasks, tests, branches |
| 2026-05-04 | Phase 6 added: News tabs (AI/Programming/Political), Discuss button, sectioned AI responses, Learn More sub-threads, knowledge tree, hierarchical MCQ with relearn | New product requirement |
| 2026-05-05 | Frontend rewritten from React/Vite/TypeScript SPA to Flask SSR (Jinja2 + HTMX + Alpine.js). Auth changed from JWT to Flask-Session + Redis. `frontend/` directory and its Dockerfile removed. Makefile added to replace package.json scripts. | VirtualBox shared folder (vboxsf) cannot create symlinks, breaking npm install. SSR eliminates all Node.js/npm toolchain requirements. Python-only stack is simpler to operate. |
| 2026-05-06 | Added enterprise architecture layers: `backend/domain/` (frozen dataclasses), `backend/repositories/` (all SQL encapsulated, returns domain objects), `backend/api/auth/schemas.py` (Pydantic v2 request validation). Service functions now call `user_repo` and return `User` domain objects. | Flask best practice for business-grade apps: clean separation of HTTP boundary (schemas), business logic (services), data access (repositories), and domain models. Prevents raw dicts leaking across layers and makes tests mock-friendly. |
| 2026-05-15 | Rich artifacts added to sectioned responses (`feat/rich-artifacts`): hierarchy chart (Mermaid), formulas (KaTeX), data charts (Chart.js), diagrams (Mermaid). Path A chosen (JSON schema extension, not LangGraph tool calls). | Provides richer educational explanations without adding latency or infrastructure. Artifacts render in all three surfaces (main chat, wall preview, imported sessions) because message JSON is stored as-is. |
| 2026-05-17 | E2E test suite expanded to 119+ tests across 5 files (`test_app.py`, `test_quiz.py`, `test_knowledge_root.py`, `test_wall.py`, `test_chat.py`). New classes added: `TestQuizRelearn`, `TestCommentDeletion`, `TestUnsaveShare`, `TestFriendsOnlyShare`, `TestFollowRequests`. | Full user-flow coverage for social (wall, comments, follow requests) and quiz (inline quiz, relearn) features. |
| 2026-05-17 | Unit test suite at 404+ tests. 14 new tests added: 9 in `test_quiz.py` (generate-followup route, `/partial` template rendering) and 5 in `test_chat.py` (`/chat/quiz-section` LLM integration + graceful fallback). | Closes unit coverage gaps on inline quiz partial and per-section quiz generation routes. |
| 2026-05-17 | All phases 1–6 + Rich Artifacts marked complete. `PROGRESS.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md` updated to reflect current implementation state. | Documentation catch-up — all docs were showing Phase 1 "In Progress" while full platform was implemented. |
