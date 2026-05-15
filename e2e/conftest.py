from __future__ import annotations

import os
import uuid

import pytest
import requests as _requests
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


def api_register(base_url: str, user: dict | None = None) -> _requests.Session:
    """Register a new user via the API and return an authenticated requests.Session.

    The session has the Flask session cookie set after registration, so all
    subsequent requests through it are authenticated as that user.
    """
    if user is None:
        user = unique_user()
    s = _requests.Session()
    s.post(
        f"{base_url}/auth/register",
        json={
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "username": user["username"],
            "email": user["email"],
            "password": user["password"],
            "confirm_password": user["confirm_password"],
        },
    )
    return s


@pytest.fixture()
def register_and_login(page: Page) -> dict:
    """Register a fresh user via the browser form, log them in, return credentials."""
    user = unique_user()

    page.goto(f'{BASE_URL}/register', timeout=60_000)
    page.fill('#first_name', user['first_name'])
    page.fill('#last_name', user['last_name'])
    page.fill('#username', user['username'])
    page.fill('#email', user['email'])
    page.fill('#password', user['password'])
    page.fill('#confirm_password', user['confirm_password'])
    page.click('button[type="submit"]')
    page.wait_for_url(f'{BASE_URL}/app', timeout=30_000)

    return user


@pytest.fixture()
def second_api_user() -> dict:
    """Create a second user via the API and return {session, user}.

    The ``session`` is an authenticated requests.Session — use it to make
    API calls on behalf of the second user without touching the browser page.
    """
    user = unique_user()
    s = api_register(BASE_URL, user)
    return {"session": s, "user": user}
