# Knowledge Root — Implementation Progress

> Updated after each PR merge. Check boxes as tasks complete. See `IMPLEMENTATION_PLAN.md` for full task detail and test specs.
>
> **Legend:** ✅ Done · 🔄 In Progress · ⏳ Not Started · ❌ Blocked

---

## Summary Dashboard

| Phase | Branch | Status | Tests | PR |
|-------|--------|--------|-------|----|
| 1 — Auth | `feature/auth` | 🔄 In Progress | unit ✅ (30/30, 80%+) · e2e ⏳ | — |
| 2 — Session Management | `feature/session-management` | ⏳ Not Started | ⏳ | — |
| 3 — Smart News Cache | `feature/smart-news-cache` | ⏳ Not Started | ⏳ | — |
| 4 — Knowledge Check | `feature/knowledge-check` | ⏳ Not Started | ⏳ | — |
| 5 — Polish & Hardening | `feature/polish` | ⏳ Not Started | ⏳ | — |
| 6 — News Tabs + Discuss + Learning Tree | `feature/news-discuss-learn` | ⏳ Not Started | ⏳ | — |

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

### E2E Tests (`e2e/auth.spec.ts`)
- [ ] `user can register with valid data and is redirected to /app`
- [ ] `register with existing username shows inline error`
- [ ] `user can log in with username`
- [ ] `user can log in with email`
- [ ] `wrong password shows inline error`
- [ ] `unauthenticated user redirected from /app to /login`
- [ ] `user can log out and cannot access /app`
- [ ] `session cookie persists across page reloads`

### Phase 1 Acceptance Criteria
- [x] All unit tests pass — 30/30, coverage ≥ 80% (`make test-unit`)
- [ ] All E2E tests pass (`make test-e2e`)
- [ ] GitHub Actions (ci, code-review, security-review, architecture-review) all green on PR
- [x] No secrets in code or `.env` committed
- [ ] PR merged to `main` with description referencing all ✅ items above

---

## Phase 2 — Session Management (`feature/session-management`)

### Database
- [ ] Write `migrations/002_chat_sessions.sql`
- [ ] Wire migration into `app.py` startup

### Backend — `sessions.py`
- [ ] `POST /sessions` — create session, return session row
- [ ] `GET /sessions` — list user's sessions ordered by last_message_at DESC
- [ ] `PATCH /sessions/{id}` — rename with ownership check
- [ ] `DELETE /sessions/{id}` — delete with ownership check + LangGraph checkpoint cleanup
- [ ] `GET /sessions/{id}/messages` — replay from LangGraph state

### Backend — Update `POST /chat`
- [ ] Require `session_id` in request body
- [ ] Verify session ownership (`user_id = g.user_id`)
- [ ] Use session's `thread_id` as LangGraph config key
- [ ] Update `last_message_at` on every message
- [ ] Trigger auto-title generation after first reply (if `title IS NULL`)
- [ ] Return `title` in response

### Backend — Auto-title (`agent.py`)
- [ ] Add `generate_title(first_user_msg, first_ai_reply)` function
- [ ] Fallback to truncated user message if LLM call fails

### Frontend
- [ ] `src/api/sessions.ts` — CRUD calls
- [ ] `src/hooks/useSessions.ts` — React Query wrapper with optimistic updates
- [ ] `src/components/ChatSidebar.tsx` — grouped list, new chat button
- [ ] `src/components/SessionItem.tsx` — title, timestamp, rename/delete actions
- [ ] Update `App.tsx` — add left-pane ChatSidebar
- [ ] Update `useChat.ts` — accept `session_id`, pass to `/chat`

### Backend Unit Tests (`tests/unit/test_sessions.py`)
- [ ] `test_create_session_returns_201`
- [ ] `test_list_sessions_returns_user_only`
- [ ] `test_rename_session_success`
- [ ] `test_rename_other_users_session_returns_403`
- [ ] `test_delete_session_success`
- [ ] `test_delete_other_users_session_returns_403`
- [ ] `test_chat_without_session_returns_400`
- [ ] `test_chat_with_valid_session_succeeds`
- [ ] `test_chat_with_other_users_session_returns_403`
- [ ] `test_auto_title_set_after_first_reply`
- [ ] `test_get_messages_for_session`

