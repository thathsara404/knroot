from __future__ import annotations

import logging

from backend.core.db import execute_returning, query_one
from backend.domain.user import User

logger = logging.getLogger(__name__)


class UserRepository:
    """All SQL for the users table. Returns domain models, never raw dicts."""

    def _to_user(self, row: dict) -> User:
        return User(
            id=str(row['id']),
            username=row['username'],
            email=row['email'],
            full_name=row['full_name'],
            phone=row.get('phone'),
            created_at=row['created_at'],
        )

    def find_by_id(self, user_id: str) -> User | None:
        row = query_one(
            'SELECT id, username, email, phone, full_name, created_at FROM users WHERE id = %s',
            (user_id,),
        )
        return self._to_user(row) if row else None

    def find_for_auth(self, identifier: str) -> tuple[User, str] | None:
        """Single-purpose auth query: returns (user, password_hash) or None.

        Tries username first, then email — password_hash never leaves this method.
        """
        row = query_one('SELECT * FROM users WHERE username = %s', (identifier,))
        if not row:
            row = query_one('SELECT * FROM users WHERE email = %s', (identifier.lower(),))
        if not row:
            return None
        return self._to_user(row), row['password_hash']

    def exists_by_username(self, username: str) -> bool:
        return bool(query_one('SELECT 1 FROM users WHERE username = %s', (username,)))

    def exists_by_email(self, email: str) -> bool:
        return bool(query_one('SELECT 1 FROM users WHERE email = %s', (email,)))

    def create(
        self,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        phone: str | None = None,
    ) -> User:
        row = execute_returning(
            '''INSERT INTO users (username, email, phone, full_name, password_hash)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, username, email, phone, full_name, created_at''',
            (username, email, phone, full_name, password_hash),
        )
        return self._to_user(row)


# Module-level singleton — import this, don't instantiate UserRepository directly
user_repo = UserRepository()
