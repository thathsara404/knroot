"""Unit tests for the community wall — routes and pure service functions."""
import json
import pytest

WALL_SVC = "backend.api.wall.service"

# ===========================================================================
# Pure service functions — no DB, no HTTP
# ===========================================================================


class TestUpvotesToStars:
    def _fn(self):
        from backend.api.wall.service import upvotes_to_stars
        return upvotes_to_stars

    def test_zero_upvotes_gives_zero_stars(self):
        assert self._fn()(0) == 0.0

    def test_negative_upvotes_gives_zero_stars(self):
        assert self._fn()(-100) == 0.0

    def test_below_first_threshold_still_zero(self):
        assert self._fn()(999) == 0.0

    def test_at_first_threshold_gives_one_star(self):
        assert self._fn()(1_000) == 1.0

    def test_between_first_and_second_threshold(self):
        assert self._fn()(5_000) == 1.0

    def test_at_second_threshold_gives_two_stars(self):
        assert self._fn()(10_000) == 2.0

    def test_at_third_threshold_gives_three_stars(self):
        assert self._fn()(100_000) == 3.0

    def test_beyond_last_threshold_gives_five_stars(self):
        assert self._fn()(10_000_001) == 5.0

    def test_return_type_is_float(self):
        result = self._fn()(500)
        assert isinstance(result, float)


class TestEvaluateReshareEvents:
    def _call(
        self, sharer_id="userA", source_owner_id="userB",
        snapshot_upvotes=0, snapshot_downvotes=0, already_has_bonus=False,
    ):
        from backend.api.wall.service import _evaluate_reshare_events
        return _evaluate_reshare_events(
            sharer_id, source_owner_id,
            snapshot_upvotes, snapshot_downvotes, already_has_bonus,
        )

    def test_first_reshare_earns_bonus(self):
        events = self._call(already_has_bonus=False)
        assert any(e["reason"] == "reshare_bonus" for e in events)

    def test_second_reshare_no_bonus(self):
        events = self._call(already_has_bonus=True)
        assert not any(e["reason"] == "reshare_bonus" for e in events)

    def test_resharing_own_post_no_bonus(self):
        events = self._call(sharer_id="userA", source_owner_id="userA", already_has_bonus=False)
        assert not any(e["reason"] == "reshare_bonus" for e in events)

    def test_toxic_threshold_exactly_triggers_penalty(self):
        events = self._call(snapshot_downvotes=50)  # threshold is 50
        assert any(e["reason"] == "toxic_penalty" for e in events)

    def test_below_toxic_threshold_no_penalty(self):
        events = self._call(snapshot_downvotes=49)
        assert not any(e["reason"] == "toxic_penalty" for e in events)

    def test_own_toxic_post_still_gets_penalty(self):
        events = self._call(sharer_id="userA", source_owner_id="userA", snapshot_downvotes=50)
        assert any(e["reason"] == "toxic_penalty" for e in events)

    def test_clean_reshare_of_own_post_yields_no_events(self):
        events = self._call(sharer_id="A", source_owner_id="A", snapshot_downvotes=0)
        assert events == []

    def test_bonus_event_has_correct_points(self):
        from backend.api.wall.service import SCORING
        events = self._call()
        bonus = next(e for e in events if e["reason"] == "reshare_bonus")
        assert bonus["points"] == SCORING["reshare_bonus_pts"]

    def test_penalty_event_has_correct_points(self):
        from backend.api.wall.service import SCORING
        events = self._call(snapshot_downvotes=50)
        penalty = next(e for e in events if e["reason"] == "toxic_penalty")
        assert penalty["points"] == SCORING["toxic_penalty_pts"]

    def test_event_snapshots_are_recorded(self):
        events = self._call(snapshot_upvotes=5, snapshot_downvotes=0)
        for e in events:
            assert e["snapshot_upvotes"] == 5
            assert e["snapshot_downvotes"] == 0

    def test_both_bonus_and_penalty_can_occur_together(self):
        events = self._call(snapshot_downvotes=50, already_has_bonus=False)
        reasons = {e["reason"] for e in events}
        assert "reshare_bonus" in reasons
        assert "toxic_penalty" in reasons