### Frontend Unit Tests
- [ ] `ChatSidebar.test.tsx` — 8 test cases
- [ ] `SessionItem.test.tsx` — rename/delete behaviour
- [ ] `useSessions.test.ts` — 5 test cases

### E2E Tests (`e2e/sessions.spec.ts`)
- [ ] `new chat creates a session in the sidebar`
- [ ] `session gets auto-title after first message`
- [ ] `user can rename a session`
- [ ] `user can delete a session`
- [ ] `deleted session is no longer in sidebar`
- [ ] `switching sessions loads correct message history`
- [ ] `sessions from other users are not visible`

### Phase 2 Acceptance Criteria
- [ ] All unit tests pass with ≥ 80% coverage
- [ ] All E2E tests pass
- [ ] All GitHub Actions green
- [ ] PR description references all ✅ items above

---

## Phase 3 — Smart News Cache (`feature/smart-news-cache`)

### Infrastructure
- [ ] Add `redis`, `APScheduler` to `requirements.txt`
- [ ] Add Redis service to `docker-compose.yml` with memory cap + LRU policy
- [ ] Add `REDIS_URL` env var to `docker-compose.yml` and `.env-example`

### Database
- [ ] Write `migrations/003_news_cache.sql`
- [ ] Wire migration into `app.py` startup

### Backend — `cache/news.py`
- [ ] Redis client initialisation (with connection pool)
- [ ] `get_news(force: bool = False)` — day + hour cache merge algorithm
- [ ] `fetch_from_rss(since: datetime)` — filtered RSS fetch
- [ ] `promote_hour_to_day()` — APScheduler job
- [ ] `redis_get` / `redis_set` helpers with DB fallback
- [ ] `db_upsert` / `db_get` for `news_cache` table
- [ ] Article deduplication by `link` field
- [ ] Stable article ID: `sha256(link)[:12]`

### Backend — `app.py`
- [ ] Replace old `news.py` import with `cache/news.py`
- [ ] Register APScheduler at startup
- [ ] Add `?force=true` query param to `GET /news`
- [ ] Return `{articles, cache_hit, fetched_at}` shape

### Frontend
- [ ] Update `NewsArticle` type in `types/index.ts`
- [ ] Update `useNews.ts` — handle new response shape
- [ ] Update `NewsPanel.tsx` — source grouping, article timestamps, refresh button, "updated X min ago" badge

### Backend Unit Tests (`tests/unit/test_news.py`)
- [ ] `test_get_news_returns_articles`
- [ ] `test_hour_cache_hit_skips_rss_fetch`
- [ ] `test_day_cache_used_for_older_articles`
- [ ] `test_force_true_bypasses_hour_cache`
- [ ] `test_promote_hour_to_day_merges_correctly`
- [ ] `test_deduplication_by_link`
- [ ] `test_db_fallback_when_redis_unavailable`
- [ ] `test_empty_feed_returns_gracefully`
- [ ] `test_article_id_is_stable_hash_of_link`

### Frontend Unit Tests
- [ ] `NewsPanel.test.tsx` — 7 test cases (updated for new article shape)

### E2E Tests (`e2e/news.spec.ts`)
- [ ] `news panel loads on app open`
- [ ] `articles are grouped by source`
- [ ] `refresh button loads updated news`
- [ ] `news persists across page navigation within session`

### Phase 3 Acceptance Criteria
- [ ] All unit tests pass with ≥ 80% coverage
- [ ] All E2E tests pass
- [ ] All GitHub Actions green
- [ ] Redis data confirmed present via `redis-cli` smoke check in CI
- [ ] PR description references all ✅ items above

---

## Phase 4 — Knowledge Check (`feature/knowledge-check`)

### Database
- [ ] Write `migrations/004_mcq_attempts.sql`
- [ ] Wire migration into `app.py` startup

