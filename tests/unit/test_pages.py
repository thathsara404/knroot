"""Tests for Jinja2 page routes (backend/api/pages/routes.py)."""


# ── Landing page (/) — publicly accessible ────────────────────────────────────

def test_landing_renders_for_unauthenticated(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Mathemariza' in resp.data


def test_landing_renders_for_authenticated(authed_client):
    # Authenticated users also see the landing page at /
    resp = authed_client.get('/')
    assert resp.status_code == 200
    assert b'Mathemariza' in resp.data


# ── App dashboard (/app) — auth required ─────────────────────────────────────

def test_app_redirects_unauthenticated_to_login(client):
    resp = client.get('/app')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_app_renders_for_authenticated(authed_client):
    resp = authed_client.get('/app')
    assert resp.status_code == 200


# ── Auth pages (/login, /register) ───────────────────────────────────────────

def test_login_page_renders(client):
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'Sign In' in resp.data


def test_register_page_renders(client):
    resp = client.get('/register')
    assert resp.status_code == 200
    assert b'Create Account' in resp.data


def test_login_page_redirects_when_already_authenticated(authed_client):
    resp = authed_client.get('/login')
    assert resp.status_code == 302


def test_register_page_redirects_when_already_authenticated(authed_client):
    resp = authed_client.get('/register')
    assert resp.status_code == 302


# ── Learn page (/learn/<session_id>) — auth required ─────────────────────────

def test_learn_page_redirects_unauthenticated(client):
    resp = client.get('/learn/some-session-id')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_learn_page_redirects_when_session_not_found(authed_client, mocker):
    mocker.patch('backend.api.sessions.service.get_session', return_value=None)
    mocker.patch('backend.api.sessions.service.get_tree', return_value=[])
    resp = authed_client.get('/learn/nonexistent-session')
    assert resp.status_code == 302


def test_learn_page_renders_for_valid_session(authed_client, mocker):
    mocker.patch('backend.api.sessions.service.get_session', return_value={
        'id': 'sess-1', 'title': 'Test Session', 'session_type': 'regular',
        'topic': None, 'created_at': '2026-01-01T00:00:00',
    })
    mocker.patch('backend.api.sessions.service.get_tree', return_value=[])
    resp = authed_client.get('/learn/sess-1')
    assert resp.status_code == 200
    assert b'Test Session' in resp.data


# ── Quiz page (/quiz/<attempt_id>) — auth required ───────────────────────────

def test_quiz_page_redirects_unauthenticated(client):
    resp = client.get('/quiz/some-attempt-id')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_quiz_page_renders_for_valid_attempt(authed_client, mocker):
    mocker.patch('backend.api.quiz.service.get_attempt', return_value={
        'attempt_id': 'attempt-1', 'session_id': 'sess-1',
        'questions': [], 'answers': {}, 'score': None, 'completed_at': None,
    })
    mocker.patch('backend.api.sessions.service.get_session', return_value={
        'id': 'sess-1', 'title': 'ML Basics', 'session_type': 'regular',
    })
    mocker.patch('backend.core.db.query_one', return_value=None)
    resp = authed_client.get('/quiz/attempt-1')
    assert resp.status_code == 200


def test_quiz_page_uses_fallback_title_when_session_missing(authed_client, mocker):
    mocker.patch('backend.api.quiz.service.get_attempt', return_value={
        'attempt_id': 'attempt-1', 'session_id': 'sess-1',
        'questions': [], 'answers': {}, 'score': None, 'completed_at': None,
    })
    mocker.patch('backend.api.sessions.service.get_session', return_value=None)
    mocker.patch('backend.core.db.query_one', return_value=None)
    resp = authed_client.get('/quiz/attempt-1')
    assert resp.status_code == 200
    assert b'Knowledge Check' in resp.data
