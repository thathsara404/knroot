from __future__ import annotations

import logging
from functools import wraps

from flask import g, redirect, session, url_for

from backend.core.errors import UnauthorizedError

logger = logging.getLogger(__name__)


def require_auth(f):
    """Page-route guard: redirects unauthenticated browsers to /login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('pages.login'))
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_api_auth(f):
    """HTMX/JSON-endpoint guard: returns 401 JSON if session is missing."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            raise UnauthorizedError('Authentication required')
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated
