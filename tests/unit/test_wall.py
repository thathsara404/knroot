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


# ===========================================================================
# _parse_message_content — fence exception path (lines 25-26)
# ===========================================================================

def test_parse_message_content_fence_without_newline_does_not_raise():
    from backend.api.wall.service import _parse_message_content
    # "```" with no newline — split("\n", 1)[1] would raise IndexError, caught by except
    result = _parse_message_content("```")
    assert result["type"] == "text"
    assert result["text"] == "```"


# ===========================================================================
# get_user_score — DB-backed function (lines 106-125)
# ===========================================================================

class TestGetUserScore:
    def test_returns_all_fields(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={
            "score": 150, "upvotes": 20, "downvotes": 5, "share_count": 3,
        })
        from backend.api.wall.service import get_user_score
        result = get_user_score("user-1")
        assert result["score"] == 150
        assert result["upvotes"] == 20
        assert result["downvotes"] == 5
        assert result["share_count"] == 3

    def test_stars_computed_from_upvotes(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={
            "score": 0, "upvotes": 5000, "downvotes": 0, "share_count": 1,
        })
        from backend.api.wall.service import get_user_score
        result = get_user_score("user-1")
        assert result["stars"] == 1.0  # 5000 upvotes → 1 star

    def test_none_row_returns_zeros(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import get_user_score
        result = get_user_score("user-1")
        assert result["score"] == 0
        assert result["upvotes"] == 0
        assert result["stars"] == 0.0

    def test_null_score_field_coerced_to_zero(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={
            "score": None, "upvotes": None, "downvotes": None, "share_count": None,
        })
        from backend.api.wall.service import get_user_score
        result = get_user_score("user-1")
        assert result["score"] == 0


# ===========================================================================
# delete_share — service function (lines 236-244)
# ===========================================================================

class TestDeleteShareService:
    def test_raises_when_share_not_found(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import delete_share
        with pytest.raises(ValueError, match="not found"):
            delete_share("user-1", "share-1")

    def test_raises_when_not_owner(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"user_id": "other-user"})
        from backend.api.wall.service import delete_share
        with pytest.raises(ValueError, match="authorised"):
            delete_share("user-1", "share-1")

    def test_deletes_share_when_owner(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"user_id": "user-1"})
        mock_execute = mocker.patch("backend.api.wall.service.execute")
        from backend.api.wall.service import delete_share
        delete_share("user-1", "share-1")
        mock_execute.assert_called_once()


# ===========================================================================
# _serialize_share — pure helper (lines 253-259)
# ===========================================================================

class TestSerializeShare:
    def test_stringifies_uuid_fields(self):
        import uuid
        from backend.api.wall.service import _serialize_share
        share_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        row = {"id": share_id, "user_id": "u1", "session_id": None, "source_share_id": None}
        result = _serialize_share(row)
        assert result["id"] == "12345678-1234-5678-1234-567812345678"

    def test_stringifies_created_at_datetime(self):
        from datetime import datetime, timezone
        from backend.api.wall.service import _serialize_share
        dt = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
        row = {"id": "s1", "user_id": "u1", "created_at": dt, "session_id": None, "source_share_id": None}
        result = _serialize_share(row)
        assert "2026-05-15" in result["created_at"]

    def test_none_uuid_fields_stay_none(self):
        from backend.api.wall.service import _serialize_share
        row = {"id": "s1", "user_id": "u1", "session_id": None, "source_share_id": None}
        result = _serialize_share(row)
        assert result["session_id"] is None
        assert result["source_share_id"] is None

    def test_returns_copy_not_mutating_original(self):
        from backend.api.wall.service import _serialize_share
        original_row = {"id": "s1", "user_id": "u1", "session_id": None, "source_share_id": None}
        row_copy = dict(original_row)
        _serialize_share(original_row)
        assert original_row == row_copy


# ===========================================================================
# wall/routes.py — invalid offset falls back to 0 (lines 20-21)
# ===========================================================================

