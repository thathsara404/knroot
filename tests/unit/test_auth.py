from unittest.mock import patch, MagicMock
import pytest


_USER_ROW = {
    'id': 'user-uuid-1234',
    'username': 'testuser',
    'email': 'test@example.com',
    'phone': '+1234567890',
    'full_name': 'Test User',
    'password_hash': '',  # set per-test when bcrypt needed
    'created_at': __import__('datetime').datetime(2026, 1, 1, tzinfo=__import__('datetime').timezone.utc),
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _hashed(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(4)).decode()


def _register(client, payload):
    return client.post('/auth/register', json=payload)


def _login(client, identifier='testuser', password='SecurePass1'):
    return client.post('/auth/login', json={'identifier': identifier, 'password': password})


# ── register ─────────────────────────────────────────────────────────────────

def test_register_success(client, valid_user_payload, mocker):
    mocker.patch('backend.api.auth.service.query_one', return_value=None)
    row = {**_USER_ROW}
    mocker.patch('backend.api.auth.service.execute_returning', return_value=row)

    with patch('backend.api.auth.service.login_user', return_value=(
        'access-tok', 'refresh-tok', {'id': 'user-uuid-1234', 'username': 'testuser',
                                       'email': 'test@example.com', 'phone': None,
                                       'full_name': 'Test User', 'created_at': '2026-01-01T00:00:00+00:00'}
    )):
        resp = _register(client, valid_user_payload)

    assert resp.status_code == 201
    data = resp.get_json()
    assert 'access_token' in data
    assert data['user']['username'] == 'testuser'


def test_register_duplicate_username_returns_409(client, valid_user_payload, mocker):
    mocker.patch('backend.api.auth.service.query_one', return_value={'id': 'existing'})
    resp = _register(client, valid_user_payload)
    assert resp.status_code == 409
    assert 'Username' in resp.get_json()['error']


def test_register_duplicate_email_returns_409(client, valid_user_payload, mocker):
    def _side(sql, params):
        if 'username' in sql:
            return None
        return {'id': 'existing'}
    mocker.patch('backend.api.auth.service.query_one', side_effect=_side)
    resp = _register(client, valid_user_payload)
    assert resp.status_code == 409
    assert 'Email' in resp.get_json()['error']


def test_register_weak_password_returns_422(client, mocker):
    resp = _register(client, {
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'short', 'full_name': 'Test',
    })
    assert resp.status_code == 422
    assert 'fields' in resp.get_json()


def test_register_invalid_email_returns_422(client, mocker):
    resp = _register(client, {
        'username': 'testuser', 'email': 'not-an-email',
        'password': 'SecurePass1', 'full_name': 'Test',
    })
    assert resp.status_code == 422
    assert 'email' in resp.get_json().get('fields', {})


def test_register_invalid_username_returns_422(client):
    resp = _register(client, {
        'username': 'x',  # too short
        'email': 'a@b.com', 'password': 'SecurePass1', 'full_name': 'Test',
    })
    assert resp.status_code == 422
    assert 'username' in resp.get_json().get('fields', {})


def test_register_invalid_phone_returns_422(client):
    resp = _register(client, {
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'SecurePass1', 'full_name': 'Test',
        'phone': 'not-a-phone',
    })
    assert resp.status_code == 422
    assert 'phone' in resp.get_json().get('fields', {})


def test_register_missing_full_name_returns_422(client):
    resp = _register(client, {
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'SecurePass1',
    })
    assert resp.status_code == 422
    assert 'full_name' in resp.get_json().get('fields', {})


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_success_returns_access_token(client, mocker):
    row = {**_USER_ROW, 'password_hash': _hashed('SecurePass1')}
    mocker.patch('backend.api.auth.service.query_one', return_value=row)
    resp = _login(client)
    assert resp.status_code == 200
    assert 'access_token' in resp.get_json()


def test_login_by_email_succeeds(client, mocker):
    row = {**_USER_ROW, 'password_hash': _hashed('SecurePass1')}
    def _side(sql, params):
        if 'username' in sql:
            return None
        return row
    mocker.patch('backend.api.auth.service.query_one', side_effect=_side)
    resp = _login(client, identifier='test@example.com')
    assert resp.status_code == 200


def test_login_wrong_password_returns_401(client, mocker):
    row = {**_USER_ROW, 'password_hash': _hashed('SecurePass1')}
    mocker.patch('backend.api.auth.service.query_one', return_value=row)
    resp = _login(client, password='WrongPass1')
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client, mocker):
    mocker.patch('backend.api.auth.service.query_one', return_value=None)
    resp = _login(client)
    assert resp.status_code == 401


def test_login_missing_fields_returns_422(client):
    resp = client.post('/auth/login', json={'identifier': 'testuser'})
    assert resp.status_code == 422
    assert 'password' in resp.get_json().get('fields', {})


# ── refresh ───────────────────────────────────────────────────────────────────