class TestParseMessageContent:
    def _call(self, content):
        from backend.api.wall.service import _parse_message_content
        return _parse_message_content(content)

    def test_none_returns_empty_text(self):
        assert self._call(None) == {"type": "text", "text": ""}

    def test_empty_string_returns_empty_text(self):
        assert self._call("") == {"type": "text", "text": ""}

    def test_plain_string_returns_text_type(self):
        result = self._call("Hello world")
        assert result["type"] == "text"
        assert result["text"] == "Hello world"

    def test_valid_sectioned_json_parsed(self):
        payload = json.dumps({"type": "sectioned", "intro": "Hi", "sections": [], "outro": ""})
        result = self._call(payload)
        assert result["type"] == "sectioned"
        assert result["intro"] == "Hi"

    def test_code_fenced_json_is_unwrapped(self):
        payload = {"type": "sectioned", "intro": "Fenced", "sections": [], "outro": ""}
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        result = self._call(fenced)
        assert result["type"] == "sectioned"
        assert result["intro"] == "Fenced"

    def test_non_sectioned_json_returns_text(self):
        result = self._call('{"type": "other", "data": 1}')
        assert result["type"] == "text"

    def test_malformed_json_returns_text(self):
        result = self._call("{not: valid json")
        assert result["type"] == "text"

    def test_whitespace_only_returns_text(self):
        result = self._call("   ")
        assert result["type"] == "text"


# ===========================================================================
# Route auth guards
# ===========================================================================

def test_public_wall_partial_requires_auth(client):
    assert client.get("/wall/public/partial").status_code in (302, 401)


def test_private_wall_partial_requires_auth(client):
    assert client.get("/wall/private/partial").status_code in (302, 401)


def test_profile_partial_requires_auth(client):
    assert client.get("/wall/profile/partial").status_code in (302, 401)


def test_score_partial_requires_auth(client):
    assert client.get("/wall/score/partial").status_code in (302, 401)


def test_create_share_requires_auth(client):
    assert client.post("/wall/shares", json={"session_id": "s"}).status_code == 401


def test_delete_share_requires_auth(client):
    assert client.delete("/wall/shares/share-1").status_code == 401


def test_save_share_requires_auth(client):
    assert client.post("/wall/shares/share-1/save").status_code == 401


def test_unsave_share_requires_auth(client):
    assert client.delete("/wall/shares/share-1/save").status_code == 401


def test_vote_requires_auth(client):
    assert client.post("/wall/shares/share-1/vote", json={"vote": 1}).status_code == 401


def test_add_comment_requires_auth(client):
    assert client.post("/wall/shares/share-1/comments", json={"content": "Hi"}).status_code == 401


def test_list_comments_requires_auth(client):
    assert client.get("/wall/shares/share-1/comments").status_code == 401


def test_delete_comment_requires_auth(client):
    assert client.delete("/wall/comments/comment-1").status_code == 401


def test_follow_requires_auth(client):
    assert client.post("/wall/follow/user-2").status_code == 401


def test_unfollow_requires_auth(client):
    assert client.delete("/wall/follow/user-2").status_code == 401


def test_accept_follow_requires_auth(client):
    assert client.post("/wall/follow-requests/user-2/accept").status_code == 401


def test_reject_follow_requires_auth(client):
    assert client.post("/wall/follow-requests/user-2/reject").status_code == 401


def test_follow_count_requires_auth(client):
    assert client.get("/wall/follow-requests/count").status_code == 401


def test_preview_partial_requires_auth(client):
    assert client.get("/wall/shares/share-1/preview/partial").status_code in (302, 401)


def test_session_preview_partial_requires_auth(client):
    assert client.get("/wall/shares/share-1/sessions/sess-1/preview/partial").status_code in (302, 401)


def test_import_share_requires_auth(client):
    assert client.post("/wall/shares/share-1/import").status_code == 401


# ===========================================================================
# Fixtures shared across partial + CRUD tests
# ===========================================================================

