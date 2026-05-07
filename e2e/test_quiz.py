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


class TestQuizGeneration:
    def test_check_knowledge_button_appears_with_active_session(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "Explain how transformers work in NLP")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        expect(page.locator('button:has-text("Check Knowledge")')).to_be_visible()

    def test_check_knowledge_opens_quiz_tab(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "Explain self-attention mechanism")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        # Click and wait for new tab
        with page.expect_popup(timeout=60_000) as popup_info:
            page.click('button:has-text("Check Knowledge")')
        quiz_page = popup_info.value
        quiz_page.wait_for_load_state("networkidle", timeout=60_000)
        assert "/quiz/" in quiz_page.url
        quiz_page.close()

    def test_quiz_page_shows_questions(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "Explain backpropagation and gradient descent")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        with page.expect_popup(timeout=90_000) as popup_info:
            page.click('button:has-text("Check Knowledge")')
        quiz_page = popup_info.value
        quiz_page.wait_for_selector("text=Knowledge Check", timeout=60_000)
        # Questions should be rendered
        assert quiz_page.locator("button").count() > 4  # at least 4 option buttons
        quiz_page.close()

    def test_quiz_submit_shows_score(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "What is the difference between RNN and LSTM?")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        with page.expect_popup(timeout=90_000) as popup_info:
            page.click('button:has-text("Check Knowledge")')
        quiz_page = popup_info.value
        quiz_page.wait_for_selector("text=Knowledge Check", timeout=60_000)
        # Click the first option of each question
        option_buttons = quiz_page.locator("button").filter(
            has_not_text="Submit Quiz"
        ).filter(has_not_text="Check Knowledge").filter(has_not_text="Back")
        count = option_buttons.count()
        # Select every 4th button (first option of each question)
        for i in range(0, min(count, 32), 4):
            try:
                option_buttons.nth(i).click()
                quiz_page.wait_for_timeout(200)
            except Exception:
                pass
        # Submit
        submit_btn = quiz_page.locator('button:has-text("Submit Quiz")')
        if submit_btn.is_visible():
            submit_btn.click()
            quiz_page.wait_for_selector("text=Retry", timeout=15_000)
            assert "Retry" in quiz_page.inner_text("body")
        quiz_page.close()


class TestQuizRetry:
    def test_quiz_retry_navigates_to_new_attempt(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_message_and_wait(page, "Tell me about BERT and GPT models")
        page.wait_for_selector('button:has-text("Check Knowledge")', timeout=5_000)
        with page.expect_popup(timeout=90_000) as popup_info:
            page.click('button:has-text("Check Knowledge")')
        quiz_page = popup_info.value
        quiz_page.wait_for_selector("text=Knowledge Check", timeout=60_000)
        original_url = quiz_page.url
        # Submit immediately (no answers selected)
        submit_btn = quiz_page.locator('button:has-text("Submit Quiz")')
        if submit_btn.is_visible() and not submit_btn.is_disabled():
            submit_btn.click()
            quiz_page.wait_for_selector("text=Retry", timeout=15_000)
            quiz_page.click('button:has-text("Retry")')
            quiz_page.wait_for_load_state("networkidle", timeout=10_000)
            # URL should change to new attempt
            assert quiz_page.url != original_url
            assert "/quiz/" in quiz_page.url
        quiz_page.close()
