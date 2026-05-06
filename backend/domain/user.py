from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """Immutable domain model — no Flask, no DB, no business logic."""
    id: str
    username: str
    email: str
    full_name: str
    created_at: datetime
    phone: str | None = None

    def to_profile(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'created_at': self.created_at.isoformat(),
        }