def test_refresh_issues_new_token(client, mocker, fresh_redis, app):
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    jti = 'test-jti-1234'
    fresh_redis.setex(f'refresh:{jti}', 3600, '1')
    refresh_tok = pyjwt.encode(
        {'sub': 'user-1', 'jti': jti,
         'exp': datetime.now(timezone.utc) + timedelta(days=7),
         'iat': datetime.now(timezone.utc)},
        app.config['SECRET_KEY'], algorithm='HS256'
    )
    client.set_cookie('refresh_token', refresh_tok)
    resp = client.post('/auth/refresh')
    assert resp.status_code == 200
    assert 'access_token' in resp.get_json()
    assert not fresh_redis.exists(f'refresh:{jti}')


def test_refresh_with_rotated_token_returns_401(client, app):
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    refresh_tok = pyjwt.encode(
        {'sub': 'user-1', 'jti': 'nonexistent-jti',
         'exp': datetime.now(timezone.utc) + timedelta(days=7),
         'iat': datetime.now(timezone.utc)},
        app.config['SECRET_KEY'], algorithm='HS256'
    )
    client.set_cookie('refresh_token', refresh_tok)
    resp = client.post('/auth/refresh')
    assert resp.status_code == 401


# ── logout ────────────────────────────────────────────────────────────────────

def test_logout_invalidates_refresh_token(client, fresh_redis, auth_headers, app, mocker):
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    jti = 'logout-jti'
    fresh_redis.setex(f'refresh:{jti}', 3600, '1')
    refresh_tok = pyjwt.encode(
        {'sub': 'user-uuid-1234', 'jti': jti,
         'exp': datetime.now(timezone.utc) + timedelta(days=7),
         'iat': datetime.now(timezone.utc)},
        app.config['SECRET_KEY'], algorithm='HS256'
    )
    client.set_cookie('refresh_token', refresh_tok)
    resp = client.post('/auth/logout', headers=auth_headers)
    assert resp.status_code == 200
    assert not fresh_redis.exists(f'refresh:{jti}')


# ── refresh — error paths ─────────────────────────────────────────────────────

def test_refresh_without_cookie_returns_401(client):
    resp = client.post('/auth/refresh')
    assert resp.status_code == 401

def test_refresh_expired_token_returns_401(client, app):
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    tok = pyjwt.encode(
        {'sub': 'user-1', 'jti': 'exp-jti',
         'exp': datetime.now(timezone.utc) - timedelta(days=1),
         'iat': datetime.now(timezone.utc) - timedelta(days=8)},
        app.config['SECRET_KEY'], algorithm='HS256',
    )
    client.set_cookie('refresh_token', tok)
    resp = client.post('/auth/refresh')
    assert resp.status_code == 401

def test_refresh_invalid_signature_returns_401(client):
    client.set_cookie('refresh_token', 'not.a.valid.jwt')
    resp = client.post('/auth/refresh')
    assert resp.status_code == 401


# ── logout — error paths ──────────────────────────────────────────────────────

def test_logout_with_invalid_refresh_token_succeeds(client, auth_headers):
    client.set_cookie('refresh_token', 'not.a.valid.jwt')
    resp = client.post('/auth/logout', headers=auth_headers)
    assert resp.status_code == 200


# ── middleware ────────────────────────────────────────────────────────────────

def test_protected_route_without_token_returns_401(client):
    resp = client.get('/auth/me')
    assert resp.status_code == 401


def test_protected_route_with_expired_token_returns_401(client, app):
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    tok = pyjwt.encode(
        {'sub': 'user-1',
         'exp': datetime.now(timezone.utc) - timedelta(minutes=1),
         'iat': datetime.now(timezone.utc) - timedelta(minutes=16)},
        app.config['SECRET_KEY'], algorithm='HS256',
    )
    resp = client.get('/auth/me', headers={'Authorization': f'Bearer {tok}'})
    assert resp.status_code == 401


def test_protected_route_with_invalid_token_returns_401(client):
    resp = client.get('/auth/me', headers={'Authorization': 'Bearer bad.token.here'})
    assert resp.status_code == 401


def test_me_user_not_found_returns_401(client, auth_headers, mocker):
    mocker.patch('backend.api.auth.service.query_one', return_value=None)
    resp = client.get('/auth/me', headers=auth_headers)
    assert resp.status_code == 401


def test_protected_route_with_valid_token_succeeds(client, auth_headers, mocker):
    mocker.patch('backend.api.auth.service.query_one', return_value={
        **_USER_ROW,
        'created_at': __import__('datetime').datetime(2026, 1, 1, tzinfo=__import__('datetime').timezone.utc)
    })
    resp = client.get('/auth/me', headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()['username'] == 'testuser'


def test_rate_limit_on_login(client):
    for _ in range(11):
        resp = client.post('/auth/login', json={'identifier': 'x', 'password': 'y'})
    assert resp.status_code == 429
