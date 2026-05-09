from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request

from backend.api.wall import service as wall_svc
from backend.core.auth import require_api_auth, require_auth

bp = Blueprint("wall", __name__)


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------

@bp.get("/wall/public/partial")
@require_auth
def public_wall_partial():
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    shares = wall_svc.list_public_shares(g.user_id, limit=20, offset=offset)
    return render_template(
        "partials/wall_public.html",
        shares=shares,
        offset=offset,
        current_user_id=g.user_id,
    )


@bp.get("/wall/private/partial")
@require_auth
def private_wall_partial():
    shares = wall_svc.list_private_shares(g.user_id)
    return render_template(
        "partials/wall_private.html",
        shares=shares,
        current_user_id=g.user_id,
    )


@bp.get("/wall/profile/partial")
@require_auth
def profile_partial():
    profile = wall_svc.get_profile(g.user_id, g.user_id)
    return render_template(
        "partials/profile_main.html",
        profile=profile,
        current_user_id=g.user_id,
    )


@bp.get("/wall/score/partial")
@require_auth
def score_partial():
    score_data = wall_svc.get_user_score(g.user_id)
    profile = wall_svc.get_profile(g.user_id, g.user_id)
    return render_template(
        "partials/profile_score.html",
        score_data=score_data,
        profile=profile,
    )


# ---------------------------------------------------------------------------
# JSON APIs
# ---------------------------------------------------------------------------

@bp.post("/wall/shares")
@require_api_auth
def create_share():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    visibility = data.get("visibility", "public")
    description = (data.get("description") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if visibility not in ("public", "friends"):
        visibility = "public"
    try:
        share = wall_svc.create_share(g.user_id, session_id, visibility, description)
        return jsonify(share), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@bp.delete("/wall/shares/<share_id>")
@require_api_auth
def delete_share(share_id: str):
    try:
        wall_svc.delete_share(g.user_id, share_id)
        return "", 204
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.post("/wall/shares/<share_id>/save")
@require_api_auth
def save_share(share_id: str):
    try:
        wall_svc.save_to_wall(g.user_id, share_id)
        return "", 204
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@bp.delete("/wall/shares/<share_id>/save")
@require_api_auth
def unsave_share(share_id: str):
    wall_svc.unsave_from_wall(g.user_id, share_id)
    return "", 204


@bp.post("/wall/shares/<share_id>/vote")
@require_api_auth
def vote_share(share_id: str):
    data = request.get_json(silent=True) or {}
    vote = data.get("vote", 0)
    if vote not in (-1, 0, 1):
        return jsonify({"error": "vote must be -1, 0, or 1"}), 400
    try:
        result = wall_svc.cast_vote(g.user_id, share_id, vote)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.post("/wall/shares/<share_id>/comments")
@require_api_auth
def add_comment(share_id: str):
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    parent_comment_id = (data.get("parent_comment_id") or "").strip() or None
    try:
        comment = wall_svc.add_comment(g.user_id, share_id, content, parent_comment_id)
        return jsonify(comment), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.get("/wall/shares/<share_id>/comments")
@require_api_auth
def list_comments(share_id: str):
    return jsonify(wall_svc.list_comments(share_id))


@bp.delete("/wall/comments/<comment_id>")
@require_api_auth
def delete_comment(comment_id: str):
    try:
        wall_svc.delete_comment(g.user_id, comment_id)
        return "", 204
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.post("/wall/follow/<user_id>")
@require_api_auth
def follow(user_id: str):
    result = wall_svc.follow_user(g.user_id, user_id)
    return jsonify(result), 200


@bp.delete("/wall/follow/<user_id>")
@require_api_auth
def unfollow(user_id: str):
    wall_svc.cancel_follow(g.user_id, user_id)
    return "", 204


@bp.post("/wall/follow-requests/<requester_id>/accept")
@require_api_auth
def accept_follow_request(requester_id: str):
    try:
        wall_svc.accept_follow_request(g.user_id, requester_id)
        return "", 204
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.post("/wall/follow-requests/<requester_id>/reject")
@require_api_auth
def reject_follow_request(requester_id: str):
    wall_svc.reject_follow_request(g.user_id, requester_id)
    return "", 204


@bp.get("/wall/follow-requests/count")
@require_api_auth
def follow_request_count():
    count = len(wall_svc.get_pending_requests(g.user_id))
    return jsonify({"count": count})


# ---------------------------------------------------------------------------
# Preview + Import
# ---------------------------------------------------------------------------

@bp.get("/wall/shares/<share_id>/preview/partial")
@require_auth
def share_preview_partial(share_id: str):
    try:
        preview = wall_svc.get_share_preview(share_id)
    except ValueError:
        return "<p class='p-4 text-gray-500 text-sm'>Share not found.</p>", 404
    return render_template("partials/share_preview_modal.html", preview=preview)


@bp.get("/wall/shares/<share_id>/sessions/<session_id>/preview/partial")
@require_auth
def share_session_preview_partial(share_id: str, session_id: str):
    share = wall_svc.get_share_preview(share_id)  # validates share exists
    content = wall_svc.get_session_preview_content(share["session_id"], session_id)
    return render_template("partials/share_session_preview.html", content=content)


@bp.post("/wall/shares/<share_id>/import")
@require_api_auth
def import_share(share_id: str):
    try:
        result = wall_svc.import_share(g.user_id, share_id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