### Backend — `quiz.py`
- [ ] `POST /quiz/generate` — load chat, call LLM, validate, insert attempt, return questions (no `correct`)
- [ ] `GET /quiz/attempt/{id}` — return state; include `correct` only if `completed_at IS NOT NULL`
- [ ] `PUT /quiz/attempt/{id}` — upsert answers; if `completed: true`, score + set `completed_at`
- [ ] `POST /quiz/retry` — clone questions into new attempt row
- [ ] `GET /quiz/attempts` — list by `?session_id=`
- [ ] MCQ JSON validator (8 questions, 4 options, `correct` 0–3, text ≥ 15 chars)
- [ ] LLM retry on validation failure (1 retry, then 503)
- [ ] Ownership check on all endpoints (`user_id = g.user_id`)

### Frontend
- [ ] `src/api/quiz.ts` — all quiz API calls
- [ ] `src/hooks/useQuiz.ts` — load, select, debounced save, submit
- [ ] `src/components/MCQCard.tsx` — active + review modes
- [ ] `src/components/QuizResult.tsx` — score display after submit
- [ ] `src/pages/Quiz.tsx` — full quiz page
- [ ] Add `/quiz/:attemptId` route in `App.tsx`
- [ ] "Check Knowledge" button in `InputBar.tsx` or below MessageList
  - [ ] Shows only after ≥ 3 assistant messages
  - [ ] Loading state during generation
  - [ ] Opens new tab on success

### Backend Unit Tests (`tests/unit/test_quiz.py`)
- [ ] `test_generate_quiz_returns_8_questions`
- [ ] `test_generate_quiz_questions_have_no_correct_field`
- [ ] `test_generate_quiz_for_other_users_session_returns_403`
- [ ] `test_get_attempt_returns_saved_answers`
- [ ] `test_get_completed_attempt_includes_correct_field`
- [ ] `test_autosave_updates_answers`
- [ ] `test_submit_scores_correctly`
- [ ] `test_submit_sets_completed_at`
- [ ] `test_retry_creates_new_attempt_same_questions`
- [ ] `test_get_attempts_returns_history`
- [ ] `test_mcq_validation_rejects_less_than_8_questions`
- [ ] `test_ownership_check_on_put_attempt`

### Frontend Unit Tests
- [ ] `Quiz.test.tsx` — 8 test cases
- [ ] `MCQCard.test.tsx` — 6 test cases
- [ ] `useQuiz.test.ts` — 6 test cases

### E2E Tests (`e2e/quiz.spec.ts`)
- [ ] `check knowledge button appears after 3 AI replies`
- [ ] `clicking check knowledge opens quiz in new tab`
- [ ] `quiz loads with 8 questions`
- [ ] `selecting an answer saves it (visible on reload)`
- [ ] `submitting quiz shows score and highlights answers`
- [ ] `correct answer is green, wrong answer is red in review`
- [ ] `retry creates fresh attempt with same questions`
- [ ] `quiz page shows session title in header`

### Phase 4 Acceptance Criteria
- [ ] All unit tests pass with ≥ 80% coverage
- [ ] All E2E tests pass
- [ ] All GitHub Actions green
- [ ] MCQ quality verified: no name/date/location questions in generated output
- [ ] PR description references all ✅ items above

---

## Phase 5 — Polish & Hardening (`feature/polish`)

### Security
- [ ] Rate limit `/auth/login`: 5 req/min per IP
- [ ] Rate limit `/auth/register`: 3 req/min per IP
- [ ] Add `Content-Security-Policy` header in Flask `after_request`
- [ ] Verify no stack traces in production error responses
- [ ] Confirm `.env` in `.gitignore`

### UX & Responsiveness
- [ ] ChatSidebar → slide-in drawer on mobile (≤ lg)
- [ ] NewsPanel → bottom sheet on mobile
- [ ] Quiz page → single-column layout on mobile
- [ ] React ErrorBoundary around ChatSidebar, NewsPanel, Quiz
- [ ] Toast notifications: session renamed, deleted, quiz submitted, auto-save error

### Additional Unit Tests
- [ ] `tests/unit/test_rate_limiting.py` — 2 test cases

