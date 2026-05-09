from __future__ import annotations

import json as _json
from typing import Any

from backend.core.db import execute, execute_returning, query, query_one
from backend.core.sse import broadcast_event, publish_event


def _parse_message_content(content: str) -> dict[str, Any]:
    """Parse a stored message content string into a renderable dict.

    Sectioned AI responses are stored as JSON:
      {"type": "sectioned", "intro": "...", "sections": [...], "outro": "..."}
    These are returned as-is for rich template rendering.
    Plain strings are wrapped as {"type": "text", "text": ...}.
    """
    if not content:
        return {"type": "text", "text": ""}
    stripped = content.strip()
    # Strip markdown code fences (```json\n{...}\n``` or ```\n{...}\n```)
    if stripped.startswith("```"):
        try:
            stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        except Exception:
            pass
    if stripped.startswith("{"):
        try:
            parsed = _json.loads(stripped)
            if isinstance(parsed, dict) and parsed.get("type") == "sectioned":
                return parsed
        except (ValueError, TypeError):
            pass
    return {"type": "text", "text": content}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_STAR_THRESHOLDS = [50, 150, 350, 600, 900]


def score_to_stars(score: int) -> float:
    """Map cumulative score to a 0.0-5.0 star rating.

    upvote = +10pts, downvote = -5pts.
    0pts -> 0 stars, 50pts -> 1 star, 150 -> 2, 350 -> 3, 600 -> 4, 900 -> 5.
    """
    if score <= 0:
        return 0.0
    for i, t in enumerate(_STAR_THRESHOLDS):
        if score < t:
            return float(i)
    return 5.0


def get_user_score(user_id: str) -> dict[str, Any]:
    """Returns dict: score, stars, upvotes, downvotes, share_count."""
    row = query_one(
        """
        SELECT
          COALESCE(SUM(CASE WHEN sv.vote = 1 THEN 10 WHEN sv.vote = -1 THEN -5 ELSE 0 END), 0) AS score,
          COALESCE(SUM(CASE WHEN sv.vote = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
          COALESCE(SUM(CASE WHEN sv.vote = -1 THEN 1 ELSE 0 END), 0) AS downvotes,
          COUNT(DISTINCT s.id) AS share_count
        FROM users u
        LEFT JOIN shares s ON s.user_id = u.id
        LEFT JOIN share_votes sv ON sv.share_id = s.id
        WHERE u.id = %s
        """,
        (user_id,),
    ) or {}
    score = int(row.get("score") or 0)
    return {
        "score": score,
        "stars": score_to_stars(score),
        "upvotes": int(row.get("upvotes") or 0),
        "downvotes": int(row.get("downvotes") or 0),
        "share_count": int(row.get("share_count") or 0),
    }


# ---------------------------------------------------------------------------
# Shares — create / delete
# ---------------------------------------------------------------------------

