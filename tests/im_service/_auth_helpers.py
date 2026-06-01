"""Shared auth helpers for IM integration + contract tests (feat-340-M1).

After R4, all IM HTTP routes require a Bearer token. Tests use these helpers to
register a tenant, install the access token onto a TestClient, and seed extra
participant users under the same tenant when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


@dataclass(frozen=True)
class AuthedUser:
    """Registered user + token bundle."""

    id: str
    username: str
    display_name: str
    owner_id: str
    access_token: str
    refresh_token: str


def make_app_client(tmp_path: Path, *, db_name: str = "im.db") -> TestClient:
    """Build one fresh FastAPI app + TestClient against a temp sqlite file."""
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
    """Register a user via /im/v1/auth/register and return tokens + user payload."""
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
    """Install the user's bearer token onto the TestClient default headers."""
    client.headers.update({"Authorization": f"Bearer {user.access_token}"})


def seed_user_under_owner(
    client: TestClient,
    *,
    username: str,
    display_name: str | None = None,
    owner_id: str,
) -> str:
    """Create a passwordless participant user manually placed under ``owner_id`` and return id."""
    from IM.infra.repositories import UserRepository

    connection = client.app.state.connection
    repo = UserRepository(connection)
    # feat-340-M18 R9-1: agent profile reads now lazily provision ``agent:<id>`` rows,
    # so a fixture that seeds the same username after a /im/v1/agents call would race
    # against the lazy bootstrap. Treat that case as idempotent and return the
    # existing row instead of failing the whole test on a UNIQUE constraint.
    existing = repo.get_user_by_username(username=username)
    if existing is not None:
        created = existing
    else:
        created = repo.create_user(
            username=username, display_name=display_name or username.title()
        )
    if created.owner_id != owner_id:
        connection.execute(
            "UPDATE users SET owner_id = ? WHERE id = ?", (owner_id, created.id)
        )
        connection.commit()
    return created.id


def register_and_authorize(
    client: TestClient,
    *,
    username: str = "owner",
    display_name: str | None = None,
) -> AuthedUser:
    """Register and authorize the client in one call."""
    user = register_user(client, username=username, display_name=display_name)
    authorize(client, user)
    return user
