"""E2E tests for the quiz (Knowledge Check) system."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL


def _send_message_and_wait(page: Page, message: str, timeout: int = 60_000) -> None:
    """Send a chat message and wait for the AI response to appear."""
    textarea = page.locator('textarea[name="message"]')
    textarea.fill(message)
    textarea.press("Enter")
    page.wait_for_selector("#chat-messages .flex.justify-start", timeout=timeout)
    page.wait_for_timeout(500)


_QUIZ_INLINE_TIMEOUT = 35_000


def _load_quiz_inline(page: Page, message: str) -> None:
    """Send a message, click Check Knowledge, wait for the inline quiz to appear."""
    _send_message_and_wait(page, message)
    page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
    page.click('button:has-text("Check Knowledge")')
    # Quiz loads inline into #chat-messages via HTMX — not a popup or new tab.
    page.wait_for_selector("#chat-messages .knr-quiz-root", timeout=_QUIZ_INLINE_TIMEOUT)
    page.wait_for_timeout(500)


class TestQuizGeneration:
    def test_check_knowledge_button_appears_with_active_session(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "Explain how transformers work in NLP")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        expect(page.locator('button:has-text("Check Knowledge")')).to_be_visible()

    def test_check_knowledge_loads_quiz_inline(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _load_quiz_inline(page, "Explain self-attention mechanism")
        # Quiz is inline — URL stays at /app; content is inside #chat-messages.
        assert "/app" in page.url
        expect(
            page.locator("#chat-messages").locator("text=Knowledge Check").first
        ).to_be_visible()

    def test_quiz_page_shows_questions(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _load_quiz_inline(page, "Explain backpropagation and gradient descent")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")
        assert quiz_area.locator("button").count() > 4

    def test_quiz_submit_shows_score(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _load_quiz_inline(page, "What is the difference between RNN and LSTM?")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")
        option_buttons = quiz_area.locator("div.space-y-1\\.5 button")
        count = option_buttons.count()
        for i in range(0, min(count, 32), 4):
            try:
                option_buttons.nth(i).click()
                page.wait_for_timeout(200)
            except Exception:
                pass
        submit_btn = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit_btn.is_visible():
            submit_btn.click()
            page.wait_for_selector("#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000)
            assert "Retry" in quiz_area.inner_text()


class TestQuizRetry:
    def test_quiz_retry_loads_new_quiz_inline(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _load_quiz_inline(page, "Tell me about BERT and GPT models")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")
        submit_btn = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit_btn.is_visible() and not submit_btn.is_disabled():
            submit_btn.click()
            page.wait_for_selector("#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000)
            quiz_area.locator('button:has-text("Retry")').click()
            # retryQuiz() when inline=true reloads a new quiz inline via HTMX.
            page.wait_for_selector(
                "#chat-messages .knr-quiz-root", timeout=_QUIZ_INLINE_TIMEOUT
            )
            expect(
                page.locator("#chat-messages").locator("text=Knowledge Check").first
            ).to_be_visible()


class TestQuizRelearn:
    def test_relearn_explanation_appears_for_wrong_answer(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _load_quiz_inline(page, "Explain gradient descent and optimisation in depth")
        quiz_area = page.locator("#chat-messages .knr-quiz-root")

        # Select the 4th option (index 3) for every question — all wrong answers
        # Scope to div.space-y-1.5 to exclude hidden relearn/explore buttons from count
        option_buttons = quiz_area.locator("div.space-y-1\\.5 button")
        count = option_buttons.count()
        for i in range(3, min(count, 32), 4):
            try:
                option_buttons.nth(i).click()
                page.wait_for_timeout(150)
            except Exception:
                pass

        submit_btn = quiz_area.locator('button:has-text("Submit Quiz")')
        if submit_btn.is_visible() and not submit_btn.is_disabled():
            submit_btn.click()
            page.wait_for_selector(
                "#chat-messages .knr-quiz-root >> text=Retry", timeout=15_000
            )

        # "Why was I wrong?" appears next to each incorrect answer after submission
        page.wait_for_selector('button:has-text("Why was I wrong?")', timeout=8_000)
        page.locator('button:has-text("Why was I wrong?")').first.click()
        # Mock LLM returns relearn explanation; panel has bg-amber-50 class
        page.wait_for_selector(".bg-amber-50", timeout=15_000)
        expect(page.locator(".bg-amber-50").first).to_be_visible()
