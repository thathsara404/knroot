from __future__ import annotations

import logging
from functools import wraps

from flask import g, make_response, redirect, request, session, url_for

from backend.core.errors import UnauthorizedError

logger = logging.getLogger(__name__)


def require_auth(f):
    """Page-route guard: redirects unauthenticated requests to /login.

    For HTMX partial requests, returns HX-Redirect instead of a 302 so the
    browser does a full-page navigation rather than swapping the login page
    HTML into the partial's target element.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            login_url = url_for('pages.login')
            if request.headers.get('HX-Request'):
                resp = make_response('', 204)
                resp.headers['HX-Redirect'] = login_url
                return resp
            return redirect(login_url)
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
