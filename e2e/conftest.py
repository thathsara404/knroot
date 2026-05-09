from __future__ import annotations

import os
import uuid

import pytest
from playwright.sync_api import Page

BASE_URL = os.getenv('BASE_URL', 'http://localhost:5001')


def unique_user() -> dict:
    """Generate a unique user payload for each test to avoid DB conflicts."""
    uid = uuid.uuid4().hex[:8]
    return {
        'first_name': 'Test',
        'last_name': 'User',
        'username': f'testuser_{uid}',
        'email': f'test_{uid}@example.com',
        'password': 'SecurePass1',
        'confirm_password': 'SecurePass1',
    }


@pytest.fixture()
def register_and_login(page: Page) -> dict:
    """Register a fresh user, log them in, and return their credentials."""
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

    return user
