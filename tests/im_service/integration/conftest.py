"""Shared helpers for IM integration tests.

Multi-user auth (feat-340-M1 R4) replaces the legacy ``POST /im/v1/users`` fixture
with token-based register/login. Tests use ``authed_client`` to obtain a TestClient
with ``Authorization: Bearer <access_token>`` already attached and the corresponding
registered user payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


@dataclass(frozen=True)
class AuthedUser:
    """Registered user + token bundle returned by ``register_user``."""

    id: str
    username: str
    display_name: str
    owner_id: str
    access_token: str
    refresh_token: str


def make_app_client(tmp_path: Path, *, db_name: str = "im.db") -> TestClient:
    """Build one fresh FastAPI app + TestClient under the tmp dir."""
    app = create_app(db_path=tmp_path / db_name)
    return TestClient(app)


def register_user(
    client: TestClient,
    *,
    username: str,
    display_name: str | None = None,
    password: str = "hunter2-strong",
    locale: str = "en",
) -> AuthedUser:
    """Register a user through /im/v1/auth/register and return tokens + user payload.

    The returned ``AuthedUser`` is safe to plug into ``authorize`` (or
    ``client.headers``) for subsequent requests.
    """
    response = client.post(
        "/im/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "display_name": display_name or username.title(),
            "locale": locale,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    user = body["user"]
    return AuthedUser(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        owner_id=user["owner_id"],
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
    )


def authorize(client: TestClient, user: AuthedUser) -> None:
    """Install the user's bearer token onto the TestClient default headers in place."""
    client.headers.update({"Authorization": f"Bearer {user.access_token}"})


def make_authed_client(
    tmp_path: Path,
    *,
    username: str = "alice",
    display_name: str | None = None,
) -> tuple[TestClient, AuthedUser]:
    """Construct a TestClient, register one user, and authorize the client.

    Tests that only need a single authenticated owner can use this in a single line:
    ``client, user = make_authed_client(tmp_path)``.
    Tests that need a second tenant should reuse the same ``client`` to call
    ``register_user`` and authorize the second user separately (e.g. via a
    second TestClient against the same app).
    """
    client = make_app_client(tmp_path)
    client.__enter__()
    try:
        user = register_user(client, username=username, display_name=display_name)
        authorize(client, user)
    except Exception:
        client.__exit__(None, None, None)
        raise
    return client, user
