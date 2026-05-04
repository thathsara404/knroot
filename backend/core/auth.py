import logging
from functools import wraps

import jwt
from flask import current_app, g, request

from backend.core.errors import UnauthorizedError

logger = logging.getLogger(__name__)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Missing or invalid Authorization header")

        token = auth_header[len("Bearer "):]
        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token has expired")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid token")

        g.user_id = payload["sub"]
        return f(*args, **kwargs)

    return decorated