### E2E Tests (`e2e/full-flow.spec.ts`)
- [ ] `golden path: register → chat → receive auto-title → check knowledge → answer → submit → score`
- [ ] `returning user: login → see previous session → resume chat → retry quiz`
- [ ] `news panel loads and refreshes without breaking chat`
- [ ] `mobile: hamburger opens sidebar, session selected, sidebar closes`

### Phase 5 Acceptance Criteria
- [ ] All unit tests pass with ≥ 80% coverage
- [ ] All E2E tests pass (including full-flow)
- [ ] All GitHub Actions green on `feature/polish` PR
- [ ] Manual smoke test on mobile viewport (375px)
- [ ] All 5 phases merged to `main`

---

---

## Phase 6 — News Tabs, Discuss & Learning Tree (`feature/news-discuss-learn`)

### Infrastructure
- [ ] Add `programming` and `political` feed lists to `cache/news.py`
- [ ] Extend cache key format to include category (`news:day:{date}:{category}`)
- [ ] Update APScheduler `promote_hour_to_day()` to iterate all three categories
- [ ] Pre-warm all three categories at startup

### Database
- [ ] Write `migrations/005_session_hierarchy.sql` (session columns + MCQ columns)
- [ ] Wire migration into `app.py` startup

### Backend — `discuss.py`
- [ ] `POST /news/discuss` — create `news_discussion` session, call LLM, parse sectioned response
- [ ] Sectioned response validator (type, intro, sections[id/title/content/learn_more_topic], outro)
- [ ] LLM retry logic for invalid section format (1 retry then 503)
- [ ] `POST /sessions/{id}/learn-more` — create `learn_more` child, inherit root, increment depth
- [ ] `GET /sessions/{id}/tree` — walk `parent_session_id` chain, return ordered array

### Backend — Updated `quiz.py`
- [ ] `POST /quiz/generate-hierarchical` — gather ancestry, concatenate topics, generate spanning MCQs
- [ ] MCQ question schema extension: `topic` field, `source_depth` field
- [ ] `scope_sessions` stored on `mcq_attempts` row
- [ ] `GET /quiz/attempt/{id}/relearn/{question_id}` — lazy LLM explanation + cache in `relearn_cache`
- [ ] Route guard: regular sessions → flat MCQ; `learn_more`/`news_discussion` sessions → hierarchical

### Backend — Updated `sessions.py`
- [ ] `GET /sessions` returns: `session_type`, `parent_session_id`, `root_session_id`, `depth_level`, `topic`, `news_article_id`

### Frontend — News Panel
- [ ] `NewsTabs.tsx` — three-tab group with React Query keyed by category
- [ ] `NewsArticleCard.tsx` — title, summary, timestamp, Source link, Discuss button
- [ ] `useDiscuss.ts` — POST /news/discuss, set active session, render first_response
- [ ] Update `App.tsx` to use `NewsTabs` instead of `NewsPanel`

### Frontend — Sectioned Responses
- [ ] `SectionedMessage.tsx` — renders sectioned format with section cards and Learn More buttons
- [ ] `useLearnMore.ts` — POST /sessions/{id}/learn-more, open `/learn/:id` in new tab
- [ ] Per-button loading + disabled-after-click state in `SectionedMessage`
- [ ] Update `Message.tsx` to delegate to `SectionedMessage` for sectioned content

### Frontend — Learn Page (`/learn/:sessionId`)
- [ ] `LearnPage.tsx` — 3-pane layout: sidebar + chat + knowledge tree
- [ ] Add `/learn/:sessionId` route in `App.tsx`
- [ ] Right pane: `KnowledgeTree` instead of `NewsPanel`
- [ ] Centre pane: same `ChatInterface` but Check Knowledge calls hierarchical endpoint

### Frontend — Knowledge Tree
- [ ] `KnowledgeTree.tsx` — visual tree with connecting lines
- [ ] `TreeNode.tsx` — individual node (icon, label, current highlight)
- [ ] `useSessionTree.ts` — GET /sessions/{id}/tree React Query hook
- [ ] Back to root / back one level navigation buttons

