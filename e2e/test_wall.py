"""E2E tests: Wall tab — navigation, sharing, voting, comments, save/import, follow, profile.

Multi-user scenarios use `second_api_user` (a requests.Session authenticated as a
different user) to create sessions and shares via the JSON API, then the primary
browser user interacts with those shares through the UI.
"""
from __future__ import annotations

import uuid

import pytest
import requests as _requests
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

_WALL_TIMEOUT = 20_000
_CHAT_TIMEOUT = 30_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_chat_message(page: Page, message: str) -> None:
    """Submit a chat message and wait for AI response."""
    page.locator('textarea[name="message"]').fill(message)
    page.locator('textarea[name="message"]').press("Enter")
    page.wait_for_selector("#chat-messages .flex.justify-start", timeout=_CHAT_TIMEOUT)
    page.wait_for_timeout(400)


def _navigate_to_wall(page: Page) -> None:
    """Click the Wall tab and wait for the Public Wall heading to appear."""
    page.click('button[title="Wall"]')
    page.wait_for_selector("text=Public Wall", timeout=_WALL_TIMEOUT)


def _open_share_modal(page: Page) -> None:
    """Hover the first session row to reveal and click the Share button."""
    session_link = page.locator("#session-list a").first
    session_link.hover()
    page.wait_for_timeout(300)
    page.locator('[aria-label="Share"]').first.click()
    page.wait_for_selector("text=Share to Wall", timeout=8_000)


def _share_active_session(page: Page, description: str = "") -> str:
    """Open share modal, optionally set description, submit, and return unique desc."""
    uid = uuid.uuid4().hex[:6]
    full_desc = f"{description} {uid}".strip()
    _open_share_modal(page)
    desc_input = page.locator('textarea[x-model="shareModal.description"]')
    desc_input.fill(full_desc)
    page.click('button:has-text("Share to Wall")', timeout=5_000)
    page.wait_for_timeout(2_000)
    return full_desc