def test_public_wall_partial_invalid_offset_defaults_to_zero(authed_client, mocker):
    mock = mocker.patch(f"{WALL_SVC}.list_public_shares", return_value=[])
    authed_client.get("/wall/public/partial?offset=notanumber")
    mock.assert_called_once_with("user-uuid-1234", limit=20, offset=0)


# ===========================================================================
# create_share service (lines 145-231)
# ===========================================================================

class TestCreateShareService:
    _DT = __import__("datetime").datetime(2026, 1, 1,
                      tzinfo=__import__("datetime").timezone.utc)
    _BASE_ROW = {
        "id": "share-1", "user_id": "user-1", "session_id": "sess-1",
        "visibility": "public", "description": "desc", "source_share_id": None,
        "created_at": _DT,
    }

    def test_session_not_owned_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import create_share
        with pytest.raises(ValueError, match="Session not found"):
            create_share("user-1", "sess-1", "public", "desc")

    def test_already_shared_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "sess-1"},           # owns session
            {"id": "existing-share"},   # already shared
        ])
        from backend.api.wall.service import create_share
        with pytest.raises(ValueError, match="already been shared"):
            create_share("user-1", "sess-1", "public", "desc")

    def test_invalid_visibility_normalised_to_public(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "sess-1"}, None,
            {"imported_from_share_id": None},
            {"full_name": "Alice", "username": "alice"},
        ])
        mock_er = mocker.patch("backend.api.wall.service.execute_returning", return_value=self._BASE_ROW)
        mocker.patch("backend.api.wall.service.broadcast_event")
        from backend.api.wall.service import create_share
        create_share("user-1", "sess-1", "secret", "desc")
        call_args = mock_er.call_args[0][1]
        assert "public" in call_args  # visibility normalised

    def test_happy_path_no_reshare(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "sess-1"},                        # owns session
            None,                                    # not already shared
            {"imported_from_share_id": None},        # no reshare
            {"full_name": "Alice", "username": "alice"},  # author
        ])
        mocker.patch("backend.api.wall.service.execute_returning", return_value=self._BASE_ROW)
        mocker.patch("backend.api.wall.service.broadcast_event")
        from backend.api.wall.service import create_share
        result = create_share("user-1", "sess-1", "public", "desc")
        assert result["id"] == "share-1"

    def test_reshare_path_with_bonus_events(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "sess-1"},                        # owns
            None,                                    # not shared yet
            {"imported_from_share_id": "src-share"}, # is a reshare
            {"user_id": "other-user", "upvotes": 10, "downvotes": 0},  # src data
            None,                                    # no existing bonus
            {"full_name": "Alice", "username": "alice"},               # author
        ])
        row = {**self._BASE_ROW, "source_share_id": "src-share"}
        mocker.patch("backend.api.wall.service.execute_returning", return_value=row)
        mock_exec = mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.broadcast_event")
        from backend.api.wall.service import create_share
        result = create_share("user-1", "sess-1", "public", "desc")
        assert result["id"] == "share-1"
        mock_exec.assert_called()  # score event was persisted


# ===========================================================================
# _fetch_session_tree (lines 428-448)
# ===========================================================================

class TestFetchSessionTree:
    def test_returns_formatted_list(self, mocker):
        mocker.patch("backend.api.wall.service.query", return_value=[
            {"id": "s1", "title": "Root", "session_type": "regular",
             "depth_level": 0, "parent_session_id": None, "topic": None},
            {"id": "s2", "title": "Child", "session_type": "quiz",
             "depth_level": 1, "parent_session_id": "s1", "topic": "ML"},
        ])
        from backend.api.wall.service import _fetch_session_tree
        result = _fetch_session_tree("s1")
        assert len(result) == 2
        assert result[0]["id"] == "s1"
        assert result[1]["depth_level"] == 1
        assert result[1]["parent_session_id"] == "s1"

    def test_empty_query_returns_empty_list(self, mocker):
        mocker.patch("backend.api.wall.service.query", return_value=[])
        from backend.api.wall.service import _fetch_session_tree
        assert _fetch_session_tree("s1") == []


