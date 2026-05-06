from __future__ import annotations

import re

from pydantic import BaseModel, model_validator

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,50}$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_PHONE_RE = re.compile(r'^\+?[1-9]\d{1,14}$')


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone: str | None = None
    password: str
    confirm_password: str

    @model_validator(mode='after')
    def validate_fields(self) -> RegisterRequest:
        errors: dict[str, str] = {}

        if not self.first_name.strip() or len(self.first_name) > 50:
            errors['first_name'] = 'Required and must be under 50 characters'
        if not self.last_name.strip() or len(self.last_name) > 50:
            errors['last_name'] = 'Required and must be under 50 characters'
        if not _USERNAME_RE.match(self.username):
            errors['username'] = 'Must be 3–50 characters: letters, digits, or underscores'
        if not _EMAIL_RE.match(self.email):
            errors['email'] = 'Enter a valid email address'
        if self.phone and not _PHONE_RE.match(self.phone):
            errors['phone'] = 'Enter a valid phone number (e.g. +1234567890)'

        pw = self.password
        pw_ok = len(pw) >= 8 and any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw)
        if not pw_ok:
            errors['password'] = 'At least 8 characters with one letter and one digit'
        elif self.password != self.confirm_password:
            errors['confirm_password'] = 'Passwords do not match'

        if errors:
            raise ValueError(errors)

        return self


class LoginRequest(BaseModel):
    identifier: str
    password: str

    @model_validator(mode='after')
    def validate_fields(self) -> LoginRequest:
        errors: dict[str, str] = {}
        if not self.identifier:
            errors['identifier'] = 'Required'
        if not self.password:
            errors['password'] = 'Required'
        if errors:
            raise ValueError(errors)
        return self
