"""Unit tests for the IM auth service (password hash + JWT + refresh + revoke)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from IM.application.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    RegistrationError,
    TokenPair,
)
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import UserRepository


@pytest.fixture()
def auth_service(tmp_path: Path) -> AuthService:
    """Build an AuthService backed by a fresh SQLite database."""
    connection = connect(tmp_path / "im.sqlite3")
    initialize_schema(connection)
    return AuthService(
        users=UserRepository(connection),
        jwt_secret="test-secret-do-not-use-in-prod",
        access_ttl_seconds=2,
        refresh_ttl_seconds=10,
    )


def test_register_creates_user_with_hashed_password(auth_service: AuthService) -> None:
    """Registration must hash the password and return a token pair plus the new user."""
    pair = auth_service.register(
        username="alice",
        password="hunter2-strong",
        display_name="Alice",
    )

    assert isinstance(pair, TokenPair)
    assert pair.access_token
    assert pair.refresh_token
    assert pair.user.username == "alice"
    assert pair.user.display_name == "Alice"
    # password_hash never leaks through a TokenPair user payload.
    assert (
        getattr(pair.user, "password_hash", None) is None
        or pair.user.password_hash is None
        or pair.user.password_hash != "hunter2-strong"
    )


def test_register_rejects_duplicate_username(auth_service: AuthService) -> None:
    """Two registrations with the same username must raise RegistrationError."""
    auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    with pytest.raises(RegistrationError):
        auth_service.register(
            username="alice", password="other-password", display_name="Alice 2"
        )


def test_register_rejects_weak_password(auth_service: AuthService) -> None:
    """Password shorter than the floor must be rejected loudly."""
    with pytest.raises(RegistrationError):
        auth_service.register(username="alice", password="short", display_name="Alice")


def test_login_succeeds_with_correct_password(auth_service: AuthService) -> None:
    """Login must return a fresh token pair for the matching password."""
    auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    pair = auth_service.login(username="alice", password="hunter2-strong")
    assert pair.access_token
    assert pair.refresh_token
    assert pair.user.username == "alice"


def test_login_rejects_wrong_password(auth_service: AuthService) -> None:
    """Wrong password must raise InvalidCredentialsError, not silently fail."""
    auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    with pytest.raises(InvalidCredentialsError):
        auth_service.login(username="alice", password="wrong-password")


def test_login_rejects_unknown_user(auth_service: AuthService) -> None:
    """Unknown username must also raise InvalidCredentialsError (avoid existence oracle)."""
    with pytest.raises(InvalidCredentialsError):
        auth_service.login(username="ghost", password="hunter2-strong")


def test_verify_access_token_returns_user_id(auth_service: AuthService) -> None:
    """Decoded access token must yield the original user id."""
    pair = auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    user_id = auth_service.verify_access_token(pair.access_token)
    assert user_id == pair.user.id


def test_verify_access_token_rejects_garbage(auth_service: AuthService) -> None:
    """A non-JWT garbage string must raise InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        auth_service.verify_access_token("not-a-jwt")


def test_verify_access_token_rejects_expired(auth_service: AuthService) -> None:
    """An expired access token must raise InvalidTokenError."""
    pair = auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    time.sleep(2.5)  # access_ttl_seconds=2 in fixture
    with pytest.raises(InvalidTokenError):
        auth_service.verify_access_token(pair.access_token)


def test_refresh_rotates_tokens(auth_service: AuthService) -> None:
    """Refresh must mint new tokens; old refresh token must no longer work."""
    pair = auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    new_pair = auth_service.refresh(pair.refresh_token)
    assert new_pair.access_token != pair.access_token
    assert new_pair.refresh_token != pair.refresh_token
    # Reusing the old refresh token after rotation must be rejected.
    with pytest.raises(InvalidTokenError):
        auth_service.refresh(pair.refresh_token)


def test_logout_revokes_refresh_token(auth_service: AuthService) -> None:
    """After logout the refresh token must be rejected."""
    pair = auth_service.register(
        username="alice", password="hunter2-strong", display_name="Alice"
    )
    auth_service.logout(pair.refresh_token)
    with pytest.raises(InvalidTokenError):
        auth_service.refresh(pair.refresh_token)


def test_register_stores_locale(auth_service: AuthService) -> None:
    """The user record must persist the requested locale (default 'en')."""
    pair = auth_service.register(
        username="alice",
        password="hunter2-strong",
        display_name="Alice",
        locale="zh",
    )
    assert pair.user.locale == "zh"
    default_pair = auth_service.register(
        username="bob",
        password="hunter2-strong",
        display_name="Bob",
    )
    assert default_pair.user.locale == "en"
