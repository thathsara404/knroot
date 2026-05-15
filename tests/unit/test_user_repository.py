"""Unit tests for backend.repositories.user_repository.UserRepository."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

REPO = "backend.repositories.user_repository"

_ROW = {
    "id": "uuid-1",
    "username": "alice",
    "email": "alice@example.com",
    "full_name": "Alice Smith",
    "phone": "+1234567890",
    "password_hash": "hashed_pw",
    "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
}


def _repo():
    from backend.repositories.user_repository import user_repo
    return user_repo


class TestFindById:
    def test_returns_user_when_row_found(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value=_ROW)
        user = _repo().find_by_id("uuid-1")
        assert user is not None
        assert user.username == "alice"
        assert user.email == "alice@example.com"

    def test_returns_none_when_not_found(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value=None)
        user = _repo().find_by_id("no-such-id")
        assert user is None

    def test_user_id_is_string(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value=_ROW)
        user = _repo().find_by_id("uuid-1")
        assert isinstance(user.id, str)


class TestFindForAuth:
    def test_finds_by_username(self, mocker):
        mock_qo = mocker.patch(f"{REPO}.query_one", side_effect=[_ROW, None])
        result = _repo().find_for_auth("alice")
        assert result is not None
        user, pw_hash = result
        assert user.username == "alice"
        assert pw_hash == "hashed_pw"
        # Should only have called query_one once (username matched)
        assert mock_qo.call_count == 1

    def test_falls_back_to_email_lookup(self, mocker):
        mock_qo = mocker.patch(f"{REPO}.query_one", side_effect=[None, _ROW])
        result = _repo().find_for_auth("alice@example.com")
        assert result is not None
        user, _ = result
        assert user.email == "alice@example.com"
        assert mock_qo.call_count == 2

    def test_returns_none_when_not_found(self, mocker):
        mocker.patch(f"{REPO}.query_one", side_effect=[None, None])
        result = _repo().find_for_auth("nobody")
        assert result is None


class TestExistsChecks:
    def test_exists_by_username_true(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value={"1": 1})
        assert _repo().exists_by_username("alice") is True

    def test_exists_by_username_false(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value=None)
        assert _repo().exists_by_username("nobody") is False

    def test_exists_by_email_true(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value={"1": 1})
        assert _repo().exists_by_email("alice@example.com") is True

    def test_exists_by_email_false(self, mocker):
        mocker.patch(f"{REPO}.query_one", return_value=None)
        assert _repo().exists_by_email("nobody@example.com") is False


class TestCreate:
    def test_create_returns_user(self, mocker):
        mocker.patch(f"{REPO}.execute_returning", return_value=_ROW)
        user = _repo().create(
            username="alice",
            email="alice@example.com",
            full_name="Alice Smith",
            password_hash="hashed",
            phone="+1234567890",
        )
        assert user.username == "alice"
        assert user.full_name == "Alice Smith"

    def test_create_without_phone(self, mocker):
        row = {**_ROW, "phone": None}
        mocker.patch(f"{REPO}.execute_returning", return_value=row)
        user = _repo().create(
            username="bob",
            email="bob@example.com",
            full_name="Bob Jones",
            password_hash="hashed",
        )
        assert user.phone is None

    def test_create_calls_execute_returning(self, mocker):
        mock_er = mocker.patch(f"{REPO}.execute_returning", return_value=_ROW)
        _repo().create("alice", "alice@example.com", "Alice", "pw")
        assert mock_er.call_count == 1