# ===========================================================================
# list_public_shares / list_private_shares (lines 455-503)
# ===========================================================================

def test_list_public_shares_returns_hydrated_rows(mocker):
    mocker.patch("backend.api.wall.service.query", return_value=[{"id": "share-1"}])
    mocker.patch("backend.api.wall.service._hydrate_share_rows",
                 return_value=[{"id": "share-1", "hydrated": True}])
    from backend.api.wall.service import list_public_shares
    result = list_public_shares("user-1", limit=10, offset=5)
    assert result == [{"id": "share-1", "hydrated": True}]


def test_list_public_shares_empty_list(mocker):
    mocker.patch("backend.api.wall.service.query", return_value=[])
    mocker.patch("backend.api.wall.service._hydrate_share_rows", return_value=[])
    from backend.api.wall.service import list_public_shares
    assert list_public_shares("user-1") == []


def test_list_private_shares_returns_hydrated_rows(mocker):
    mocker.patch("backend.api.wall.service.query", return_value=[{"id": "share-2"}])
    mocker.patch("backend.api.wall.service._hydrate_share_rows",
                 return_value=[{"id": "share-2"}])
    from backend.api.wall.service import list_private_shares
    result = list_private_shares("user-1")
    assert len(result) == 1


# ===========================================================================
# cast_vote (lines 517-565)
# ===========================================================================

class TestCastVoteService:
    def _score(self):
        return {"score": 0, "stars": 0.0, "upvotes": 0, "downvotes": 0, "share_count": 0}

    def test_share_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import cast_vote
        with pytest.raises(ValueError, match="Share not found"):
            cast_vote("user-1", "share-1", 1)

    def test_upvote_returns_correct_dict(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"user_id": "author"},
            {"upvotes": 1, "downvotes": 0},
        ])
        mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.broadcast_event")
        mocker.patch("backend.api.wall.service.get_user_score", return_value=self._score())
        from backend.api.wall.service import cast_vote
        result = cast_vote("user-1", "share-1", 1)
        assert result["upvotes"] == 1
        assert result["my_vote"] == 1

    def test_downvote_returns_correct_dict(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"user_id": "author"},
            {"upvotes": 0, "downvotes": 1},
        ])
        mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.broadcast_event")
        mocker.patch("backend.api.wall.service.get_user_score", return_value=self._score())
        from backend.api.wall.service import cast_vote
        result = cast_vote("user-1", "share-1", -1)
        assert result["my_vote"] == -1

    def test_remove_vote_executes_delete(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"user_id": "author"},
            {"upvotes": 0, "downvotes": 0},
        ])
        mock_exec = mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.broadcast_event")
        mocker.patch("backend.api.wall.service.get_user_score", return_value=self._score())
        from backend.api.wall.service import cast_vote
        cast_vote("user-1", "share-1", 0)
        mock_exec.assert_called()


# ===========================================================================
# _serialize_comment (lines 579-587)
# ===========================================================================

class TestSerializeComment:
    def test_formats_all_fields(self):
        from datetime import datetime, timezone
        from backend.api.wall.service import _serialize_comment
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        row = {"id": "c1", "share_id": "s1", "user_id": "u1",
               "full_name": "Alice", "content": "Hi!", "created_at": dt,
               "parent_comment_id": None}
        result = _serialize_comment(row)
        assert result["id"] == "c1"
        assert result["author_name"] == "Alice"
        assert "2026" in result["created_at"]
        assert result["parent_comment_id"] is None

    def test_none_created_at_returns_none(self):
        from backend.api.wall.service import _serialize_comment
        row = {"id": "c1", "share_id": "s1", "user_id": "u1",
               "author_name": "Bob", "content": "Hi!", "created_at": None,
               "parent_comment_id": "p1"}
        result = _serialize_comment(row)
        assert result["created_at"] is None
        assert result["parent_comment_id"] == "p1"


# ===========================================================================
# add_comment (lines 597-630)
# ===========================================================================

