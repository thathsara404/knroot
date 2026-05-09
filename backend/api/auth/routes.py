from __future__ import annotations

import logging

from pydantic import ValidationError
from flask import Blueprint, g, jsonify, make_response, redirect, request, session, url_for

from backend.api.auth import service as auth_service
from backend.api.auth.schemas import LoginRequest, RegisterRequest
from backend.core.auth import require_api_auth
from backend.core.errors import UnprocessableError
from backend.extensions import limiter

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__, url_prefix='/auth')


def _parse(schema_cls, data: dict):
    """Parse request data via Pydantic schema; raise UnprocessableError on failure."""
    try:
        return schema_cls.model_validate(data)
    except ValidationError as exc:
        fields: dict[str, str] = {}
        for err in exc.errors():
            if err['type'] == 'value_error':
                # Pydantic v2 wraps the raised ValueError in ctx['error'] as a ValueError object
                exc_obj = err.get('ctx', {}).get('error')
                if isinstance(exc_obj, ValueError) and exc_obj.args:
                    inner = exc_obj.args[0]
                    if isinstance(inner, dict):
                        fields.update(inner)
                        continue
            loc = '.'.join(str(part) for part in err['loc']) if err['loc'] else ''
            fields[loc] = err['msg']
        raise UnprocessableError(fields=fields)


def _get_data() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def _redirect_or_htmx(endpoint: str):
    url = url_for(endpoint)
    if request.headers.get('HX-Request'):
        resp = make_response('', 204)
        resp.headers['HX-Redirect'] = url
        return resp
    return redirect(url)


@bp.post('/register')
@limiter.limit('3 per minute')
def register():
    req = _parse(RegisterRequest, _get_data())
    user = auth_service.register_user(
        first_name=req.first_name,
        last_name=req.last_name,
        username=req.username,
        email=req.email,
        password=req.password,
        phone=req.phone,
    )
    session['user_id'] = user.id
    session.permanent = True
    return _redirect_or_htmx('pages.index')


@bp.post('/login')
@limiter.limit('10 per minute')
def login():
    req = _parse(LoginRequest, _get_data())
    user = auth_service.login_user(req.identifier.strip(), req.password)
    session['user_id'] = user.id
    session.permanent = True
    return _redirect_or_htmx('pages.index')


@bp.post('/logout')
def logout():
    session.clear()
    return _redirect_or_htmx('pages.login')


@bp.get('/me')
@require_api_auth
def me():
    return jsonify(auth_service.get_user(g.user_id).to_profile())
