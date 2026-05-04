from flask import Blueprint, jsonify

from backend.core.db import get_pool

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    try:
        with get_pool().connection() as conn:
            conn.execute("SELECT 1")
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as exc:
        return jsonify({"status": "error", "db": str(exc)}), 503
