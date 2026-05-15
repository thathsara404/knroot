import datetime
import pytest

from backend.domain.user import User

_USER = User(
    id='user-uuid-1234',
    username='testuser',
    email='test@example.com',
    full_name='Test User',
    phone='+1234567890',
    created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
)

HTMX = {'HX-Request': 'true'}
REPO = 'backend.repositories.user_repository.user_repo'


def _hashed(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(4)).decode()


def _register(client, payload):
    return client.post('/auth/register', json=payload)


def _login(client, identifier='testuser', password='SecurePass1', extra_headers=None):
    headers = {'Content-Type': 'application/json'}
    if extra_headers:
        headers.update(extra_headers)
    return client.post(
        '/auth/login',
        json={'identifier': identifier, 'password': password},
        headers=headers,
    )


# ── register ─────────────────────────────────────────────────────────────────

def test_register_success_redirects(client, valid_user_payload, mocker):
    mocker.patch(f'{REPO}.exists_by_username', return_value=False)
    mocker.patch(f'{REPO}.exists_by_email', return_value=False)
    mocker.patch(f'{REPO}.create', return_value=_USER)
    resp = _register(client, valid_user_payload)
    assert resp.status_code == 302


def test_register_success_sets_session(client, valid_user_payload, mocker):
    mocker.patch(f'{REPO}.exists_by_username', return_value=False)
    mocker.patch(f'{REPO}.exists_by_email', return_value=False)
    mocker.patch(f'{REPO}.create', return_value=_USER)
    _register(client, valid_user_payload)
    with client.session_transaction() as sess:
        assert sess.get('user_id') == 'user-uuid-1234'


def test_register_htmx_returns_204_with_hx_redirect(client, valid_user_payload, mocker):
    mocker.patch(f'{REPO}.exists_by_username', return_value=False)
    mocker.patch(f'{REPO}.exists_by_email', return_value=False)
    mocker.patch(f'{REPO}.create', return_value=_USER)
    resp = client.post('/auth/register', json=valid_user_payload, headers=HTMX)
    assert resp.status_code == 204
    assert 'HX-Redirect' in resp.headers


def test_register_duplicate_username_returns_409(client, valid_user_payload, mocker):
    mocker.patch(f'{REPO}.exists_by_username', return_value=True)
    resp = _register(client, valid_user_payload)
    assert resp.status_code == 409
    assert 'Username' in resp.get_json()['error']


def test_register_duplicate_email_returns_409(client, valid_user_payload, mocker):
    mocker.patch(f'{REPO}.exists_by_username', return_value=False)
    mocker.patch(f'{REPO}.exists_by_email', return_value=True)
    resp = _register(client, valid_user_payload)
    assert resp.status_code == 409
    assert 'Email' in resp.get_json()['error']


def test_register_weak_password_returns_422(client):
    resp = _register(client, {
        'first_name': 'Test', 'last_name': 'User',
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'short', 'confirm_password': 'short',
    })
    assert resp.status_code == 422
    assert 'password' in resp.get_json().get('fields', {})


def test_register_password_mismatch_returns_422(client):
    resp = _register(client, {
        'first_name': 'Test', 'last_name': 'User',
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'SecurePass1', 'confirm_password': 'DifferentPass1',
    })
    assert resp.status_code == 422
    assert 'confirm_password' in resp.get_json().get('fields', {})


def test_register_invalid_email_returns_422(client):
    resp = _register(client, {
        'first_name': 'Test', 'last_name': 'User',
        'username': 'testuser', 'email': 'not-an-email',
        'password': 'SecurePass1', 'confirm_password': 'SecurePass1',
    })
    assert resp.status_code == 422
    assert 'email' in resp.get_json().get('fields', {})


def test_register_invalid_username_returns_422(client):
    resp = _register(client, {
        'first_name': 'Test', 'last_name': 'User',
        'username': 'x', 'email': 'a@b.com',
        'password': 'SecurePass1', 'confirm_password': 'SecurePass1',
    })
    assert resp.status_code == 422
    assert 'username' in resp.get_json().get('fields', {})


def test_register_invalid_phone_returns_422(client):
    resp = _register(client, {
        'first_name': 'Test', 'last_name': 'User',
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'SecurePass1', 'confirm_password': 'SecurePass1',
        'phone': 'not-a-phone',
    })
    assert resp.status_code == 422
    assert 'phone' in resp.get_json().get('fields', {})


def test_register_missing_name_returns_422(client):
    resp = _register(client, {
        'username': 'testuser', 'email': 'a@b.com',
        'password': 'SecurePass1', 'confirm_password': 'SecurePass1',
    })
    assert resp.status_code == 422
    fields = resp.get_json().get('fields', {})
    assert 'first_name' in fields or 'last_name' in fields


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_success_redirects(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=(_USER, _hashed('SecurePass1')))
    resp = _login(client)
    assert resp.status_code == 302