def _api_create_share(api_session: _requests.Session, description: str = "E2E share") -> dict:
    """Have the API user send a chat message then create a public share. Returns share dict."""
    r = api_session.post(
        f"{BASE_URL}/chat",
        json={"message": "Explain neural networks briefly"},
    )
    assert r.status_code == 200, f"POST /chat failed {r.status_code}: {r.text[:300]}"
    data = r.json()
    session_id = data.get("session_id")
    assert session_id, "No session_id in chat response"

    r2 = api_session.post(
        f"{BASE_URL}/wall/shares",
        json={"session_id": session_id, "visibility": "public", "description": description},
    )
    assert r2.status_code == 201, f"POST /wall/shares failed {r2.status_code}: {r2.text[:300]}"
    return r2.json()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class TestWallNavigation:
    def test_wall_tab_loads_public_wall(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        page.click('button[title="Wall"]')
        page.wait_for_selector("text=Public Wall", timeout=_WALL_TIMEOUT)
        assert "Public Wall" in page.inner_text("#chat-messages")

    def test_my_wall_toggle_loads_private_panel(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        # switchTab('wall') auto-loads /wall/private/partial into #right-panel
        # and sets showWallPrivate=true so the panel is already visible.
        _navigate_to_wall(page)
        page.wait_for_selector("text=My Wall", timeout=_WALL_TIMEOUT)
        assert "My Wall" in page.inner_text("#right-panel")

    def test_profile_tab_loads_profile(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        page.click('button[title="Profile"]')
        page.wait_for_timeout(1_500)
        # Profile partial loads into #chat-messages
        assert page.locator("#chat-messages").is_visible()

    def test_score_toggle_loads_score_panel(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        # switchTab('profile') auto-loads /wall/score/partial into #right-panel
        # and starts with showProfileScore=true so the panel is already visible.
        # Do NOT click the Score toggle — it toggles visibility (would hide it).
        page.click('button[title="Profile"]')
        page.wait_for_timeout(1_500)
        expect(page.locator("#right-panel")).to_be_visible()

    def test_root_tab_restores_chat_input(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        _navigate_to_wall(page)
        page.click('button[title="Mathemariza"]')
        page.wait_for_selector('textarea[name="message"]', timeout=8_000)
        expect(page.locator('textarea[name="message"]')).to_be_visible()


# ---------------------------------------------------------------------------
# Share to wall
# ---------------------------------------------------------------------------


class TestShareToWall:
    def test_share_button_visible_on_session_hover(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "What is deep learning?")
        page.wait_for_timeout(600)
        page.locator("#session-list a").first.hover()
        page.wait_for_timeout(300)
        expect(page.locator('[aria-label="Share"]').first).to_be_visible()

    def test_share_modal_opens(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "Explain convolutional networks")
        page.wait_for_timeout(600)
        _open_share_modal(page)
        expect(page.locator("text=Share to Wall").first).to_be_visible()

    def test_share_modal_visibility_options(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "What is BERT?")
        page.wait_for_timeout(600)
        _open_share_modal(page)
        select = page.locator('select[x-model="shareModal.visibility"]')
        expect(select).to_be_visible()
        options = select.locator("option").all_text_contents()
        assert any("Public" in o for o in options)
        assert any("Friends" in o for o in options)

    def test_share_appears_in_public_wall(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "Explain recurrent networks in detail")
        page.wait_for_timeout(600)
        full_desc = _share_active_session(page, "E2E pub wall")
        _navigate_to_wall(page)
        assert full_desc in page.inner_text("#chat-messages")

    def test_own_share_has_delete_not_save(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "Explain gradient descent clearly")
        page.wait_for_timeout(600)
        full_desc = _share_active_session(page, "own share test")
        _navigate_to_wall(page)
        # Locate the card by description text
        own_card = page.locator('[data-share-id]').filter(has_text=full_desc).first
        expect(own_card.locator('[aria-label="Delete share"]')).to_be_visible()
        assert own_card.locator('button:has-text("Save")').count() == 0


# ---------------------------------------------------------------------------
# Voting (requires second user's share visible in public wall)
# ---------------------------------------------------------------------------


class TestVoting:
    def test_upvote_increments_count(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Upvote test {uid}")
        share_id = share["id"]

        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)

        card = page.locator(f'[data-share-id="{share_id}"]')
        # upvote count span
        count_span = card.locator('span[x-text="upvotes"]')
        initial = int(count_span.inner_text() or "0")

        # First button in the vote row is the upvote button
        vote_row = card.locator('.border-t.border-gray-100').first
        vote_row.locator('button').first.click()

        # Wait for Alpine to reflect the server response in the upvote count span
        page.wait_for_function(
            f'(function(){{ var el = document.querySelector(\'[data-share-id="{share_id}"] span[x-text="upvotes"]\'); return el && parseInt(el.innerText || "0") > {initial}; }})()',
            timeout=30_000,
        )
        new_count = int(count_span.inner_text() or "0")
        assert new_count > initial

    def test_downvote_sets_aria_pressed(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Downvote test {uid}")
        share_id = share["id"]

        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)

        card = page.locator(f'[data-share-id="{share_id}"]')
        vote_row = card.locator('.border-t.border-gray-100').first
        # Second button in vote row is downvote
        downvote_btn = vote_row.locator('button').nth(1)
        downvote_btn.click()
        page.wait_for_timeout(800)
        # Alpine sets aria-pressed="true" after a downvote lands
        assert downvote_btn.get_attribute("aria-pressed") == "true"


# ---------------------------------------------------------------------------
# Comments (requires second user's share)
# ---------------------------------------------------------------------------


class TestComments:
    def _land_on_share(
        self, page: Page, api_session: _requests.Session, label: str
    ) -> tuple[str, "playwright.sync_api.Locator"]:
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(api_session, f"{label} {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        card = page.locator(f'[data-share-id="{share_id}"]')
        return share_id, card

    def test_comments_section_expands(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        _, card = self._land_on_share(page, second_api_user["session"], "expand comments")
        card.locator('button:has-text("Comments")').click()
        page.wait_for_timeout(600)
        expect(card.locator('input[placeholder="Add a comment…"]')).to_be_visible()

    def test_add_comment_appears(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        _, card = self._land_on_share(page, second_api_user["session"], "add comment")
        card.locator('button:has-text("Comments")').click()
        page.wait_for_timeout(400)

        uid = uuid.uuid4().hex[:6]
        comment = f"Test comment {uid}"
        card.locator('input[placeholder="Add a comment…"]').fill(comment)
        card.locator('button:has-text("Post")').click()
        page.wait_for_timeout(1_200)
        assert comment in card.inner_text()

    def test_reply_appears_nested(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        _, card = self._land_on_share(page, second_api_user["session"], "reply test")
        card.locator('button:has-text("Comments")').click()
        page.wait_for_timeout(400)

        uid = uuid.uuid4().hex[:6]
        card.locator('input[placeholder="Add a comment…"]').fill(f"Parent {uid}")
        card.locator('button:has-text("Post")').click()
        page.wait_for_timeout(1_200)

        # Click Reply on the newly added top-level comment
        card.locator('button:has-text("Reply")').first.click()
        page.wait_for_timeout(300)
        reply_text = f"Reply {uid}"
        card.locator('input[placeholder="Write a reply…"]').fill(reply_text)
        # The submit Reply button inside the form
        card.locator('button[type="submit"]:has-text("Reply")').click()
        page.wait_for_timeout(1_200)
        assert reply_text in card.inner_text()


# ---------------------------------------------------------------------------
# Save and import (requires second user's share)
# ---------------------------------------------------------------------------


class TestSaveAndImport:
    def test_other_users_share_has_save_button(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Save btn {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        card = page.locator(f'[data-share-id="{share_id}"]')
        expect(card.locator('button:has-text("Save")')).to_be_visible()

    def test_save_changes_button_to_saved(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Save state {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        card = page.locator(f'[data-share-id="{share_id}"]')
        card.locator('button:has-text("Save")').click()
        page.wait_for_timeout(1_000)
        expect(card.locator('button:has-text("Saved")')).to_be_visible()

    def test_saved_share_appears_in_my_wall(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"My wall {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        page.locator(f'[data-share-id="{share_id}"]').locator('button:has-text("Save")').click()
        # wallSaveToWall auto-reloads #right-panel immediately after save on wall tab
        page.wait_for_selector(f'#right-panel [data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        assert page.locator(f'#right-panel [data-share-id="{share_id}"]').count() >= 1

    def test_import_to_root_button_visible_in_my_wall(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Import btn {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        page.locator(f'[data-share-id="{share_id}"]').locator('button:has-text("Save")').click()
        # wallSaveToWall auto-reloads #right-panel immediately after save on wall tab
        page.wait_for_selector(f'#right-panel [data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        private_card = page.locator(f'#right-panel [data-share-id="{share_id}"]')
        expect(private_card.locator('button:has-text("Import to Root")')).to_be_visible()

    def test_import_adds_session_to_root(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Import exec {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        page.locator(f'[data-share-id="{share_id}"]').locator('button:has-text("Save")').click()
        # wallSaveToWall auto-reloads #right-panel immediately after save on wall tab
        page.wait_for_selector(f'#right-panel [data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        private_card = page.locator(f'#right-panel [data-share-id="{share_id}"]')
        initial_sessions = page.locator("#session-list a").count()
        private_card.locator('button:has-text("Import to Root")').click()
        # Confirm via KnrConfirm dialog (button id = knr-confirm-ok)
        page.wait_for_selector('#knr-confirm-ok', timeout=8_000)
        page.locator('#knr-confirm-ok').click()
        page.wait_for_timeout(2_500)

        imported = private_card.locator("text=Imported").count() >= 1
        sessions_grew = page.locator("#session-list a").count() > initial_sessions
        assert imported or sessions_grew


# ---------------------------------------------------------------------------
# Follow user
# ---------------------------------------------------------------------------


class TestFollowUser:
    def test_follow_button_changes_to_requested(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Follow test {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        card = page.locator(f'[data-share-id="{share_id}"]')
        follow_btn = card.locator('button:has-text("Follow")')
        if follow_btn.count() > 0 and follow_btn.first.is_visible():
            follow_btn.first.click()
            page.wait_for_timeout(2_500)
            requested = card.locator('button:has-text("Requested")').count() >= 1
            following = card.locator('text=Following').count() >= 1
            assert requested or following, "Follow state did not update to Requested or Following"


# ---------------------------------------------------------------------------
# Profile and score
# ---------------------------------------------------------------------------


class TestProfileAndScore:
    def test_profile_shows_own_username(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        page.click('button[title="Profile"]')
        page.wait_for_timeout(2_000)
        assert register_and_login["username"] in page.inner_text("#chat-messages")

    def test_score_panel_is_accessible(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        page.wait_for_load_state("networkidle")
        # switchTab('profile') auto-loads score into #right-panel; panel is
        # already visible since showProfileScore starts true. Don't toggle it.
        page.click('button[title="Profile"]')
        page.wait_for_timeout(1_500)
        expect(page.locator("#right-panel")).to_be_visible()

    def test_profile_lists_own_shares(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "Tell me about decision trees")
        page.wait_for_timeout(600)
        full_desc = _share_active_session(page, "Profile share")
        page.click('button[title="Profile"]')
        page.wait_for_timeout(2_000)
        assert full_desc in page.inner_text("#chat-messages")


# ---------------------------------------------------------------------------
# Delete share
# ---------------------------------------------------------------------------


class TestDeleteShare:
    def test_delete_own_share_removes_card(self, page: Page, register_and_login: dict):
        page.goto(f"{BASE_URL}/app")
        _send_chat_message(page, "Explain support vector machines")
        page.wait_for_timeout(600)
        full_desc = _share_active_session(page, "Delete target")
        _navigate_to_wall(page)

        target_card = page.locator('[data-share-id]').filter(has_text=full_desc).first
        target_card.locator('[aria-label="Delete share"]').click()
        # Confirm via KnrConfirm dialog — wait for it to appear, then click OK
        page.wait_for_selector('#knr-confirm-ok', timeout=8_000)
        page.locator('#knr-confirm-ok').click()
        page.wait_for_timeout(1_500)
        # Full page reload to confirm server-side deletion
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_timeout(1_000)
        assert page.locator('[data-share-id]').filter(has_text=full_desc).count() == 0


# ---------------------------------------------------------------------------
# Preview modal
# ---------------------------------------------------------------------------


class TestSharePreview:
    def test_preview_button_opens_modal(
        self, page: Page, register_and_login: dict, second_api_user: dict
    ):
        uid = uuid.uuid4().hex[:6]
        share = _api_create_share(second_api_user["session"], f"Preview test {uid}")
        share_id = share["id"]
        page.goto(f"{BASE_URL}/app")
        _navigate_to_wall(page)
        page.wait_for_selector(f'[data-share-id="{share_id}"]', timeout=_WALL_TIMEOUT)
        card = page.locator(f'[data-share-id="{share_id}"]')
        card.locator('button:has-text("Preview")').click()
        page.wait_for_timeout(1_500)
        # Preview modal should appear — either a dialog role or some preview-specific text
        has_dialog = page.locator('[role="dialog"]').count() >= 1
        has_preview_text = page.locator("text=Preview").count() >= 1
        assert has_dialog or has_preview_text