def create_share(
    user_id: str, session_id: str, visibility: str, description: str
) -> dict[str, Any]:
    """Insert share, return the created share dict.

    Raises ValueError if the session doesn't belong to the user.
    """
    if visibility not in ("public", "friends"):
        visibility = "public"

    owns = query_one(
        "SELECT 1 FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not owns:
        raise ValueError("Session not found or not owned by user")

    # Honour UNIQUE(user_id, session_id) — surface a friendly error on dup.
    existing = query_one(
        "SELECT id FROM shares WHERE user_id = %s AND session_id = %s",
        (user_id, session_id),
    )
    if existing:
        raise ValueError("This session has already been shared")

    # If this session was itself imported from a share, propagate attribution forward.
    source_share_id = None
    imported_ref = query_one(
        "SELECT imported_from_share_id FROM chat_sessions WHERE id = %s",
        (session_id,),
    )
    if imported_ref and imported_ref.get("imported_from_share_id"):
        source_share_id = str(imported_ref["imported_from_share_id"])

    row = execute_returning(
        """
        INSERT INTO shares (user_id, session_id, visibility, description, source_share_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, user_id, session_id, visibility, description,
                  source_share_id, created_at
        """,
        (user_id, session_id, visibility, description or None, source_share_id),
    )
    author = query_one("SELECT full_name, username FROM users WHERE id = %s", (user_id,)) or {}
    broadcast_event("share_created", {
        "share_id": str(row["id"]),
        "user_id": str(user_id),
        "author_name": author.get("full_name") or "",
        "author_username": author.get("username") or "",
    })
    return _serialize_share(row)


def delete_share(user_id: str, share_id: str) -> None:
    """Delete share if owner. Raises ValueError if not found / not owner."""
    row = query_one(
        "SELECT user_id FROM shares WHERE id = %s",
        (share_id,),
    )
    if not row:
        raise ValueError("Share not found")
    if str(row["user_id"]) != str(user_id):
        raise ValueError("Not authorised to delete this share")
    execute("DELETE FROM shares WHERE id = %s", (share_id,))


# ---------------------------------------------------------------------------
# Shares — list (public / private)
# ---------------------------------------------------------------------------

def _serialize_share(row: dict) -> dict[str, Any]:
    """Stringify UUIDs/datetimes for JSON safety."""
    out = dict(row)
    for k in ("id", "user_id", "session_id", "source_share_id"):
        if k in out and out[k] is not None:
            out[k] = str(out[k])
    if "created_at" in out and out["created_at"] is not None:
        out["created_at"] = out["created_at"].isoformat()
    return out


def _hydrate_share_rows(rows: list[dict], viewer_user_id: str) -> list[dict[str, Any]]:
    """Add author info, vote counts, viewer's vote, comment count, save status and tree."""
    if not rows:
        return []

    share_ids = [str(r["id"]) for r in rows]
    author_ids = list({str(r["user_id"]) for r in rows})

    # Vote tally per share
    vote_rows = query(
        """
        SELECT share_id,
               COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0)  AS upvotes,
               COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) AS downvotes
        FROM share_votes
        WHERE share_id = ANY(%s::uuid[])
        GROUP BY share_id
        """,
        (share_ids,),
    )
    votes_by_share = {str(v["share_id"]): v for v in vote_rows}

    # Viewer's vote per share
    my_vote_rows = query(
        """
        SELECT share_id, vote FROM share_votes
        WHERE user_id = %s AND share_id = ANY(%s::uuid[])
        """,
        (viewer_user_id, share_ids),
    )
    my_vote_by_share = {str(v["share_id"]): int(v["vote"]) for v in my_vote_rows}

    # Comment counts per share
    comment_rows = query(
        """
        SELECT share_id, COUNT(*) AS cnt
        FROM share_comments
        WHERE share_id = ANY(%s::uuid[])
        GROUP BY share_id
        """,
        (share_ids,),
    )
    comments_by_share = {str(c["share_id"]): int(c["cnt"]) for c in comment_rows}

    # Viewer's follow status for each author (batch, excludes self)
    follow_status_rows = query(
        """
        SELECT followed_id, status
        FROM user_follows
        WHERE follower_id = %s AND followed_id = ANY(%s::uuid[])
        """,
        (viewer_user_id, author_ids),
    )
    follow_status_by_author = {str(r["followed_id"]): r["status"] for r in follow_status_rows}

    # Whether the viewer has saved each share to their private wall
    saved_rows = query(
        """
        SELECT share_id FROM wall_saves
        WHERE user_id = %s AND share_id = ANY(%s::uuid[])
        """,
        (viewer_user_id, share_ids),
    )
    saved_share_ids = {str(r["share_id"]) for r in saved_rows}

    # Author profile + score in a single batch
    authors_by_id: dict[str, dict[str, Any]] = {}
    if author_ids:
        rows_a = query(
            """
            SELECT u.id, u.full_name, u.username,
                   COALESCE(SUM(CASE WHEN sv.vote = 1 THEN 10
                                     WHEN sv.vote = -1 THEN -5
                                     ELSE 0 END), 0) AS score
            FROM users u
            LEFT JOIN shares s2 ON s2.user_id = u.id
            LEFT JOIN share_votes sv ON sv.share_id = s2.id
            WHERE u.id = ANY(%s::uuid[])
            GROUP BY u.id, u.full_name, u.username
            """,
            (author_ids,),
        )
        for ar in rows_a:
            score_val = int(ar["score"] or 0)
            authors_by_id[str(ar["id"])] = {
                "id": str(ar["id"]),
                "full_name": ar["full_name"],
                "username": ar["username"],
                "score": score_val,
                "stars": score_to_stars(score_val),
            }

    # Source attribution — fetch original authors for any share that was imported
    source_ids = [str(r.get("source_share_id")) for r in rows if r.get("source_share_id")]
    source_attr_by_id: dict[str, dict[str, Any]] = {}
    if source_ids:
        src_rows = query(
            """
            SELECT sh.id AS share_id, u.full_name, u.username
            FROM shares sh JOIN users u ON u.id = sh.user_id
            WHERE sh.id = ANY(%s::uuid[])
            """,
            (source_ids,),
        )
        for sr in src_rows:
            source_attr_by_id[str(sr["share_id"])] = {
                "full_name": sr["full_name"],
                "username": sr["username"],
            }

    out: list[dict[str, Any]] = []
    for r in rows:
        share = _serialize_share({
            "id": r["id"],
            "user_id": r["user_id"],
            "session_id": r["session_id"],
            "visibility": r["visibility"],
            "description": r.get("description"),
            "source_share_id": r.get("source_share_id"),
            "created_at": r.get("created_at"),
        })
        sid = share["id"]
        v = votes_by_share.get(sid, {})
        share["upvotes"] = int(v.get("upvotes") or 0)
        share["downvotes"] = int(v.get("downvotes") or 0)
        share["my_vote"] = my_vote_by_share.get(sid, 0)
        share["comment_count"] = comments_by_share.get(sid, 0)
        share["author"] = authors_by_id.get(
            share["user_id"],
            {"id": share["user_id"], "full_name": "Unknown", "username": "",
             "score": 0, "stars": 0.0},
        )
        share["session_title"] = r.get("session_title") or "Untitled"
        share["session_type"] = r.get("session_type") or "regular"
        share["session_topic"] = r.get("session_topic")
        share["session_tree"] = _fetch_session_tree(share["session_id"])
        share["source_share_id"] = (
            str(r["source_share_id"]) if r.get("source_share_id") else None
        )
        share["source_attribution"] = (
            source_attr_by_id.get(share["source_share_id"])
            if share["source_share_id"] else None
        )
        # None for own shares; 'pending'/'accepted' for others
        share["follow_status"] = (
            follow_status_by_author.get(share["user_id"])
            if str(share["user_id"]) != str(viewer_user_id) else None
        )
        # is_own: row-level flag from list_private_shares query (or derive from user_id)
        share["is_own"] = bool(r.get("is_own", str(r["user_id"]) == str(viewer_user_id)))
        # saved_to_wall: True if viewer has added this share to their private wall
        share["saved_to_wall"] = sid in saved_share_ids or bool(r.get("is_saved", False))
        out.append(share)
    return out


def _fetch_session_tree(session_id: str) -> list[dict[str, Any]]:
    """Return the whole tree (depth-ordered) rooted at the share's session.

    Handles legacy rows where root_session_id may be NULL on a root session.
    """
    rows = query(
        """
        SELECT id, title, session_type, depth_level, parent_session_id, topic
        FROM chat_sessions
        WHERE root_session_id = %s
           OR (id = %s AND root_session_id IS NULL)
        ORDER BY depth_level, created_at
        """,
        (session_id, session_id),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": str(r["id"]),
            "title": r.get("title"),
            "session_type": r.get("session_type"),
            "depth_level": int(r.get("depth_level") or 0),
            "parent_session_id": str(r["parent_session_id"]) if r.get("parent_session_id") else None,
            "topic": r.get("topic"),
        })
    return out


