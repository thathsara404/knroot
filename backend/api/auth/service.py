from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import current_app

from backend.core.db import execute_returning, query_one
from backend.core.errors import ConflictError, UnauthorizedError, UnprocessableError
from backend.extensions import get_redis

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,50}$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_PHONE_RE = re.compile(r'^\+?[1-9]\d{1,14}$')


def _validate_register(data: dict) -> None:
    fields: dict[str, str] = {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    full_name = (data.get('full_name') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not _USERNAME_RE.match(username):
        fields['username'] = 'Must be 3–50 characters: letters, digits, or underscores'
    if not _EMAIL_RE.match(email):
        fields['email'] = 'Enter a valid email address'
    if phone and not _PHONE_RE.match(phone):
        fields['phone'] = 'Enter a valid phone number (E.164 format)'
    if not full_name or len(full_name) > 100:
        fields['full_name'] = 'Required and must be under 100 characters'
    pw_ok = (
        len(password) >= 8
        and any(c.isdigit() for c in password)
        and any(c.isalpha() for c in password)
    )
    if not pw_ok:
        fields['password'] = 'At least 8 characters with one letter and one digit'

    if fields:
        raise UnprocessableError(fields=fields)


def _access_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=current_app.config['JWT_ACCESS_EXPIRES_MINUTES']
    )
    return jwt.encode(
        {'sub': user_id, 'exp': exp, 'iat': datetime.now(timezone.utc)},
        current_app.config['SECRET_KEY'],
        algorithm='HS256',
    )


def _refresh_token(user_id: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    exp = datetime.now(timezone.utc) + timedelta(
        days=current_app.config['JWT_REFRESH_EXPIRES_DAYS']
    )
    token = jwt.encode(
        {'sub': user_id, 'jti': jti, 'exp': exp, 'iat': datetime.now(timezone.utc)},
        current_app.config['SECRET_KEY'],
        algorithm='HS256',
    )
    return token, jti


def _store_jti(jti: str) -> None:
    ttl = current_app.config['JWT_REFRESH_EXPIRES_DAYS'] * 86400
    get_redis().setex(f'refresh:{jti}', ttl, '1')


def _profile(row: dict) -> dict:
    return {
        'id': str(row['id']),
        'username': row['username'],
        'email': row['email'],
        'phone': row.get('phone'),
        'full_name': row['full_name'],
        'created_at': row['created_at'].isoformat(),
    }


def register_user(data: dict) -> dict:
    _validate_register(data)
    username = data['username'].strip()
    email = data['email'].strip().lower()
    full_name = data['full_name'].strip()
    phone = (data.get('phone') or '').strip() or None
    password_hash = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt(rounds=12)).decode()

    if query_one('SELECT 1 FROM users WHERE username = %s', (username,)):
        raise ConflictError('Username already taken')
    if query_one('SELECT 1 FROM users WHERE email = %s', (email,)):
        raise ConflictError('Email already registered')

    row = execute_returning(
        '''INSERT INTO users (username, email, phone, full_name, password_hash)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, username, email, phone, full_name, created_at''',
        (username, email, phone, full_name, password_hash),
    )
    return _profile(row)


def login_user(identifier: str, password: str) -> tuple[str, str, dict]:
    row = query_one('SELECT * FROM users WHERE username = %s', (identifier,))
    if not row:
        row = query_one('SELECT * FROM users WHERE email = %s', (identifier.lower(),))
    if not row or not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        raise UnauthorizedError('Invalid credentials')

    user_id = str(row['id'])
    access = _access_token(user_id)
    refresh, jti = _refresh_token(user_id)
    _store_jti(jti)
    return access, refresh, _profile(row)


def rotate_refresh_token(token: str) -> tuple[str, str]:
    try:
        payload = jwt.decode(
            token, current_app.config['SECRET_KEY'], algorithms=['HS256']
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError('Refresh token has expired')
    except jwt.InvalidTokenError:
        raise UnauthorizedError('Invalid refresh token')

    jti = payload.get('jti', '')
    if not jti or not get_redis().exists(f'refresh:{jti}'):
        raise UnauthorizedError('Refresh token has been revoked')

    get_redis().delete(f'refresh:{jti}')
    new_access = _access_token(payload['sub'])
    new_refresh, new_jti = _refresh_token(payload['sub'])
    _store_jti(new_jti)
    return new_access, new_refresh


def revoke_refresh_token(token: str) -> None:
    try:
        payload = jwt.decode(
            token, current_app.config['SECRET_KEY'], algorithms=['HS256']
        )
        get_redis().delete(f'refresh:{payload.get("jti", "")}')
    except jwt.InvalidTokenError:
        pass


def get_user_profile(user_id: str) -> dict:
    row = query_one(
        'SELECT id, username, email, phone, full_name, created_at FROM users WHERE id = %s',
        (user_id,),
    )
    if not row:
        raise UnauthorizedError('User not found')
    return _profile(row)