class TestAddCommentService:
    _DT = __import__("datetime").datetime(2026, 1, 1,
                      tzinfo=__import__("datetime").timezone.utc)

    def test_empty_content_raises(self, mocker):
        from backend.api.wall.service import add_comment
        with pytest.raises(ValueError, match="content required"):
            add_comment("user-1", "share-1", "")

    def test_whitespace_content_raises(self, mocker):
        from backend.api.wall.service import add_comment
        with pytest.raises(ValueError, match="content required"):
            add_comment("user-1", "share-1", "   ")

    def test_share_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import add_comment
        with pytest.raises(ValueError, match="Share not found"):
            add_comment("user-1", "share-1", "Hello")

    def test_invalid_parent_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "share-1"},   # share exists
            None,                # parent not found
        ])
        from backend.api.wall.service import add_comment
        with pytest.raises(ValueError, match="Invalid parent comment"):
            add_comment("user-1", "share-1", "Reply", parent_comment_id="bad")

    def test_success_returns_comment_dict(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "share-1"},
            {"full_name": "Alice"},
        ])
        mocker.patch("backend.api.wall.service.execute_returning", return_value={
            "id": "c1", "share_id": "share-1", "user_id": "user-1",
            "content": "Hello!", "created_at": self._DT, "parent_comment_id": None,
        })
        mocker.patch("backend.api.wall.service.broadcast_event")
        from backend.api.wall.service import add_comment
        result = add_comment("user-1", "share-1", "Hello!")
        assert result["id"] == "c1"
        assert result["content"] == "Hello!"


# ===========================================================================
# list_comments (lines 634-645)
# ===========================================================================

def test_list_comments_service_returns_serialized(mocker):
    from datetime import datetime, timezone
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mocker.patch("backend.api.wall.service.query", return_value=[
        {"id": "c1", "share_id": "s1", "user_id": "u1", "author_name": "Alice",
         "content": "Hi!", "created_at": dt, "parent_comment_id": None},
    ])
    from backend.api.wall.service import list_comments
    result = list_comments("share-1")
    assert len(result) == 1
    assert result[0]["content"] == "Hi!"


def test_list_comments_service_empty(mocker):
    mocker.patch("backend.api.wall.service.query", return_value=[])
    from backend.api.wall.service import list_comments
    assert list_comments("share-1") == []


# ===========================================================================
# delete_comment (lines 649-663)
# ===========================================================================

class TestDeleteCommentService:
    def test_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import delete_comment
        with pytest.raises(ValueError, match="not found"):
            delete_comment("user-1", "comment-1")

    def test_not_owner_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one",
                     return_value={"user_id": "other", "share_id": "s1"})
        from backend.api.wall.service import delete_comment
        with pytest.raises(ValueError, match="authorised"):
            delete_comment("user-1", "comment-1")

    def test_success_executes_and_broadcasts(self, mocker):
        mocker.patch("backend.api.wall.service.query_one",
                     return_value={"user_id": "user-1", "share_id": "s1"})
        mock_exec = mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.broadcast_event")
        from backend.api.wall.service import delete_comment
        delete_comment("user-1", "comment-1")
        mock_exec.assert_called()


# ===========================================================================
# save_to_wall / unsave_from_wall (lines 674-694)
# ===========================================================================

class TestSaveToWall:
    def test_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import save_to_wall
        with pytest.raises(ValueError, match="not found"):
            save_to_wall("user-1", "share-1")

    def test_own_share_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"user_id": "user-1"})
        from backend.api.wall.service import save_to_wall
        with pytest.raises(ValueError, match="own share"):
            save_to_wall("user-1", "share-1")

    def test_success_calls_execute(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"user_id": "other"})
        mock_exec = mocker.patch("backend.api.wall.service.execute")
        from backend.api.wall.service import save_to_wall
        save_to_wall("user-1", "share-1")
        mock_exec.assert_called()


def test_unsave_from_wall_calls_execute(mocker):
    mock_exec = mocker.patch("backend.api.wall.service.execute")
    from backend.api.wall.service import unsave_from_wall
    unsave_from_wall("user-1", "share-1")
    mock_exec.assert_called()


