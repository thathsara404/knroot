from __future__ import annotations

import logging
from flask import jsonify

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    default_message = "An unexpected error occurred"

    def __init__(self, message: str | None = None, detail: str | None = None):
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    default_message = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    default_message = "Access denied"


class UnauthorizedError(AppError):
    status_code = 401
    default_message = "Authentication required"


class ConflictError(AppError):
    status_code = 409
    default_message = "Resource already exists"


class UnprocessableError(AppError):
    status_code = 422
    default_message = "Validation failed"

    def __init__(self, message: str | None = None, fields: dict | None = None, detail: str | None = None):
        self.fields = {k: v for k, v in (fields or {}).items() if v is not None}
        super().__init__(message, detail)


class ServiceUnavailableError(AppError):
    status_code = 503
    default_message = "Upstream service unavailable"


def register_error_handlers(app):
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(exc: RateLimitExceeded):
        return jsonify({"error": "Too many requests", "detail": str(exc.description)}), 429


    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError):
        body = {"error": exc.message}
        if isinstance(exc, UnprocessableError) and exc.fields:
            body["fields"] = exc.fields
        if exc.detail and app.config.get("DEBUG"):
            body["detail"] = exc.detail
        return jsonify(body), exc.status_code

    @app.errorhandler(404)
    def handle_404(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(_):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        logger.exception("Unhandled exception")
        body = {"error": "Internal server error"}
        if app.config.get("DEBUG"):
            body["detail"] = str(exc)
        return jsonify(body), 500
