from __future__ import annotations

import logging

import bcrypt

from backend.core.errors import ConflictError, UnauthorizedError
from backend.domain.user import User
from backend.repositories.user_repository import user_repo

logger = logging.getLogger(__name__)


def register_user(first_name: str, last_name: str, username: str,
                  email: str, password: str, phone: str | None = None) -> User:
    if user_repo.exists_by_username(username):
        raise ConflictError('Username already taken')
    if user_repo.exists_by_email(email.lower()):
        raise ConflictError('Email already registered')

    full_name = f"{first_name.strip()} {last_name.strip()}"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return user_repo.create(username, email.lower(), full_name, password_hash, phone)


def login_user(identifier: str, password: str) -> User:
    result = user_repo.find_for_auth(identifier)
    if not result or not bcrypt.checkpw(password.encode(), result[1].encode()):
        raise UnauthorizedError('Invalid credentials')
    return result[0]


def get_user(user_id: str) -> User:
    user = user_repo.find_by_id(user_id)
    if not user:
        raise UnauthorizedError('User not found')
    return user
