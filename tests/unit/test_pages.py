"""Tests for Jinja2 page routes (backend/api/pages/routes.py)."""


def test_login_page_renders(client):
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'Sign In' in resp.data


def test_register_page_renders(client):
    resp = client.get('/register')
    assert resp.status_code == 200
    assert b'Create Account' in resp.data


def test_index_redirects_unauthenticated(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_index_renders_for_authenticated(authed_client):
    resp = authed_client.get('/')
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data


def test_login_page_redirects_when_already_authenticated(authed_client):
    resp = authed_client.get('/login')
    assert resp.status_code == 302


def test_register_page_redirects_when_already_authenticated(authed_client):
    resp = authed_client.get('/register')
    assert resp.status_code == 302