### Frontend — ChatSidebar (nested)
- [ ] Build client-side tree from `GET /sessions` data (group by `parent_session_id`)
- [ ] Render `📰` for `news_discussion`, `⚡` for `learn_more`, no icon for `regular`
- [ ] Collapsible subtree on `news_discussion` nodes
- [ ] Indent `learn_more` nodes by `depth_level * 16px`

### Frontend — Enhanced Quiz Page
- [ ] `RelearPanel.tsx` — wrong-answer explanation card with Explore deeper button
- [ ] `useHierarchicalQuiz.ts` — generate-hierarchical, relearn fetch, correct → learn more
- [ ] After submit: wrong → show `RelearPanel` (lazy-load explanation)
- [ ] After submit: correct → show green badge + `[Explore deeper →]` button
- [ ] `[Explore deeper]` click → `useLearnMore(attempt.session_id, question.topic)`
- [ ] `[Check Knowledge]` button detects session type and calls correct endpoint

### Backend Unit Tests
- [ ] `tests/unit/test_discuss.py` — 12 test cases (see IMPLEMENTATION_PLAN.md §6 Backend)
- [ ] `tests/unit/test_news_categories.py` — 7 test cases
- [ ] `tests/unit/test_hierarchical_quiz.py` — 7 test cases

### Frontend Unit Tests
- [ ] `NewsTabs.test.tsx` — 3 test cases
- [ ] `NewsArticleCard.test.tsx` — 5 test cases
- [ ] `SectionedMessage.test.tsx` — 6 test cases
- [ ] `KnowledgeTree.test.tsx` — 6 test cases
- [ ] `RelearPanel.test.tsx` — 4 test cases
- [ ] `useDiscuss.test.ts` — 4 test cases
- [ ] `useLearnMore.test.ts` — 3 test cases
- [ ] `useSessionTree.test.ts` — 3 test cases
- [ ] `useHierarchicalQuiz.test.ts` — 4 test cases

### E2E Tests
- [ ] `e2e/discuss.spec.ts` — 7 test cases
- [ ] `e2e/learn-more.spec.ts` — 9 test cases
- [ ] `e2e/hierarchical-quiz.spec.ts` — 9 test cases

### Phase 6 Acceptance Criteria
- [ ] All unit tests pass with ≥ 80% coverage
- [ ] All E2E tests pass
- [ ] All GitHub Actions green
- [ ] News tabs verified: each category shows distinct sources
- [ ] Sectioned response verified: 3–5 sections generated, no personal/political opinion content
- [ ] Knowledge tree renders correctly at depth 3+ in a real browser
- [ ] Hierarchical MCQ covers multiple depth levels (check `source_depth` values spread across 0,1,2+)
- [ ] Relearn explanations cached: second load of same question does not trigger a new LLM call
- [ ] PR description references all ✅ items above

---

## Notes & Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-04 | Architecture document created | Baseline before implementation |
| 2026-05-04 | Implementation plan created | Defines all tasks, tests, branches |
| 2026-05-04 | Phase 6 added: News tabs (AI/Programming/Political), Discuss button, sectioned AI responses, Learn More sub-threads, knowledge tree, hierarchical MCQ with relearn | New product requirement |
| 2026-05-05 | Frontend rewritten from React/Vite/TypeScript SPA to Flask SSR (Jinja2 + HTMX + Alpine.js). Auth changed from JWT to Flask-Session + Redis. `frontend/` directory and its Dockerfile removed. Makefile added to replace package.json scripts. | VirtualBox shared folder (vboxsf) cannot create symlinks, breaking npm install. SSR eliminates all Node.js/npm toolchain requirements. Python-only stack is simpler to operate. |
| 2026-05-06 | Added enterprise architecture layers: `backend/domain/` (frozen dataclasses), `backend/repositories/` (all SQL encapsulated, returns domain objects), `backend/api/auth/schemas.py` (Pydantic v2 request validation). Service functions now call `user_repo` and return `User` domain objects. | Flask best practice for business-grade apps: clean separation of HTTP boundary (schemas), business logic (services), data access (repositories), and domain models. Prevents raw dicts leaking across layers and makes tests mock-friendly. |
| — | _(add as decisions are made during implementation)_ | — |