def test_login_success_sets_session(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=(_USER, _hashed('SecurePass1')))
    _login(client)
    with client.session_transaction() as sess:
        assert sess.get('user_id') == 'user-uuid-1234'


def test_login_htmx_returns_204_with_hx_redirect(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=(_USER, _hashed('SecurePass1')))
    resp = _login(client, extra_headers=HTMX)
    assert resp.status_code == 204
    assert 'HX-Redirect' in resp.headers


def test_login_by_email_succeeds(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=(_USER, _hashed('SecurePass1')))
    resp = _login(client, identifier='test@example.com')
    assert resp.status_code == 302


def test_login_wrong_password_returns_401(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=(_USER, _hashed('SecurePass1')))
    resp = _login(client, password='WrongPass1')
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client, mocker):
    mocker.patch(f'{REPO}.find_for_auth', return_value=None)
    resp = _login(client)
    assert resp.status_code == 401


def test_login_missing_fields_returns_422(client):
    resp = client.post('/auth/login', json={'identifier': 'testuser'})
    assert resp.status_code == 422
    assert 'password' in resp.get_json().get('fields', {})


# ── logout ────────────────────────────────────────────────────────────────────

def test_logout_clears_session(authed_client):
    resp = authed_client.post('/auth/logout')
    assert resp.status_code == 302
    with authed_client.session_transaction() as sess:
        assert sess.get('user_id') is None


def test_logout_without_session_still_redirects(client):
    resp = client.post('/auth/logout')
    assert resp.status_code == 302


def test_logout_htmx_returns_204_with_hx_redirect(authed_client):
    resp = authed_client.post('/auth/logout', headers=HTMX)
    assert resp.status_code == 204
    assert 'HX-Redirect' in resp.headers


# ── /auth/me ──────────────────────────────────────────────────────────────────

def test_me_without_session_returns_401(client):
    resp = client.get('/auth/me')
    assert resp.status_code == 401


def test_me_with_session_returns_profile(authed_client, mocker):
    mocker.patch(f'{REPO}.find_by_id', return_value=_USER)
    resp = authed_client.get('/auth/me')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == 'testuser'
    assert data['email'] == 'test@example.com'


def test_me_user_not_found_returns_401(authed_client, mocker):
    mocker.patch(f'{REPO}.find_by_id', return_value=None)
    resp = authed_client.get('/auth/me')
    assert resp.status_code == 401


# ── rate limits ───────────────────────────────────────────────────────────────

def test_rate_limit_on_login(client):
    for _ in range(11):
        resp = client.post('/auth/login', json={'identifier': 'x', 'password': 'y'})
    assert resp.status_code == 429


# ── auth/schemas.py direct validation (covers lines 26, 28, 57, 59, 61) ──────

def test_register_schema_empty_first_name_raises_validation_error():
    from pydantic import ValidationError
    from backend.api.auth.schemas import RegisterRequest
    with pytest.raises(ValidationError):
        RegisterRequest(
            first_name='',
            last_name='Valid',
            username='testuser',
            email='test@example.com',
            password='SecurePass1',
            confirm_password='SecurePass1',
        )


def test_register_schema_empty_last_name_raises_validation_error():
    from pydantic import ValidationError
    from backend.api.auth.schemas import RegisterRequest
    with pytest.raises(ValidationError):
        RegisterRequest(
            first_name='Valid',
            last_name='',
            username='testuser',
            email='test@example.com',
            password='SecurePass1',
            confirm_password='SecurePass1',
        )


def test_login_schema_empty_identifier_raises_validation_error():
    from pydantic import ValidationError
    from backend.api.auth.schemas import LoginRequest
    with pytest.raises(ValidationError):
        LoginRequest(identifier='', password='securepass')


def test_login_schema_empty_password_raises_validation_error():
    from pydantic import ValidationError
    from backend.api.auth.schemas import LoginRequest
    with pytest.raises(ValidationError):
        LoginRequest(identifier='user', password='')


def test_login_schema_both_empty_raises_validation_error():
    from pydantic import ValidationError
    from backend.api.auth.schemas import LoginRequest
    with pytest.raises(ValidationError):
        LoginRequest(identifier='', password='')


# ── backend/core/llm.py: build_llm_client with no API key (line 12) ──────────

def test_build_llm_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    from backend.core.llm import build_llm_client
    with pytest.raises(RuntimeError, match='OPENROUTER_API_KEY'):
        build_llm_client()