# ===========================================================================
# follow_user / cancel_follow (lines 706-748)
# ===========================================================================

class TestFollowUser:
    def test_self_follow_returns_self_status(self, mocker):
        from backend.api.wall.service import follow_user
        assert follow_user("user-1", "user-1")["status"] == "self"

    def test_existing_follow_returns_current_status(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"status": "accepted"})
        from backend.api.wall.service import follow_user
        assert follow_user("user-1", "user-2")["status"] == "accepted"

    def test_new_follow_request_returns_pending(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            None,
            {"id": "user-1", "full_name": "Alice", "username": "alice"},
        ])
        mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.publish_event")
        from backend.api.wall.service import follow_user
        assert follow_user("user-1", "user-2")["status"] == "pending"

    def test_follow_when_requester_not_found_still_returns_pending(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[None, None])
        mocker.patch("backend.api.wall.service.execute")
        mocker.patch("backend.api.wall.service.publish_event")
        from backend.api.wall.service import follow_user
        assert follow_user("user-1", "user-2")["status"] == "pending"


def test_cancel_follow_calls_execute(mocker):
    mock_exec = mocker.patch("backend.api.wall.service.execute")
    from backend.api.wall.service import cancel_follow
    cancel_follow("user-1", "user-2")
    mock_exec.assert_called()


# ===========================================================================
# accept_follow_request / reject_follow_request (lines 753-791)
# ===========================================================================

class TestAcceptFollowRequest:
    def test_no_pending_request_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import accept_follow_request
        with pytest.raises(ValueError, match="No pending request"):
            accept_follow_request("user-2", "user-1")

    def test_not_pending_status_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={"status": "accepted"})
        from backend.api.wall.service import accept_follow_request
        with pytest.raises(ValueError, match="not in pending"):
            accept_follow_request("user-2", "user-1")

    def test_success_sends_notification(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"status": "pending"},
            {"id": "user-2", "full_name": "Bob", "username": "bob"},
        ])
        mocker.patch("backend.api.wall.service.execute")
        mock_publish = mocker.patch("backend.api.wall.service.publish_event")
        from backend.api.wall.service import accept_follow_request
        accept_follow_request("user-2", "user-1")
        mock_publish.assert_called()


def test_reject_follow_request_calls_execute(mocker):
    mock_exec = mocker.patch("backend.api.wall.service.execute")
    from backend.api.wall.service import reject_follow_request
    reject_follow_request("user-2", "user-1")
    mock_exec.assert_called()


# ===========================================================================
# get_pending_requests (lines 796-814)
# ===========================================================================

def test_get_pending_requests_returns_formatted_list(mocker):
    from datetime import datetime, timezone
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mocker.patch("backend.api.wall.service.query", return_value=[
        {"id": "u1", "full_name": "Alice", "username": "alice", "requested_at": dt},
    ])
    from backend.api.wall.service import get_pending_requests
    result = get_pending_requests("user-2")
    assert len(result) == 1
    assert result[0]["username"] == "alice"
    assert "2026" in result[0]["requested_at"]


def test_get_pending_requests_none_requested_at(mocker):
    mocker.patch("backend.api.wall.service.query", return_value=[
        {"id": "u1", "full_name": "Bob", "username": "bob", "requested_at": None},
    ])
    from backend.api.wall.service import get_pending_requests
    result = get_pending_requests("user-2")
    assert result[0]["requested_at"] is None


# ===========================================================================
# get_profile (lines 824-867)
# ===========================================================================

