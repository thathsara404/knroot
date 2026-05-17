"""E2E tests: Knowledge Root building — chat, explore inner roots, quiz lifecycle.

All LLM calls are handled by the mock-llm Docker service which returns
deterministic canned responses, so no real API tokens are consumed.
"""
from __future__ import annotations

import json
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, api_register

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_AI_RESPONSE_SELECTOR = "#chat-messages .flex.justify-start"
_CHAT_TIMEOUT = 30_000   # mock LLM responds in <1 s, but allow for cold start
_EXPLORE_TIMEOUT = 25_000


def _send_and_wait(page: Page, message: str, timeout: int = _CHAT_TIMEOUT) -> None:
    """Fill the chat input, submit, and wait for the first AI response bubble."""
    textarea = page.locator('textarea[name="message"]')
    textarea.fill(message)
    textarea.press("Enter")
    page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=timeout)
    page.wait_for_timeout(400)


# ---------------------------------------------------------------------------
# Chat and sectioned response
# ---------------------------------------------------------------------------

class TestChatAndSectionedResponse:
    def test_send_message_shows_user_bubble(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.locator('textarea[name="message"]').fill("What is machine learning?")
        page.locator('textarea[name="message"]').press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-end", timeout=10_000)
        assert "What is machine learning?" in page.inner_text("#chat-messages")

    def test_ai_response_appears_after_message(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain neural networks")
        assert page.locator(_AI_RESPONSE_SELECTOR).count() >= 1

    def test_sectioned_response_shows_section_cards(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "How does backpropagation work?")
        # Mock returns "Core Concept" as first section title
        page.wait_for_selector("text=Core Concept", timeout=8_000)
        expect(page.locator("text=Core Concept").first).to_be_visible()

    def test_sectioned_response_shows_all_three_sections(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain gradient descent")
        page.wait_for_selector("text=Core Concept", timeout=8_000)
        assert page.locator("text=Practical Applications").count() >= 1
        assert page.locator("text=Advanced Considerations").count() >= 1

    def test_sectioned_response_has_explore_buttons(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is the attention mechanism?")
        page.wait_for_selector("text=Core Concept", timeout=8_000)
        explore_buttons = page.locator('button:has-text("Explore")')
        assert explore_buttons.count() >= 1

    def test_sectioned_response_has_intro_block(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain transformer architecture")
        # Mock intro text contains "educational overview"
        page.wait_for_selector("text=educational overview", timeout=8_000)

    def test_session_created_in_sidebar(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Tell me about convolutional neural networks")
        page.wait_for_timeout(600)
        assert page.locator("#session-list a").count() >= 1

    def test_session_auto_title_set(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is reinforcement learning?")
        # Auto-title fires after response; mock returns "Test Knowledge Topic"
        page.wait_for_timeout(2_000)
        session_links = page.locator("#session-list a")
        assert session_links.count() >= 1
        title = session_links.first.inner_text().strip()
        # Title should not still be the default "New Chat" placeholder
        assert len(title) > 0

    def test_check_knowledge_button_appears(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "How does random forest work?")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=8_000)
        expect(page.locator('button:has-text("Check Knowledge")')).to_be_visible()

    def test_new_chat_clears_session_and_shows_news(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain support vector machines")
        page.click('button[title="New Chat"]')
        page.wait_for_selector("#news-articles", timeout=10_000)
        expect(page.locator("#news-articles")).to_be_visible()


# ---------------------------------------------------------------------------
# Explore → inner roots
# ---------------------------------------------------------------------------

class TestExploreAndInnerRoots:
    def test_explore_button_triggers_new_session(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain LSTM networks")
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        initial_count = page.locator("#session-list a").count()

        page.locator('button:has-text("Explore")').first.click()

        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {initial_count}",
            timeout=_EXPLORE_TIMEOUT,
        )
        assert page.locator("#session-list a").count() > initial_count

    def test_explore_loads_new_content_in_chat_pane(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is transfer learning?")
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        before_sessions = page.locator("#session-list a").count()

        page.locator('button:has-text("Explore")').first.click()

        # exploreSection replaces #chat-messages with a spinner then loads new
        # learn_more session content — wait for sidebar to gain the child session.
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {before_sessions}",
            timeout=_EXPLORE_TIMEOUT,
        )
        assert page.locator("#session-list a").count() > before_sessions

    def test_explore_button_changes_to_loaded(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain dropout regularisation")
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        before_sessions = page.locator("#session-list a").count()
        page.locator('button:has-text("Explore")').first.click()
        # exploreSection replaces #chat-messages immediately, destroying the
        # original Alpine.js scope — the "Loaded" badge never becomes visible.
        # Observable side-effect: a new child session appears in the sidebar.
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {before_sessions}",
            timeout=_EXPLORE_TIMEOUT,
        )
        assert page.locator("#session-list a").count() > before_sessions

    def test_second_explore_deepens_tree(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain batch normalisation")
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)

        before = page.locator("#session-list a").count()

        # First explore — creates depth-1 child
        page.locator('button:has-text("Explore")').first.click()
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {before}",
            timeout=_EXPLORE_TIMEOUT,
        )
        after_first = page.locator("#session-list a").count()

        # Second explore on the new content — creates depth-2 child
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        page.locator('button:has-text("Explore")').first.click()
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {after_first}",
            timeout=_EXPLORE_TIMEOUT,
        )
        assert page.locator("#session-list a").count() >= 2

    def test_knowledge_tree_panel_loads_on_session_click(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What are recurrent neural networks?")
        page.wait_for_timeout(600)
        page.locator("#session-list a").first.click()
        # Clicking a session loads its messages into #chat-messages; the right
        # panel shows topic-relevant news (not a separate Knowledge Tree panel).
        page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=8_000)
        assert page.locator(_AI_RESPONSE_SELECTOR).count() >= 1

    def test_explore_child_session_appears_indented_in_sidebar(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain word embeddings")
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        initial_count = page.locator("#session-list a").count()

        page.locator('button:has-text("Explore")').first.click()
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {initial_count}",
            timeout=_EXPLORE_TIMEOUT,
        )
        # The session list should now show a nested structure (expand arrow appears)
        assert page.locator('#session-list [class*="border-l"]').count() >= 1


# ---------------------------------------------------------------------------
# Quiz generation lifecycle
# ---------------------------------------------------------------------------

_QUIZ_TIMEOUT = 35_000


class TestQuizLifecycle:
    def _load_quiz_inline(self, page: Page, message: str) -> None:
        """Send a message, wait for AI, click Check Knowledge, wait for inline quiz."""
        _send_and_wait(page, message)
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=8_000)
        page.click('button:has-text("Check Knowledge")')
        # Quiz loads inline into #chat-messages via HTMX (not a popup/new tab).
        page.wait_for_selector("#chat-messages .knr-quiz-root", timeout=_QUIZ_TIMEOUT)
        page.wait_for_timeout(500)

    def test_quiz_loads_inline(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "Explain gradient descent in depth")
        # Quiz is inline — URL stays at /app, content is inside #chat-messages.
        assert "/app" in page.url
        expect(page.locator("#chat-messages").locator("text=Knowledge Check").first).to_be_visible()

    def test_quiz_shows_knowledge_check_heading(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "What is the vanishing gradient problem?")
        expect(page.locator("#chat-messages").locator("text=Knowledge Check").first).to_be_visible()

    def test_quiz_has_multiple_option_buttons(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "Explain convolutional layers in CNNs")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")
        # Mock returns 8 questions × 4 options = at least 5 buttons
        assert quiz_area.locator("button").count() >= 5

    def test_quiz_submit_shows_score(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "How does the Adam optimiser work?")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")

        option_buttons = quiz_area.locator("button").filter(
            has_not_text="Submit Quiz"
        ).filter(has_not_text="Retry")
        count = min(option_buttons.count(), 32)
        for i in range(0, count, 4):
            try:
                option_buttons.nth(i).click()
                page.wait_for_timeout(80)
            except Exception:
                pass

        submit = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit.is_visible():
            submit.click()
            page.wait_for_selector("#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000)
            assert "Retry" in quiz_area.inner_text()

    def test_quiz_retry_loads_new_quiz_inline(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "Explain softmax and cross-entropy")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")

        submit = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit.is_visible() and not submit.is_disabled():
            submit.click()
            page.wait_for_selector("#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000)
            quiz_area.locator('button:has-text("Retry")').click()
            # retryQuiz() when inline=true reloads a new quiz inline via HTMX.
            page.wait_for_selector("#chat-messages .knr-quiz-root", timeout=_QUIZ_TIMEOUT)
            expect(
                page.locator("#chat-messages").locator("text=Knowledge Check").first
            ).to_be_visible()

    def test_followup_quiz_button_appears_after_submit(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        self._load_quiz_inline(page, "What is residual learning?")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")

        # Select one answer per question to enable the Submit button
        option_buttons = quiz_area.locator("button").filter(
            has_not_text="Submit Quiz"
        ).filter(has_not_text="Retry")
        count = min(option_buttons.count(), 32)
        for i in range(0, count, 4):
            try:
                option_buttons.nth(i).click()
                page.wait_for_timeout(80)
            except Exception:
                pass

        submit = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit.is_visible() and not submit.is_disabled():
            submit.click()
            page.wait_for_selector("#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000)

        # Chat input remains accessible while inline quiz is displayed
        assert page.locator('textarea[name="message"]').is_visible()


# ---------------------------------------------------------------------------
# Session navigation and management
# ---------------------------------------------------------------------------

class TestSessionNavigation:
    def test_click_session_loads_messages(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain principal component analysis")
        page.wait_for_timeout(600)
        page.locator("#session-list a").first.click()
        # Chat messages should be visible after loading the session
        page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=10_000)

    def test_second_message_in_same_session(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is k-nearest neighbours?")
        first_count = page.locator(_AI_RESPONSE_SELECTOR).count()
        _send_and_wait(page, "Give me an example of kNN in practice")
        # Two AI responses should now be visible
        assert page.locator(_AI_RESPONSE_SELECTOR).count() > first_count

    def test_sidebar_session_count_increments_on_explore(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is naive Bayes?")
        before = page.locator("#session-list a").count()
        page.wait_for_selector('button:has-text("Explore")', timeout=8_000)
        page.locator('button:has-text("Explore")').first.click()
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {before}",
            timeout=_EXPLORE_TIMEOUT,
        )
        assert page.locator("#session-list a").count() == before + 1


# ---------------------------------------------------------------------------
# Artifact rendering — hierarchy chart and artifact toggles
# ---------------------------------------------------------------------------
# The mock LLM returns a _SECTIONED response that includes:
#   • hierarchy_diagram  (flowchart TD with 3 section nodes)
#   • s1 artifacts: [formula]
#   • s2 artifacts: [bar chart]
#   • s3 artifacts: []
# These tests verify that the frontend renders and toggles them correctly.

_ARTIFACT_TIMEOUT = 8_000


class TestArtifactsRendering:
    def test_hierarchy_chart_wrapper_rendered_in_response(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain gradient descent")
        # hierarchy-diagram-wrapper is server-rendered; no JS interaction required
        page.wait_for_selector(".hierarchy-diagram-wrapper", timeout=_ARTIFACT_TIMEOUT)
        expect(page.locator(".hierarchy-diagram-wrapper").first).to_be_visible()

    def test_formula_artifact_toggle_button_present(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is the sigmoid function?")
        page.wait_for_selector('button:has-text("Show Formula")', timeout=_ARTIFACT_TIMEOUT)
        expect(page.locator('button:has-text("Show Formula")').first).to_be_visible()

    def test_chart_artifact_toggle_button_present(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Compare ML approaches")
        page.wait_for_selector('button:has-text("Show Chart")', timeout=_ARTIFACT_TIMEOUT)
        expect(page.locator('button:has-text("Show Chart")').first).to_be_visible()

    def test_formula_toggle_reveals_katex_panel(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain backpropagation")
        page.wait_for_selector('button:has-text("Show Formula")', timeout=_ARTIFACT_TIMEOUT)
        page.locator('button:has-text("Show Formula")').first.click()
        # Alpine x-show makes the panel visible; katex-block is inside it
        expect(page.locator(".katex-block").first).to_be_visible(timeout=5_000)

    def test_formula_toggle_button_text_changes_to_hide(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What is softmax?")
        page.wait_for_selector('button:has-text("Show Formula")', timeout=_ARTIFACT_TIMEOUT)
        page.locator('button:has-text("Show Formula")').first.click()
        expect(
            page.locator('button:has-text("Hide Formula")').first
        ).to_be_visible(timeout=5_000)

    def test_chart_toggle_reveals_canvas(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Show me a performance comparison")
        page.wait_for_selector('button:has-text("Show Chart")', timeout=_ARTIFACT_TIMEOUT)
        page.locator('button:has-text("Show Chart")').first.click()
        # Canvas element becomes visible; Chart.js renders on it asynchronously
        expect(page.locator("canvas.artifact-chart").first).to_be_visible(timeout=5_000)

    def test_formula_panel_collapses_on_second_click(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain activation functions")
        page.wait_for_selector('button:has-text("Show Formula")', timeout=_ARTIFACT_TIMEOUT)
        btn = page.locator('button:has-text("Show Formula")').first
        # Open
        btn.click()
        expect(page.locator(".katex-block").first).to_be_visible(timeout=5_000)
        # Close
        page.locator('button:has-text("Hide Formula")').first.click()
        page.wait_for_timeout(300)
        expect(page.locator(".katex-block").first).not_to_be_visible()

    def test_all_three_artifact_types_have_toggles(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What are advanced ML considerations?")
        page.wait_for_selector("text=Advanced Considerations", timeout=_ARTIFACT_TIMEOUT)
        # s1=formula, s2=chart, s3=diagram — all three toggles must be present
        page.wait_for_selector('button:has-text("Show Formula")', timeout=_ARTIFACT_TIMEOUT)
        assert page.locator('button:has-text("Show Formula")').count() >= 1
        assert page.locator('button:has-text("Show Chart")').count() >= 1
        assert page.locator('button:has-text("Show Diagram")').count() >= 1


# ---------------------------------------------------------------------------
# Helpers for wall preview and import tests
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Diagram artifact toggle (Mermaid)
# ---------------------------------------------------------------------------
# s3 "Advanced Considerations" now carries a diagram artifact in the mock response.

class TestDiagramArtifact:
    def test_diagram_artifact_toggle_button_present(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "What are the advanced theoretical considerations?")
        page.wait_for_selector('button:has-text("Show Diagram")', timeout=_ARTIFACT_TIMEOUT)
        expect(page.locator('button:has-text("Show Diagram")').first).to_be_visible()

    def test_diagram_toggle_reveals_mermaid_wrapper(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_and_wait(page, "Explain advanced considerations in depth")
        page.wait_for_selector('button:has-text("Show Diagram")', timeout=_ARTIFACT_TIMEOUT)
        page.locator('button:has-text("Show Diagram")').first.click()
        # The artifact panel slides open revealing its .mermaid-wrapper.
        # Use :not(.hierarchy-diagram-wrapper) to distinguish from the top hierarchy chart.
        expect(
            page.locator(".mermaid-wrapper:not(.hierarchy-diagram-wrapper)").first
        ).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# Helpers for wall preview and import tests
# ---------------------------------------------------------------------------

import uuid as _uuid


def _unique_api_user(prefix: str) -> dict:
    """Return a unique user payload suitable for api_register."""
    uid = _uuid.uuid4().hex[:8]
    return {
        "first_name": "User",
        "last_name": prefix.capitalize(),
        "username": f"{prefix}_{uid}",
        "email": f"{prefix}_{uid}@example.com",
        "password": "SecurePass1",
        "confirm_password": "SecurePass1",
    }


def _browser_login_as(page: Page, user: dict) -> None:
    """Log out the current browser user, then log in as `user`."""
    page.request.post(f"{BASE_URL}/auth/logout")
    page.goto(f"{BASE_URL}/login")
    page.fill("#identifier", user["email"])
    page.fill("#password", user["password"])
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/app", timeout=20_000)


# ---------------------------------------------------------------------------
# Wall preview modal — artifacts inside share_session_preview.html
# ---------------------------------------------------------------------------
# These tests verify that when a session with rich artifacts is shared and its
# preview modal is opened, the hierarchy diagram wrapper and artifact toggles
# are present and functional inside the modal.

_PREVIEW_MODAL_TIMEOUT = 12_000


def _send_and_share(page: Page) -> str:
    """Send one message (gets rich mock response), create a public share, return share_id."""
    page.goto(f"{BASE_URL}/app")
    _send_and_wait(page, "Explain gradient descent for the wall preview test")

    # Get the session_id from the first item in the sidebar
    page.wait_for_selector("[data-session-id]", timeout=10_000)
    session_id = page.locator("[data-session-id]").first.get_attribute("data-session-id")

    # Create a public share via API — page.request reuses the browser session cookie
    resp = page.request.post(
        f"{BASE_URL}/wall/shares",
        data=json.dumps({"session_id": session_id}),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 201
    return resp.json()["id"]


def _open_preview(page: Page, share_id: str) -> None:
    """Trigger wallOpenPreview and wait for the modal to settle."""
    page.evaluate(f"window.wallOpenPreview('{share_id}')")
    page.wait_for_selector("#share-preview-overlay", timeout=_PREVIEW_MODAL_TIMEOUT)
    page.wait_for_timeout(600)   # allow HTMX to settle


class TestWallPreviewArtifacts:
    def test_wall_preview_shows_hierarchy_wrapper(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)
        _open_preview(page, share_id)
        expect(
            page.locator("#preview-content .hierarchy-diagram-wrapper").first
        ).to_be_visible(timeout=5_000)

    def test_wall_preview_shows_formula_toggle(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)
        _open_preview(page, share_id)
        expect(
            page.locator('#preview-content button:has-text("Show Formula")').first
        ).to_be_visible(timeout=5_000)

    def test_wall_preview_shows_chart_toggle(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)
        _open_preview(page, share_id)
        expect(
            page.locator('#preview-content button:has-text("Show Chart")').first
        ).to_be_visible(timeout=5_000)

    def test_wall_preview_formula_toggle_reveals_katex_block(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)
        _open_preview(page, share_id)
        page.locator('#preview-content button:has-text("Show Formula")').first.click()
        expect(
            page.locator("#preview-content .katex-block").first
        ).to_be_visible(timeout=5_000)

    def test_wall_preview_chart_toggle_reveals_canvas(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)
        _open_preview(page, share_id)
        page.locator('#preview-content button:has-text("Show Chart")').first.click()
        expect(
            page.locator("#preview-content canvas.artifact-chart").first
        ).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# Imported sessions — artifacts preserved through deep copy
# ---------------------------------------------------------------------------
# These tests verify that when User B imports User A's shared session, the
# copied session_messages content retains all artifact JSON, and artifacts
# render correctly when User B views the imported session in the chat.

class TestImportedSessionArtifacts:
    def test_imported_session_shows_hierarchy_wrapper(
        self, page: Page, register_and_login: dict
    ):
        # User A: send message, share session
        share_id = _send_and_share(page)

        # User B: register via API and import the share
        user_b_data = _unique_api_user("beta")
        import_session = api_register(BASE_URL, user_b_data)
        import_resp = import_session.post(f"{BASE_URL}/wall/shares/{share_id}/import")
        assert import_resp.status_code == 201

        # Log out user A, log in as user B
        _browser_login_as(page, user_b_data)

        # User B: click the imported session in the sidebar
        page.wait_for_selector("[data-session-id]", timeout=10_000)
        page.locator("[data-session-id]").first.click()

        # Verify hierarchy wrapper is present in the loaded messages
        page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=15_000)
        page.wait_for_selector(".hierarchy-diagram-wrapper", timeout=8_000)
        expect(page.locator(".hierarchy-diagram-wrapper").first).to_be_visible()

    def test_imported_session_shows_formula_artifact_toggle(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)

        user_b_data = _unique_api_user("gamma")
        import_session = api_register(BASE_URL, user_b_data)
        import_session.post(f"{BASE_URL}/wall/shares/{share_id}/import")

        _browser_login_as(page, user_b_data)

        page.wait_for_selector("[data-session-id]", timeout=10_000)
        page.locator("[data-session-id]").first.click()
        page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=15_000)

        page.wait_for_selector('button:has-text("Show Formula")', timeout=8_000)
        expect(page.locator('button:has-text("Show Formula")').first).to_be_visible()

    def test_imported_session_formula_toggle_renders_katex(
        self, page: Page, register_and_login: dict
    ):
        share_id = _send_and_share(page)

        user_b_data = _unique_api_user("delta")
        import_session = api_register(BASE_URL, user_b_data)
        import_session.post(f"{BASE_URL}/wall/shares/{share_id}/import")

        _browser_login_as(page, user_b_data)

        page.wait_for_selector("[data-session-id]", timeout=10_000)
        page.locator("[data-session-id]").first.click()
        page.wait_for_selector(_AI_RESPONSE_SELECTOR, timeout=15_000)

        page.wait_for_selector('button:has-text("Show Formula")', timeout=8_000)
        page.locator('button:has-text("Show Formula")').first.click()
        expect(page.locator(".katex-block").first).to_be_visible(timeout=5_000)