_PROFILE = {
    "id": "user-uuid-1234",
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "created_at": "2026-01-01T00:00:00+00:00",
    "score": 0,
    "stars": 0.0,
    "upvotes": 0,
    "downvotes": 0,
    "share_count": 0,
    "follower_count": 2,
    "following_count": 3,
    "is_following": False,
    "follow_request_sent": False,
    "is_self": True,
    "pending_requests": [],
    "recent_shares": [],
}

_SCORE = {"score": 0, "stars": 0.0, "upvotes": 0, "downvotes": 0, "share_count": 0}

_PREVIEW = {
    "id": "share-1",
    "session_id": "sess-1",
    "session_title": "Learning Roots",
    "session_type": "regular",
    "author_name": "Test User",
    "author_username": "testuser",
    "description": "A test share",
    "tree": [
        {"id": "sess-1", "title": "Learning Roots", "session_type": "regular",
         "depth_level": 0, "parent_session_id": None, "topic": None},
    ],
    "initial_session_id": "sess-1",
    "initial_content": {
        "type": "messages", "messages": [], "session_type": "regular",
        "article_link": "", "article_title": "", "title": "Learning Roots",
    },
}


# ===========================================================================
# Partial route rendering
# ===========================================================================

def test_public_wall_partial_empty_state(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.list_public_shares", return_value=[])
    resp = authed_client.get("/wall/public/partial")
    assert resp.status_code == 200
    assert b"No shares yet" in resp.data


def test_private_wall_partial_empty_state(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.list_private_shares", return_value=[])
    resp = authed_client.get("/wall/private/partial")
    assert resp.status_code == 200
    assert b"Your wall is empty" in resp.data


def test_profile_partial_renders_username(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_profile", return_value=_PROFILE)
    resp = authed_client.get("/wall/profile/partial")
    assert resp.status_code == 200
    assert b"testuser" in resp.data


def test_profile_partial_renders_full_name(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_profile", return_value=_PROFILE)
    resp = authed_client.get("/wall/profile/partial")
    assert b"Test User" in resp.data


def test_score_partial_renders_header(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_user_score", return_value=_SCORE)
    mocker.patch(f"{WALL_SVC}.get_profile", return_value=_PROFILE)
    resp = authed_client.get("/wall/score/partial")
    assert resp.status_code == 200
    assert b"Your Score" in resp.data


def test_score_partial_shows_star_rating(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_user_score", return_value=_SCORE)
    mocker.patch(f"{WALL_SVC}.get_profile", return_value=_PROFILE)
    resp = authed_client.get("/wall/score/partial")
    assert b"0.0" in resp.data


def test_public_wall_partial_respects_offset(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.list_public_shares", return_value=[])
    authed_client.get("/wall/public/partial?offset=20")
    mock.assert_called_once_with("user-uuid-1234", limit=20, offset=20)


def test_public_wall_partial_default_offset_zero(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.list_public_shares", return_value=[])
    authed_client.get("/wall/public/partial")
    mock.assert_called_once_with("user-uuid-1234", limit=20, offset=0)


# ===========================================================================
# Share CRUD
# ===========================================================================

def test_create_share_missing_session_id_returns_400(authed_client):
    resp = authed_client.post("/wall/shares", json={})
    assert resp.status_code == 400
    assert "session_id" in resp.get_json().get("error", "")


def test_create_share_success_returns_201(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.create_share", return_value={
        "id": "share-1", "session_id": "sess-1", "visibility": "public",
    })
    resp = authed_client.post("/wall/shares", json={"session_id": "sess-1"})
    assert resp.status_code == 201
    assert resp.get_json()["id"] == "share-1"


def test_create_share_duplicate_returns_422(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.create_share", side_effect=ValueError("already been shared"))
    resp = authed_client.post("/wall/shares", json={"session_id": "sess-1"})
    assert resp.status_code == 422


def test_create_share_bad_session_returns_422(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.create_share", side_effect=ValueError("Session not found"))
    resp = authed_client.post("/wall/shares", json={"session_id": "bad"})
    assert resp.status_code == 422


def test_create_share_invalid_visibility_normalised_to_public(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.create_share", return_value={"id": "share-1"})
    authed_client.post("/wall/shares", json={"session_id": "sess-1", "visibility": "secret"})
    call_visibility = mock.call_args.args[2] if mock.call_args.args else mock.call_args.kwargs.get("visibility")
    assert call_visibility == "public"


def test_create_share_friends_visibility_allowed(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.create_share", return_value={"id": "share-1"})
    authed_client.post("/wall/shares", json={"session_id": "sess-1", "visibility": "friends"})
    call_visibility = mock.call_args.args[2] if mock.call_args.args else mock.call_args.kwargs.get("visibility")
    assert call_visibility == "friends"


def test_delete_share_success_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.delete_share", return_value=None)
    resp = authed_client.delete("/wall/shares/share-1")
    assert resp.status_code == 204


def test_delete_share_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.delete_share", side_effect=ValueError("Share not found"))
    resp = authed_client.delete("/wall/shares/share-1")
    assert resp.status_code == 404


def test_delete_share_not_owner_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.delete_share", side_effect=ValueError("Not authorised"))
    resp = authed_client.delete("/wall/shares/share-1")
    assert resp.status_code == 404


# ===========================================================================
# Save / Unsave
# ===========================================================================

def test_save_share_success_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.save_to_wall", return_value=None)
    resp = authed_client.post("/wall/shares/share-1/save")
    assert resp.status_code == 204


def test_save_share_not_found_returns_422(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.save_to_wall", side_effect=ValueError("Share not found"))
    resp = authed_client.post("/wall/shares/share-1/save")
    assert resp.status_code == 422


def test_unsave_share_success_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.unsave_from_wall", return_value=None)
    resp = authed_client.delete("/wall/shares/share-1/save")
    assert resp.status_code == 204


# ===========================================================================
# Votes
# ===========================================================================

def test_vote_invalid_value_returns_400(authed_client):
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": 5})
    assert resp.status_code == 400


def test_vote_value_minus_two_returns_400(authed_client):
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": -2})
    assert resp.status_code == 400


def test_vote_upvote_returns_200(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.cast_vote", return_value={"upvotes": 1, "downvotes": 0, "user_vote": 1})
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": 1})
    assert resp.status_code == 200
    assert resp.get_json()["user_vote"] == 1


def test_vote_downvote_returns_200(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.cast_vote", return_value={"upvotes": 0, "downvotes": 1, "user_vote": -1})
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": -1})
    assert resp.status_code == 200
    assert resp.get_json()["user_vote"] == -1


def test_vote_remove_returns_200(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.cast_vote", return_value={"upvotes": 0, "downvotes": 0, "user_vote": 0})
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": 0})
    assert resp.status_code == 200


def test_vote_share_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.cast_vote", side_effect=ValueError("Share not found"))
    resp = authed_client.post("/wall/shares/share-1/vote", json={"vote": 1})
    assert resp.status_code == 404


# ===========================================================================
# Comments
# ===========================================================================

def test_add_comment_missing_content_returns_400(authed_client):
    resp = authed_client.post("/wall/shares/share-1/comments", json={})
    assert resp.status_code == 400


def test_add_comment_whitespace_content_returns_400(authed_client):
    resp = authed_client.post("/wall/shares/share-1/comments", json={"content": "   "})
    assert resp.status_code == 400


def test_add_comment_success_returns_201(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.add_comment", return_value={"id": "comment-1", "content": "Great!"})
    resp = authed_client.post("/wall/shares/share-1/comments", json={"content": "Great!"})
    assert resp.status_code == 201
    assert resp.get_json()["id"] == "comment-1"


def test_add_comment_with_parent_id(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.add_comment", return_value={"id": "comment-2"})
    authed_client.post("/wall/shares/share-1/comments", json={
        "content": "Reply!", "parent_comment_id": "comment-1",
    })
    call_parent = mock.call_args.args[3] if len(mock.call_args.args) >= 4 else mock.call_args.kwargs.get("parent_comment_id")
    assert call_parent == "comment-1"


def test_add_comment_share_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.add_comment", side_effect=ValueError("Share not found"))
    resp = authed_client.post("/wall/shares/share-1/comments", json={"content": "Hi"})
    assert resp.status_code == 404


def test_list_comments_returns_200_list(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.list_comments", return_value=[{"id": "c1", "content": "Nice"}])
    resp = authed_client.get("/wall/shares/share-1/comments")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)
    assert resp.get_json()[0]["id"] == "c1"


def test_list_comments_empty_returns_empty_list(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.list_comments", return_value=[])
    resp = authed_client.get("/wall/shares/share-1/comments")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_delete_comment_success_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.delete_comment", return_value=None)
    resp = authed_client.delete("/wall/comments/comment-1")
    assert resp.status_code == 204


def test_delete_comment_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.delete_comment", side_effect=ValueError("Not found"))
    resp = authed_client.delete("/wall/comments/comment-1")
    assert resp.status_code == 404


# ===========================================================================
# Follow system
# ===========================================================================

def test_follow_user_returns_200_with_status(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.follow_user", return_value={"status": "pending"})
    resp = authed_client.post("/wall/follow/user-2")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"


def test_unfollow_user_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.cancel_follow", return_value=None)
    resp = authed_client.delete("/wall/follow/user-2")
    assert resp.status_code == 204


def test_accept_follow_request_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.accept_follow_request", return_value=None)
    resp = authed_client.post("/wall/follow-requests/user-2/accept")
    assert resp.status_code == 204


def test_accept_follow_request_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.accept_follow_request", side_effect=ValueError("No pending request"))
    resp = authed_client.post("/wall/follow-requests/user-2/accept")
    assert resp.status_code == 404


def test_reject_follow_request_returns_204(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.reject_follow_request", return_value=None)
    resp = authed_client.post("/wall/follow-requests/user-2/reject")
    assert resp.status_code == 204


def test_follow_count_returns_json_count(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_pending_requests", return_value=[{"id": "u1"}, {"id": "u2"}])
    resp = authed_client.get("/wall/follow-requests/count")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 2


def test_follow_count_zero_when_empty(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_pending_requests", return_value=[])
    resp = authed_client.get("/wall/follow-requests/count")
    assert resp.get_json()["count"] == 0


# ===========================================================================
# Preview partials
# ===========================================================================

def test_preview_partial_renders_session_title(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    resp = authed_client.get("/wall/shares/share-1/preview/partial")
    assert resp.status_code == 200
    assert b"Learning Roots" in resp.data


def test_preview_partial_renders_author(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    resp = authed_client.get("/wall/shares/share-1/preview/partial")
    assert b"testuser" in resp.data


def test_preview_partial_not_found_returns_404(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", side_effect=ValueError("Share not found"))
    resp = authed_client.get("/wall/shares/share-1/preview/partial")
    assert resp.status_code == 404


def test_session_preview_renders_no_messages_state(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value={
        "type": "messages", "messages": [], "session_type": "regular",
        "article_link": "", "article_title": "", "title": "Learning Roots",
    })
    resp = authed_client.get("/wall/shares/share-1/sessions/sess-1/preview/partial")
    assert resp.status_code == 200
    assert b"No messages" in resp.data


def test_session_preview_renders_quiz_questions(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value={
        "type": "quiz",
        "title": "Knowledge Check",
        "questions": [
            {"id": "q1", "text": "What is gradient descent?",
             "options": ["A", "B", "C", "D"], "correct": 0, "topic": "ML"},
        ],
    })
    resp = authed_client.get("/wall/shares/share-1/sessions/sess-1/preview/partial")
    assert resp.status_code == 200
    assert b"Knowledge Check" in resp.data
    assert b"gradient descent" in resp.data


def test_session_preview_quiz_no_questions_shows_placeholder(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value={
        "type": "quiz", "title": "Quiz: ML Basics", "questions": [],
    })
    resp = authed_client.get("/wall/shares/share-1/sessions/sess-1/preview/partial")
    assert resp.status_code == 200
    assert b"not available" in resp.data


# ===========================================================================
# Import share
# ===========================================================================

def test_import_share_success_returns_201(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.import_share", return_value={"sessions_imported": 3})
    resp = authed_client.post("/wall/shares/share-1/import")
    assert resp.status_code == 201
    assert resp.get_json()["sessions_imported"] == 3


def test_import_share_error_returns_422(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.import_share", side_effect=ValueError("Already imported"))
    resp = authed_client.post("/wall/shares/share-1/import")
    assert resp.status_code == 422


# ===========================================================================
# get_session_preview_content — unit tests of the service function
# ===========================================================================

def test_preview_content_quiz_with_linked_attempt(mocker):
    """linked_attempt_id present: fetches questions directly."""
    questions = [
        {"id": "q1", "text": "What is backprop?",
         "options": ["A", "B", "C", "D"], "correct": 0, "topic": "ML"},
    ]
    mocker.patch("backend.api.wall.service.query_one", side_effect=[
        {"id": "sess-1", "title": "Quiz", "session_type": "quiz",
         "topic": None, "linked_attempt_id": "attempt-1", "parent_session_id": "sess-0"},
        {"questions": json.dumps(questions)},
    ])
    mocker.patch("backend.api.wall.service.execute")

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-0", "sess-1")
    assert result["type"] == "quiz"
    assert len(result["questions"]) == 1
    assert result["questions"][0]["text"] == "What is backprop?"


def test_preview_content_quiz_fallback_via_parent(mocker):
    """linked_attempt_id is None: falls back to parent_session_id lookup."""
    questions = [
        {"id": "q2", "text": "Explain attention mechanism clearly.",
         "options": ["A", "B", "C", "D"], "correct": 1, "topic": "Transformers"},
    ]
    mocker.patch("backend.api.wall.service.query_one", side_effect=[
        # 1. session row — no linked_attempt_id
        {"id": "sess-1", "title": "Quiz", "session_type": "quiz",
         "topic": None, "linked_attempt_id": None, "parent_session_id": "sess-0"},
        # 2. fallback: find attempt via parent_session_id
        {"id": "attempt-fallback"},
        # 3. fetch questions for that attempt
        {"questions": json.dumps(questions)},
    ])
    mocker.patch("backend.api.wall.service.execute")  # self-heal UPDATE

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-0", "sess-1")
    assert result["type"] == "quiz"
    assert len(result["questions"]) == 1


def test_preview_content_quiz_no_parent_no_attempt(mocker):
    """No linked_attempt_id and no parent: returns empty quiz."""
    mocker.patch("backend.api.wall.service.query_one", side_effect=[
        {"id": "sess-1", "title": "Quiz", "session_type": "quiz",
         "topic": None, "linked_attempt_id": None, "parent_session_id": None},
    ])
    mocker.patch("backend.api.wall.service.execute")

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-0", "sess-1")
    assert result["type"] == "quiz"
    assert result["questions"] == []


def test_preview_content_regular_returns_messages(mocker):
    mocker.patch("backend.api.wall.service.query_one", return_value={
        "id": "sess-1", "title": "My Session", "session_type": "regular",
        "topic": None, "linked_attempt_id": None, "parent_session_id": None,
    })
    mocker.patch("backend.api.wall.service.query", return_value=[
        {"role": "user", "content": "Hello", "created_at": None},
        {"role": "assistant", "content": "World", "created_at": None},
    ])

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-1", "sess-1")
    assert result["type"] == "messages"
    assert len(result["messages"]) == 2


def test_preview_content_session_not_found_returns_empty(mocker):
    mocker.patch("backend.api.wall.service.query_one", return_value=None)

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-0", "bad-id")
    assert result["type"] == "empty"


def test_preview_content_news_discussion_sets_article_link(mocker):
    mocker.patch("backend.api.wall.service.query_one", return_value={
        "id": "sess-1", "title": "AI Article", "session_type": "news_discussion",
        "topic": "https://example.com/article", "linked_attempt_id": None, "parent_session_id": None,
    })
    mocker.patch("backend.api.wall.service.query", return_value=[])

    from backend.api.wall.service import get_session_preview_content
    result = get_session_preview_content("sess-1", "sess-1")
    assert result["article_link"] == "https://example.com/article"
    assert result["article_title"] == "AI Article"