def list_public_shares(
    viewer_user_id: str, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Public shares sorted: accepted-follow authors first, then newest overall."""
    rows = query(
        """
        SELECT s.id, s.user_id, s.session_id, s.visibility, s.description,
               s.source_share_id, s.created_at,
               cs.title AS session_title, cs.session_type AS session_type, cs.topic AS session_topic
        FROM shares s
        JOIN chat_sessions cs ON cs.id = s.session_id
        LEFT JOIN user_follows uf
               ON uf.follower_id = %s
              AND uf.followed_id = s.user_id
              AND uf.status = 'accepted'
        WHERE s.visibility = 'public'
        ORDER BY
            (uf.follower_id IS NOT NULL) DESC,
            s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (viewer_user_id, limit, offset),
    )
    return _hydrate_share_rows(rows, viewer_user_id)


def list_private_shares(
    viewer_user_id: str, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Private wall: viewer's own shares + shares they saved via "Save to my wall".

    Own shares have is_own=True (delete button, no import).
    Saved shares have is_own=False (import button, unsave option).
    """
    rows = query(
        """
        SELECT s.id, s.user_id, s.session_id, s.visibility, s.description,
               s.source_share_id, s.created_at,
               cs.title AS session_title, cs.session_type AS session_type, cs.topic AS session_topic,
               (s.user_id = %s)                          AS is_own,
               (ws.user_id IS NOT NULL)                  AS is_saved
        FROM shares s
        JOIN chat_sessions cs ON cs.id = s.session_id
        LEFT JOIN wall_saves ws
               ON ws.share_id = s.id AND ws.user_id = %s
        WHERE s.user_id = %s
           OR ws.user_id = %s
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
        """,
        (viewer_user_id, viewer_user_id, viewer_user_id, viewer_user_id, limit, offset),
    )
    return _hydrate_share_rows(rows, viewer_user_id)


# ---------------------------------------------------------------------------
# Votes
# ---------------------------------------------------------------------------

def cast_vote(voter_user_id: str, share_id: str, vote: int) -> dict[str, Any]:
    """Upsert / clear a vote.

    vote = 1  -> upvote
    vote = -1 -> downvote
    vote = 0  -> remove existing vote
    """
    share = query_one(
        "SELECT user_id FROM shares WHERE id = %s",
        (share_id,),
    )
    if not share:
        raise ValueError("Share not found")

    if vote == 0:
        execute(
            "DELETE FROM share_votes WHERE share_id = %s AND user_id = %s",
            (share_id, voter_user_id),
        )
    elif vote in (1, -1):
        execute(
            """
            INSERT INTO share_votes (share_id, user_id, vote)
            VALUES (%s, %s, %s)
            ON CONFLICT (share_id, user_id) DO UPDATE SET vote = EXCLUDED.vote
            """,
            (share_id, voter_user_id, vote),
        )
    else:
        raise ValueError("vote must be -1, 0, or 1")

    tally = query_one(
        """
        SELECT
          COALESCE(SUM(CASE WHEN vote = 1  THEN 1 ELSE 0 END), 0) AS upvotes,
          COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) AS downvotes
        FROM share_votes WHERE share_id = %s
        """,
        (share_id,),
    ) or {}

    author_score = get_user_score(str(share["user_id"]))

    upvotes = int(tally.get("upvotes") or 0)
    downvotes = int(tally.get("downvotes") or 0)

    my_vote_val = vote if vote in (1, -1) else 0
    broadcast_event("vote_updated", {
        "share_id": str(share_id),
        "upvotes": upvotes,
        "downvotes": downvotes,
        "voter_user_id": str(voter_user_id),
        "my_vote": my_vote_val,
    })

    return {
        "upvotes": upvotes,
        "downvotes": downvotes,
        "my_vote": my_vote_val,
        "author_score": author_score["score"],
        "author_stars": author_score["stars"],
    }


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def _serialize_comment(row: dict) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "share_id": str(row["share_id"]) if "share_id" in row and row["share_id"] else None,
        "user_id": str(row["user_id"]),
        "author_name": row.get("author_name") or row.get("full_name") or "Unknown",
        "content": row["content"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "parent_comment_id": str(row["parent_comment_id"]) if row.get("parent_comment_id") else None,
    }


def add_comment(
    user_id: str,
    share_id: str,
    content: str,
    parent_comment_id: str | None = None,
) -> dict[str, Any]:
    """Insert comment or reply. Returns the created comment dict."""
    if not content or not content.strip():
        raise ValueError("content required")
    share = query_one("SELECT 1 FROM shares WHERE id = %s", (share_id,))
    if not share:
        raise ValueError("Share not found")
    if parent_comment_id:
        parent = query_one(
            "SELECT share_id FROM share_comments WHERE id = %s",
            (parent_comment_id,),
        )
        if not parent or str(parent["share_id"]) != str(share_id):
            raise ValueError("Invalid parent comment")
    row = execute_returning(
        """
        INSERT INTO share_comments (share_id, user_id, content, parent_comment_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, share_id, user_id, content, created_at, parent_comment_id
        """,
        (share_id, user_id, content.strip(), parent_comment_id),
    )
    author = query_one(
        "SELECT full_name FROM users WHERE id = %s",
        (user_id,),
    ) or {}
    row["author_name"] = author.get("full_name") or "You"
    comment = _serialize_comment(row)

    # Fan-out: notify every active SSE viewer that a new comment was posted.
    # Fire-and-forget — Redis failures must never break the HTTP response.
    broadcast_event(
        "comment_added",
        {"share_id": str(share_id), "comment": comment},
    )
    return comment


def list_comments(share_id: str) -> list[dict[str, Any]]:
    rows = query(
        """
        SELECT c.id, c.share_id, c.user_id, c.content, c.created_at,
               c.parent_comment_id, u.full_name AS author_name
        FROM share_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.share_id = %s
        ORDER BY c.created_at ASC
        """,
        (share_id,),
    )
    return [_serialize_comment(r) for r in rows]


def delete_comment(user_id: str, comment_id: str) -> None:
    row = query_one(
        "SELECT user_id, share_id FROM share_comments WHERE id = %s",
        (comment_id,),
    )
    if not row:
        raise ValueError("Comment not found")
    if str(row["user_id"]) != str(user_id):
        raise ValueError("Not authorised to delete this comment")
    execute("DELETE FROM share_comments WHERE id = %s", (comment_id,))
    # ON DELETE CASCADE removes replies; broadcast so all clients update live
    broadcast_event("comment_deleted", {
        "share_id": str(row["share_id"]),
        "comment_id": str(comment_id),
    })


# ---------------------------------------------------------------------------
# Wall saves (bookmark: "Save to my wall")
# ---------------------------------------------------------------------------

def save_to_wall(user_id: str, share_id: str) -> None:
    """Bookmark a public share to the viewer's private wall.

    Idempotent — inserting a duplicate is silently ignored.
    """
    share = query_one("SELECT user_id FROM shares WHERE id = %s", (share_id,))
    if not share:
        raise ValueError("Share not found")
    if str(share["user_id"]) == str(user_id):
        raise ValueError("Cannot save your own share")
    execute(
        """
        INSERT INTO wall_saves (user_id, share_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, share_id) DO NOTHING
        """,
        (user_id, share_id),
    )


def unsave_from_wall(user_id: str, share_id: str) -> None:
    """Remove a bookmark from the viewer's private wall."""
    execute(
        "DELETE FROM wall_saves WHERE user_id = %s AND share_id = %s",
        (user_id, share_id),
    )


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------

def follow_user(follower_id: str, followed_id: str) -> dict[str, str]:
    """Send a follow request.

    Idempotent — returns current status if a relationship already exists.
    """
    if str(follower_id) == str(followed_id):
        return {"status": "self"}
    existing = query_one(
        "SELECT status FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, followed_id),
    )
    if existing:
        return {"status": existing["status"]}
    execute(
        """
        INSERT INTO user_follows (follower_id, followed_id, status, requested_at)
        VALUES (%s, %s, 'pending', NOW())
        """,
        (follower_id, followed_id),
    )

    # Notify the followed user that someone is requesting to follow them.
    # Fire-and-forget — never break the HTTP response on Redis failure.
    requester = query_one(
        "SELECT id, full_name, username FROM users WHERE id = %s",
        (follower_id,),
    )
    if requester:
        publish_event(
            user_id=str(followed_id),
            event="follow_request_received",
            payload={
                "requester": {
                    "id": str(requester["id"]),
                    "full_name": requester.get("full_name"),
                    "username": requester.get("username"),
                }
            },
        )
    return {"status": "pending"}


def cancel_follow(follower_id: str, followed_id: str) -> None:
    """Cancel a pending request or remove an accepted follow."""
    execute(
        "DELETE FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, followed_id),
    )


def accept_follow_request(current_user_id: str, requester_id: str) -> None:
    """Accept an incoming follow request."""
    row = query_one(
        "SELECT status FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (requester_id, current_user_id),
    )
    if not row:
        raise ValueError("No pending request found")
    if row["status"] != "pending":
        raise ValueError("Request is not in pending state")
    execute(
        "UPDATE user_follows SET status = 'accepted' WHERE follower_id = %s AND followed_id = %s",
        (requester_id, current_user_id),
    )

    # Notify the original requester that their follow request was accepted.
    # Fire-and-forget — never break the HTTP response on Redis failure.
    accepter = query_one(
        "SELECT id, full_name, username FROM users WHERE id = %s",
        (current_user_id,),
    )
    if accepter:
        publish_event(
            user_id=str(requester_id),
            event="follow_accepted",
            payload={
                "accepted_by": {
                    "id": str(accepter["id"]),
                    "full_name": accepter.get("full_name"),
                    "username": accepter.get("username"),
                }
            },
        )


def reject_follow_request(current_user_id: str, requester_id: str) -> None:
    """Reject and delete an incoming follow request."""
    execute(
        "DELETE FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (requester_id, current_user_id),
    )


def get_pending_requests(user_id: str) -> list[dict[str, Any]]:
    """Return users who have sent a pending follow request to user_id."""
    rows = query(
        """
        SELECT u.id, u.full_name, u.username, uf.requested_at
        FROM user_follows uf
        JOIN users u ON u.id = uf.follower_id
        WHERE uf.followed_id = %s AND uf.status = 'pending'
        ORDER BY uf.requested_at ASC
        """,
        (user_id,),
    )
    return [
        {
            "id": str(r["id"]),
            "full_name": r["full_name"],
            "username": r["username"],
            "requested_at": r["requested_at"].isoformat() if r.get("requested_at") else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_profile(user_id: str, viewer_id: str) -> dict[str, Any]:
    """Returns user fields, score+stars, share/follower/following counts,
    is_following flag (whether viewer follows this user), and recent_shares (≤5)."""
    user_row = query_one(
        """
        SELECT id, username, email, full_name, created_at
        FROM users WHERE id = %s
        """,
        (user_id,),
    )
    if not user_row:
        raise ValueError("User not found")

    score_data = get_user_score(user_id)

    follower_count_row = query_one(
        "SELECT COUNT(*) AS cnt FROM user_follows WHERE followed_id = %s AND status = 'accepted'",
        (user_id,),
    ) or {}
    following_count_row = query_one(
        "SELECT COUNT(*) AS cnt FROM user_follows WHERE follower_id = %s AND status = 'accepted'",
        (user_id,),
    ) or {}
    is_following_row = query_one(
        "SELECT status FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (viewer_id, user_id),
    )
    pending_requests = (
        get_pending_requests(user_id) if str(viewer_id) == str(user_id) else []
    )

    recent_share_rows = query(
        """
        SELECT s.id, s.user_id, s.session_id, s.visibility, s.description,
               s.source_share_id, s.created_at,
               cs.title AS session_title, cs.session_type AS session_type, cs.topic AS session_topic
        FROM shares s
        JOIN chat_sessions cs ON cs.id = s.session_id
        WHERE s.user_id = %s
        ORDER BY s.created_at DESC
        LIMIT 3
        """,
        (user_id,),
    )
    recent_shares = _hydrate_share_rows(recent_share_rows, viewer_id)

    return {
        "id": str(user_row["id"]),
        "username": user_row["username"],
        "email": user_row["email"],
        "full_name": user_row["full_name"],
        "created_at": user_row["created_at"].isoformat() if user_row.get("created_at") else None,
        "score": score_data["score"],
        "stars": score_data["stars"],
        "upvotes": score_data["upvotes"],
        "downvotes": score_data["downvotes"],
        "share_count": score_data["share_count"],
        "follower_count": int(follower_count_row.get("cnt") or 0),
        "following_count": int(following_count_row.get("cnt") or 0),
        "is_following": (
            is_following_row is not None
            and is_following_row.get("status") == "accepted"
            and str(viewer_id) != str(user_id)
        ),
        "follow_request_sent": (
            is_following_row is not None
            and is_following_row.get("status") == "pending"
            and str(viewer_id) != str(user_id)
        ),
        "is_self": str(viewer_id) == str(user_id),
        "pending_requests": pending_requests,
        "recent_shares": recent_shares,
    }


# ---------------------------------------------------------------------------
# Preview — read-only modal showing a share's full session tree + content
# ---------------------------------------------------------------------------

def get_share_preview(share_id: str) -> dict[str, Any]:
    """Return share metadata + tree + first session's content (messages or quiz)."""
    share = query_one(
        """
        SELECT s.id, s.user_id, s.session_id, s.visibility, s.description, s.created_at,
               cs.title AS session_title, cs.session_type, cs.topic,
               u.full_name AS author_name, u.username AS author_username
        FROM shares s
        JOIN chat_sessions cs ON cs.id = s.session_id
        JOIN users u ON u.id = s.user_id
        WHERE s.id = %s
        """,
        (share_id,),
    )
    if not share:
        raise ValueError("Share not found")

    tree = _fetch_session_tree(str(share["session_id"]))
    first_session_id = tree[0]["id"] if tree else str(share["session_id"])
    first_content = get_session_preview_content(str(share["session_id"]), first_session_id)

    return {
        "id": str(share["id"]),
        "session_id": str(share["session_id"]),
        "session_title": share["session_title"] or "Untitled",
        "session_type": share["session_type"],
        "author_name": share["author_name"],
        "author_username": share["author_username"],
        "description": share.get("description"),
        "tree": tree,
        "initial_session_id": first_session_id,
        "initial_content": first_content,
    }


def get_session_preview_content(share_session_id: str, session_id: str) -> dict[str, Any]:
    """Content for ONE session in a shared tree.

    Non-quiz: returns messages list.
    Quiz: returns questions (no user answers) — purely ephemeral, never saved.
    """
    session = query_one(
        "SELECT id, title, session_type, topic, linked_attempt_id "
        "FROM chat_sessions WHERE id = %s",
        (session_id,),
    )
    if not session:
        return {"type": "empty", "messages": [], "questions": []}

    session_type = session.get("session_type") or "regular"

    if session_type == "quiz" and session.get("linked_attempt_id"):
        attempt = query_one(
            "SELECT questions FROM mcq_attempts WHERE id = %s",
            (session["linked_attempt_id"],),
        )
        questions: list[dict[str, Any]] = []
        if attempt and attempt.get("questions"):
            raw_qs = attempt["questions"]
            if isinstance(raw_qs, str):
                import json as _json
                raw_qs = _json.loads(raw_qs)
            questions = [
                {
                    "id": q.get("id", str(i)),
                    "text": q.get("text", ""),
                    "options": q.get("options", []),
                    "correct": q.get("correct", 0),
                    "topic": q.get("topic", ""),
                }
                for i, q in enumerate(raw_qs)
            ]
        return {
            "type": "quiz",
            "title": session.get("title") or "Knowledge Check",
            "questions": questions,
        }

    # Regular / learn_more / news_discussion: return messages
    messages = query(
        """
        SELECT role, content, created_at
        FROM session_messages
        WHERE session_id = %s
        ORDER BY created_at ASC
        """,
        (session_id,),
    )
    return {
        "type": "messages",
        "title": session.get("title") or session.get("topic") or "Session",
        "session_type": session_type,
        "messages": [
            {
                "role": m["role"],
                "content": _parse_message_content(m["content"]),
                "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
            }
            for m in messages
        ],
    }


# ---------------------------------------------------------------------------
# Import — deep-copy a shared session tree into the importing user's account
# ---------------------------------------------------------------------------

def import_share(user_id: str, share_id: str) -> dict[str, Any]:
    """Deep-copy the shared session tree (sessions + messages) into user's account.

    Returns dict with new_session_id and title.
    """
    from uuid import uuid4

    from backend.core.db import get_pool

    share = query_one(
        "SELECT user_id, session_id FROM shares WHERE id = %s",
        (share_id,),
    )
    if not share:
        raise ValueError("Share not found")
    if str(share["user_id"]) == str(user_id):
        raise ValueError("Cannot import your own share")

    # Prevent duplicate imports
    existing = query_one(
        """SELECT id FROM chat_sessions
           WHERE user_id = %s AND imported_from_share_id = %s AND depth_level = 0""",
        (user_id, share_id),
    )
    if existing:
        raise ValueError("Already imported — check your Root section")

    original_root_id = str(share["session_id"])
    sessions = query(
        """
        SELECT id, title, session_type, parent_session_id, root_session_id,
               depth_level, topic, news_article_id
        FROM chat_sessions
        WHERE root_session_id = %s OR (id = %s AND root_session_id IS NULL)
        ORDER BY depth_level ASC, created_at ASC
        """,
        (original_root_id, original_root_id),
    )
    if not sessions:
        raise ValueError("No sessions found in shared root")

    id_map: dict[str, str] = {}  # old_id -> new_id
    new_root_id: str | None = None

    with get_pool().connection() as conn:
        with conn.transaction():
            for session in sessions:
                old_id = str(session["id"])
                new_id = str(uuid4())
                id_map[old_id] = new_id
                depth = int(session["depth_level"] or 0)

                new_parent = (
                    id_map.get(str(session["parent_session_id"]))
                    if session.get("parent_session_id") else None
                )
                new_root = new_root_id if depth > 0 else None
                imported_from = share_id if depth == 0 else None

                conn.execute(
                    """
                    INSERT INTO chat_sessions
                        (id, user_id, thread_id, title, session_type,
                         parent_session_id, root_session_id, depth_level,
                         topic, news_article_id, imported_from_share_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (new_id, user_id, str(uuid4()), session.get("title"),
                     session["session_type"], new_parent, new_root, depth,
                     session.get("topic"), session.get("news_article_id"),
                     imported_from),
                )
                if depth == 0:
                    new_root_id = new_id

                # Copy messages for non-quiz sessions
                if session["session_type"] != "quiz":
                    msgs = conn.execute(
                        "SELECT role, content, created_at FROM session_messages "
                        "WHERE session_id = %s ORDER BY created_at",
                        (old_id,),
                    ).fetchall()
                    for msg in msgs:
                        conn.execute(
                            "INSERT INTO session_messages "
                            "(session_id, role, content, created_at) "
                            "VALUES (%s, %s, %s, %s)",
                            (new_id, msg["role"], msg["content"], msg["created_at"]),
                        )

    return {
        "new_session_id": new_root_id,
        "title": sessions[0].get("title") or "Imported Root",
    }