class TestGetProfile:
    _DT = __import__("datetime").datetime(2026, 1, 1,
                      tzinfo=__import__("datetime").timezone.utc)

    def test_user_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import get_profile
        with pytest.raises(ValueError, match="User not found"):
            get_profile("user-1", "viewer-1")

    def test_returns_full_profile(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "u1", "username": "alice", "email": "a@b.com",
             "full_name": "Alice", "created_at": self._DT},
            {"cnt": 5},   # follower_count
            {"cnt": 3},   # following_count
            {"status": "accepted"},  # is_following
        ])
        mocker.patch("backend.api.wall.service.query", return_value=[])
        mocker.patch("backend.api.wall.service._hydrate_share_rows", return_value=[])
        mocker.patch("backend.api.wall.service.get_user_score", return_value={
            "score": 10, "stars": 0.0, "upvotes": 5, "downvotes": 1, "share_count": 2,
        })
        mocker.patch("backend.api.wall.service.get_pending_requests", return_value=[])
        from backend.api.wall.service import get_profile
        result = get_profile("u1", "viewer-1")
        assert result["username"] == "alice"
        assert result["follower_count"] == 5
        assert result["is_following"] is True
        assert result["is_self"] is False

    def test_self_view_shows_pending_requests(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", side_effect=[
            {"id": "u1", "username": "alice", "email": "a@b.com",
             "full_name": "Alice", "created_at": self._DT},
            {"cnt": 2}, {"cnt": 1}, None,  # no is_following row for self
        ])
        mocker.patch("backend.api.wall.service.query", return_value=[])
        mocker.patch("backend.api.wall.service._hydrate_share_rows", return_value=[])
        mocker.patch("backend.api.wall.service.get_user_score", return_value={
            "score": 0, "stars": 0.0, "upvotes": 0, "downvotes": 0, "share_count": 0,
        })
        mocker.patch("backend.api.wall.service.get_pending_requests",
                     return_value=[{"id": "req-1"}])
        from backend.api.wall.service import get_profile
        result = get_profile("u1", "u1")  # same user — self view
        assert result["is_self"] is True
        assert len(result["pending_requests"]) == 1


# ===========================================================================
# get_share_preview (lines 902-921)
# ===========================================================================

class TestGetSharePreview:
    _DT = __import__("datetime").datetime(2026, 1, 1,
                      tzinfo=__import__("datetime").timezone.utc)

    def test_not_found_raises(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value=None)
        from backend.api.wall.service import get_share_preview
        with pytest.raises(ValueError, match="Share not found"):
            get_share_preview("bad-share")

    def test_returns_structured_dict(self, mocker):
        mocker.patch("backend.api.wall.service.query_one", return_value={
            "id": "share-1", "user_id": "u1", "session_id": "sess-1",
            "visibility": "public", "description": "test",
            "created_at": self._DT, "session_title": "My Session",
            "session_type": "regular", "topic": None,
            "author_name": "Alice", "author_username": "alice",
        })
        mocker.patch("backend.api.wall.service._fetch_session_tree", return_value=[
            {"id": "sess-1", "title": "My Session", "session_type": "regular",
             "depth_level": 0, "parent_session_id": None, "topic": None},
        ])
        mocker.patch("backend.api.wall.service.get_session_preview_content",
                     return_value={"type": "messages", "messages": []})
        from backend.api.wall.service import get_share_preview
        result = get_share_preview("share-1")
        assert result["id"] == "share-1"
        assert result["author_username"] == "alice"
        assert result["initial_session_id"] == "sess-1"


# ===========================================================================
# share_session_preview.html — artifact rendering in wall preview modal
# ===========================================================================

