from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, unique_user


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegisterPage:
    def test_register_page_renders_all_fields(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        expect(page.locator('#first_name')).to_be_visible()
        expect(page.locator('#last_name')).to_be_visible()
        expect(page.locator('#username')).to_be_visible()
        expect(page.locator('#email')).to_be_visible()
        expect(page.locator('#phone')).to_be_visible()
        expect(page.locator('#password')).to_be_visible()
        expect(page.locator('#confirm_password')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_register_already_logged_in_redirects_to_app(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f'{BASE_URL}/register')
        expect(page).to_have_url(f'{BASE_URL}/app')

    def test_register_success_redirects_to_app(self, page: Page):
        user = unique_user()
        page.goto(f'{BASE_URL}/register')
        page.fill('#first_name', user['first_name'])
        page.fill('#last_name', user['last_name'])
        page.fill('#username', user['username'])
        page.fill('#email', user['email'])
        page.fill('#password', user['password'])
        page.fill('#confirm_password', user['confirm_password'])
        page.click('button[type="submit"]')
        page.wait_for_url(f'{BASE_URL}/app', timeout=30_000)
        expect(page).to_have_url(f'{BASE_URL}/app')

    def test_register_shows_password_match_indicator(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        page.fill('#password', 'SecurePass1')
        page.fill('#confirm_password', 'SecurePass1')
        expect(page.get_by_text('Passwords match ✓')).to_be_visible()

    def test_register_shows_password_mismatch_indicator(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        page.fill('#password', 'SecurePass1')
        page.fill('#confirm_password', 'WrongPass1')
        expect(page.get_by_text('Passwords do not match')).to_be_visible()

    def test_register_submit_disabled_on_password_mismatch(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        page.fill('#password', 'SecurePass1')
        page.fill('#confirm_password', 'WrongPass1')
        expect(page.locator('button[type="submit"]')).to_be_disabled()

    def test_register_duplicate_username_shows_error(self, page: Page, register_and_login: dict):
        # Clear session cookies so /register doesn't redirect to /app
        page.context.clear_cookies()

        new_user = unique_user()
        new_user['username'] = register_and_login['username']  # reuse same username

        page.goto(f'{BASE_URL}/register')
        page.fill('#first_name', new_user['first_name'])
        page.fill('#last_name', new_user['last_name'])
        page.fill('#username', new_user['username'])
        page.fill('#email', new_user['email'])
        page.fill('#password', new_user['password'])
        page.fill('#confirm_password', new_user['confirm_password'])
        page.click('button[type="submit"]')

        expect(page.locator('#register-error')).to_be_visible()
        expect(page.locator('#register-error')).to_contain_text('Username')

    def test_register_weak_password_shows_error(self, page: Page):
        user = unique_user()
        page.goto(f'{BASE_URL}/register')
        page.fill('#first_name', user['first_name'])
        page.fill('#last_name', user['last_name'])
        page.fill('#username', user['username'])
        page.fill('#email', user['email'])
        page.fill('#password', 'weak')
        page.fill('#confirm_password', 'weak')
        page.click('button[type="submit"]')

        # Filter to the password field error (contains "8 characters")
        error = page.locator('p[role="alert"]').filter(has_text='8 characters')
        expect(error).to_be_visible()

    def test_register_password_toggle_shows_text(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        page.fill('#password', 'SecurePass1')
        expect(page.locator('#password')).to_have_attribute('type', 'password')
        # Click the toggle button (first one, for password field)
        page.locator('#password').locator('..').locator('button').click()
        expect(page.locator('#password')).to_have_attribute('type', 'text')


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLoginPage:
    def test_login_page_renders(self, page: Page):
        page.goto(f'{BASE_URL}/login')
        expect(page.locator('#identifier')).to_be_visible()
        expect(page.locator('#password')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_login_already_authenticated_redirects_to_app(
        self, page: Page, register_and_login: dict
    ):
        page.goto(f'{BASE_URL}/login')
        expect(page).to_have_url(f'{BASE_URL}/app')

    def test_login_with_username_succeeds(self, page: Page, register_and_login: dict):
        # Clear session then re-login with username
        page.context.clear_cookies()
        page.goto(f'{BASE_URL}/login')
        page.fill('#identifier', register_and_login['username'])
        page.fill('#password', register_and_login['password'])
        page.click('button[type="submit"]')
        page.wait_for_url(f'{BASE_URL}/app', timeout=10_000)
        expect(page).to_have_url(f'{BASE_URL}/app')

    def test_login_with_email_succeeds(self, page: Page, register_and_login: dict):
        # Clear session then re-login with email
        page.context.clear_cookies()
        page.goto(f'{BASE_URL}/login')
        page.fill('#identifier', register_and_login['email'])
        page.fill('#password', register_and_login['password'])
        page.click('button[type="submit"]')
        page.wait_for_url(f'{BASE_URL}/app', timeout=10_000)
        expect(page).to_have_url(f'{BASE_URL}/app')

    def test_login_wrong_password_shows_error(self, page: Page, register_and_login: dict):
        # Clear session then attempt login with wrong password
        page.context.clear_cookies()
        page.goto(f'{BASE_URL}/login')
        page.fill('#identifier', register_and_login['username'])
        page.fill('#password', 'WrongPassword1')
        page.click('button[type="submit"]')

        expect(page.locator('#login-error')).to_be_visible()
        expect(page).not_to_have_url(f'{BASE_URL}/app')

    def test_login_unknown_user_shows_error(self, page: Page):
        page.goto(f'{BASE_URL}/login')
        page.fill('#identifier', 'nobody_exists_xyz')
        page.fill('#password', 'SecurePass1')
        page.click('button[type="submit"]')

        expect(page.locator('#login-error')).to_be_visible()

    def test_login_password_toggle(self, page: Page):
        page.goto(f'{BASE_URL}/login')
        page.fill('#password', 'SecurePass1')
        expect(page.locator('#password')).to_have_attribute('type', 'password')
        page.locator('#password').locator('..').locator('button').click()
        expect(page.locator('#password')).to_have_attribute('type', 'text')


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_redirects_to_login(self, page: Page, register_and_login: dict):
        page.goto(f'{BASE_URL}/app')
        page.get_by_role('button', name='Sign Out').click()
        page.wait_for_url(f'{BASE_URL}/login', timeout=10_000)
        expect(page).to_have_url(f'{BASE_URL}/login')

    def test_logout_clears_session_cannot_access_app(self, page: Page, register_and_login: dict):
        page.goto(f'{BASE_URL}/app')
        page.get_by_role('button', name='Sign Out').click()
        page.wait_for_url(f'{BASE_URL}/login', timeout=10_000)
        # After logout, /app should redirect back to login
        page.goto(f'{BASE_URL}/app')
        expect(page).to_have_url(f'{BASE_URL}/login')

    def test_session_persists_on_page_reload(self, page: Page, register_and_login: dict):
        page.goto(f'{BASE_URL}/app')
        page.reload()
        expect(page).to_have_url(f'{BASE_URL}/app')


# ── Protected routes ──────────────────────────────────────────────────────────

class TestProtectedRoutes:
    def test_app_redirects_unauthenticated_to_login(self, page: Page):
        page.goto(f'{BASE_URL}/app')
        expect(page).to_have_url(f'{BASE_URL}/login')

    def test_app_renders_for_authenticated_user(self, page: Page, register_and_login: dict):
        page.goto(f'{BASE_URL}/app')
        expect(page).to_have_url(f'{BASE_URL}/app')
        expect(page).to_have_title('Dashboard — Mathemariza')

    def test_login_page_accessible_unauthenticated(self, page: Page):
        page.goto(f'{BASE_URL}/login')
        expect(page).to_have_url(f'{BASE_URL}/login')
        expect(page).to_have_title('Sign In — Mathemariza')

    def test_register_page_accessible_unauthenticated(self, page: Page):
        page.goto(f'{BASE_URL}/register')
        expect(page).to_have_url(f'{BASE_URL}/register')
        expect(page).to_have_title('Create Account — Mathemariza')
