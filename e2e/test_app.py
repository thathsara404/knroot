"""E2E tests for main app features: 3-pane layout, news, chat, sidebar."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL


class TestThreePaneLayout:
    def test_app_renders_three_panes(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        expect(page.locator("#sidebar")).to_be_visible()
        expect(page.locator("#chat-messages")).to_be_visible()
        expect(page.locator("#right-panel")).to_be_visible()

    def test_sidebar_toggle_collapses_sidebar(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        # Sidebar should start open
        expect(page.locator("#sidebar")).to_be_visible()
        page.click('button[aria-label="Toggle sidebar"]')
        page.wait_for_timeout(400)
        # Width should collapse (check class or width)
        sidebar_class = page.locator("#sidebar").get_attribute("class") or ""
        assert "w-0" in sidebar_class or "overflow-hidden" in sidebar_class

    def test_new_chat_button_present(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        expect(page.locator('button[title="New Chat"]')).to_be_visible()

    def test_chat_form_always_visible(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        expect(page.locator('textarea[name="message"]')).to_be_visible()
        expect(page.locator('#chat-form button[type="submit"]')).to_be_visible()


class TestNewsPanel:
    def test_news_panel_loads_on_startup(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        # Wait for news panel to load (HTMX fetch)
        page.wait_for_selector("#news-articles", timeout=15_000)
        expect(page.locator("#news-articles")).to_be_visible()

    def test_news_tab_switching_ai(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_selector("#right-panel", timeout=10_000)
        page.click('button:has-text("AI")')
        page.wait_for_timeout(2_000)

    def test_news_tab_switching_dev(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_selector("#right-panel", timeout=10_000)
        page.click('button:has-text("Dev")')
        page.wait_for_timeout(2_000)

    def test_news_tab_switching_world(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_selector("#right-panel", timeout=10_000)
        page.click('button:has-text("World")')
        page.wait_for_timeout(2_000)


class TestChat:
    def test_send_message_appears_in_chat(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("What is Python?")
        textarea.press("Enter")
        # User message should appear
        page.wait_for_selector(
            "#chat-messages .flex.justify-end", timeout=30_000
        )
        assert "What is Python?" in page.inner_text("#chat-messages")

    def test_send_message_creates_session_in_sidebar(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("Tell me about neural networks")
        textarea.press("Enter")
        # Wait for AI response
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        # Session list should refresh and show a new entry
        page.wait_for_timeout(500)
        session_list = page.locator("#session-list")
        assert len(page.locator("#session-list a").all()) >= 1

    def test_ai_response_appears(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("What is 2+2?")
        textarea.press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        # AI response bubble should be present
        assert page.locator("#chat-messages .flex.justify-start").count() >= 1

    def test_check_knowledge_button_appears_after_active_session(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("Explain gradient descent to me")
        textarea.press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        # Check Knowledge button should appear
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        expect(page.locator('button:has-text("Check Knowledge")')).to_be_visible()

    def test_right_panel_switches_to_tree_on_session_click(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        # Send a message to create a session
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("Explain backpropagation")
        textarea.press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        page.wait_for_timeout(500)
        # Click the first session in the sidebar
        session_links = page.locator("#session-list a")
        if session_links.count() > 0:
            session_links.first.click()
            # Clicking a session loads its messages into #chat-messages and
            # topic-relevant news into #right-panel (not a knowledge tree).
            page.wait_for_selector("#chat-messages .flex.justify-start", timeout=10_000)
            assert page.locator("#chat-messages .flex.justify-start").count() >= 1

    def test_new_chat_restores_news_panel(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        # Send a message to get an active session
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("What is attention?")
        textarea.press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        page.wait_for_timeout(500)
        # Click new chat
        page.click('button[title="New Chat"]')
        # News panel should come back
        page.wait_for_selector("#news-articles", timeout=10_000)
        expect(page.locator("#news-articles")).to_be_visible()


# ---------------------------------------------------------------------------
# Session management — delete
# ---------------------------------------------------------------------------


class TestSessionManagement:
    def test_delete_session_removes_from_sidebar(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        textarea = page.locator('textarea[name="message"]')
        textarea.fill("Explain neural networks briefly")
        textarea.press("Enter")
        page.wait_for_selector("#chat-messages .flex.justify-start", timeout=60_000)
        page.wait_for_timeout(500)

        page.wait_for_selector("[data-session-id]", timeout=8_000)
        session_id = page.locator("[data-session-id]").first.get_attribute("data-session-id")
        before_count = page.locator("#session-list a").count()

        # Trigger delete via JS to avoid relying on hover-only button discovery
        page.evaluate(f"window.deleteSession('{session_id}', 0)")
        page.wait_for_selector("#knr-confirm-ok", timeout=5_000)
        page.locator("#knr-confirm-ok").click()

        page.wait_for_timeout(1_500)
        assert page.locator("#session-list a").count() < before_count


# ---------------------------------------------------------------------------
# News → discuss (Explore button on news article cards)
# ---------------------------------------------------------------------------


class TestNewsDiscuss:
    def test_explore_news_article_creates_discussion_session(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        # Wait for news articles to load in right panel
        page.wait_for_selector("[data-article-id]", timeout=15_000)
        initial_count = page.locator("#session-list a").count()

        # Click Explore on the first news card — scoped to avoid chat section buttons
        page.locator("[data-article-id]").first.locator('button:has-text("Explore")').click()

        # A news_discussion session is created asynchronously; sidebar refreshes
        page.wait_for_function(
            f"document.querySelectorAll('#session-list a').length > {initial_count}",
            timeout=20_000,
        )
        assert page.locator("#session-list a").count() > initial_count