_SESSION_PREVIEW_RICH = {
    "type": "messages",
    "session_type": "regular",
    "article_link": "",
    "article_title": "",
    "title": "ML Fundamentals",
    "messages": [
        {
            "role": "user",
            "content": {"type": "text", "text": "Tell me about gradient descent"},
        },
        {
            "role": "assistant",
            "content": {
                "type": "sectioned",
                "intro": "This covers machine learning optimisation fundamentals.",
                "hierarchy_diagram": (
                    "flowchart TD\n"
                    "  ROOT[ML Overview] --> A[Gradient Descent]\n"
                    "  ROOT --> B[Neural Networks]\n"
                    "  ROOT --> C[Regularisation]\n"
                    "  ROOT --> D[Architecture]"
                ),
                "sections": [
                    {
                        "id": "s1",
                        "title": "Gradient Descent",
                        "content": "The core iterative optimisation algorithm.",
                        "key_points": ["Iterative convergence"],
                        "misconception": "It always finds global minima.",
                        "learn_more_topic": "Optimisation theory",
                        "artifacts": [
                            {
                                "type": "formula",
                                "latex": r"\theta := \theta - \alpha \nabla J(\theta)",
                                "caption": "Weight update rule",
                            }
                        ],
                    },
                    {
                        "id": "s2",
                        "title": "Neural Networks",
                        "content": "Interconnected layers of neurons.",
                        "key_points": ["Layers"],
                        "misconception": "Mimics the human brain exactly.",
                        "learn_more_topic": "Deep learning",
                        "artifacts": [
                            {
                                "type": "chart",
                                "chart_type": "bar",
                                "title": "Layer Sizes",
                                "labels": ["Input", "Hidden", "Output"],
                                "datasets": [{"label": "Units", "data": [784, 128, 10]}],
                                "caption": "Typical MLP architecture",
                            }
                        ],
                    },
                    {
                        "id": "s3",
                        "title": "Regularisation",
                        "content": "Preventing overfitting via constraints.",
                        "key_points": ["L1/L2 penalties"],
                        "misconception": "More data alone fixes overfitting.",
                        "learn_more_topic": "Regularisation techniques",
                        "artifacts": [
                            {
                                "type": "diagram",
                                "mermaid": (
                                    "flowchart TD\n"
                                    "  L1[L1 Norm] --> Sparse[Sparse Weights]\n"
                                    "  L2[L2 Norm] --> Small[Small Weights]"
                                ),
                                "caption": "Regularisation taxonomy",
                            }
                        ],
                    },
                    {
                        "id": "s4",
                        "title": "Architecture",
                        "content": "How layers are arranged in a network.",
                        "artifacts": [],
                    },
                ],
                "outro": "Start with gradient descent to understand how networks learn.",
            },
        },
    ],
}

_SESSION_PREVIEW_PLAIN = {
    "type": "messages",
    "session_type": "regular",
    "article_link": "",
    "article_title": "",
    "title": "Plain Topic",
    "messages": [
        {"role": "user", "content": {"type": "text", "text": "Tell me something"}},
        {
            "role": "assistant",
            "content": {
                "type": "sectioned",
                "intro": "Overview.",
                "sections": [
                    {"id": "s1", "title": "Topic", "content": "Content.", "artifacts": []}
                ],
                "outro": "Done.",
            },
        },
    ],
}


def _preview_url(share_id="share-1", session_id="sess-1"):
    return f"/wall/shares/{share_id}/sessions/{session_id}/preview/partial"


def test_session_preview_renders_hierarchy_diagram_wrapper(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert resp.status_code == 200
    assert b"hierarchy-diagram-wrapper" in resp.data


def test_session_preview_renders_section_title_data_attribute(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"data-section-title" in resp.data


def test_session_preview_renders_formula_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"Show Formula" in resp.data


def test_session_preview_renders_chart_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"Show Chart" in resp.data


def test_session_preview_renders_diagram_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"Show Diagram" in resp.data


def test_session_preview_renders_katex_block_for_formula(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"katex-block" in resp.data


def test_session_preview_renders_chart_canvas(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_RICH)
    resp = authed_client.get(_preview_url())
    assert b"artifact-chart" in resp.data


def test_session_preview_no_hierarchy_wrapper_when_diagram_absent(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_PLAIN)
    resp = authed_client.get(_preview_url())
    assert b"hierarchy-diagram-wrapper" not in resp.data


def test_session_preview_no_artifact_toggles_when_all_sections_empty(authed_client, mocker):
    mocker.patch(f"{WALL_SVC}.get_share_preview", return_value=_PREVIEW)
    mocker.patch(f"{WALL_SVC}.get_session_preview_content", return_value=_SESSION_PREVIEW_PLAIN)
    resp = authed_client.get(_preview_url())
    assert b"Show Formula" not in resp.data
    assert b"Show Chart" not in resp.data
    assert b"Show Diagram" not in resp.data
