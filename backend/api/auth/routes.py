from __future__ import annotations

import logging

import jwt
from flask import Blueprint, current_app, g, jsonify, make_response, request

from backend.api.auth import service as auth_service
from backend.core.auth import require_auth
from backend.core.errors import UnauthorizedError, UnprocessableError
from backend.extensions import limiter

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__, url_prefix='/auth')

_COOKIE_OPTS = dict(httponly=True, samesite='Strict', path='/auth/refresh')


def _refresh_cookie(token: str, debug: bool) -> dict:
    return {**_COOKIE_OPTS, 'max_age': 7 * 24 * 3600, 'secure': not debug}


@bp.post('/register')
@limiter.limit('3 per minute')
def register():
    data = request.get_json(silent=True) or {}
    auth_service.register_user(data)
    identifier = (data.get('username') or '').strip()
    password = data.get('password') or ''
    access, refresh, profile = auth_service.login_user(identifier, password)
    resp = make_response(jsonify({'access_token': access, 'user': profile}), 201)
    resp.set_cookie('refresh_token', refresh, **_refresh_cookie(refresh, current_app.debug))
    return resp


@bp.post('/login')
@limiter.limit('10 per minute')
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get('identifier') or '').strip()
    password = data.get('password') or ''
    if not identifier or not password:
        raise UnprocessableError(fields={
            'identifier': 'Required' if not identifier else None,
            'password': 'Required' if not password else None,
        })
    access, refresh, profile = auth_service.login_user(identifier, password)
    resp = make_response(jsonify({'access_token': access, 'user': profile}))
    resp.set_cookie('refresh_token', refresh, **_refresh_cookie(refresh, current_app.debug))
    return resp


@bp.post('/refresh')
def refresh():
    token = request.cookies.get('refresh_token')
    if not token:
        raise UnauthorizedError('No refresh token provided')
    new_access, new_refresh = auth_service.rotate_refresh_token(token)
    resp = make_response(jsonify({'access_token': new_access}))
    resp.set_cookie('refresh_token', new_refresh, **_refresh_cookie(new_refresh, current_app.debug))
    return resp


@bp.post('/logout')
@require_auth
def logout():
    token = request.cookies.get('refresh_token')
    if token:
        auth_service.revoke_refresh_token(token)
    resp = make_response(jsonify({'message': 'Logged out'}))
    resp.delete_cookie('refresh_token', path='/auth/refresh')
    return resp


@bp.get('/me')
@require_auth
def me():
    return jsonify(auth_service.get_user_profile(g.user_id))
