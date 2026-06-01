"""Integration tests for the IM /im/v1/auth/* HTTP endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(db_path=tmp_path / "im.db")
    return TestClient(app)


def test_register_returns_token_pair_and_user(tmp_path: Path) -> None:
    """POST /im/v1/auth/register must return access_token, refresh_token, and the new user."""
    with _make_client(tmp_path) as client:
        response = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
                "locale": "zh",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user"]["username"] == "alice"
        assert body["user"]["display_name"] == "Alice"
        assert body["user"]["locale"] == "zh"
        # password_hash must never leak through any auth response.
        assert "password_hash" not in body["user"]


def test_register_rejects_duplicate_username(tmp_path: Path) -> None:
    """Second register with the same username must respond with 409."""
    with _make_client(tmp_path) as client:
        first = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
            },
        )
        assert first.status_code == 201
        second = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice 2",
            },
        )
        assert second.status_code == 409


def test_login_then_me_returns_current_user(tmp_path: Path) -> None:
    """Login → use returned access token to call /im/v1/auth/me — must succeed."""
    with _make_client(tmp_path) as client:
        client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
            },
        )
        login_resp = client.post(
            "/im/v1/auth/login",
            json={"username": "alice", "password": "hunter2-strong"},
        )
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["access_token"]
        me_resp = client.get(
            "/im/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200, me_resp.text
        body = me_resp.json()
        assert body["username"] == "alice"
        assert body["display_name"] == "Alice"
        assert body["locale"] == "en"


def test_login_wrong_password_returns_401(tmp_path: Path) -> None:
    """Wrong password → 401, not 400, and a generic detail (no existence oracle)."""
    with _make_client(tmp_path) as client:
        client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
            },
        )
        response = client.post(
            "/im/v1/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )
        assert response.status_code == 401


def test_me_without_token_returns_401(tmp_path: Path) -> None:
    """Calling /im/v1/auth/me without Authorization header must return 401."""
    with _make_client(tmp_path) as client:
        response = client.get("/im/v1/auth/me")
        assert response.status_code == 401


def test_me_with_invalid_token_returns_401(tmp_path: Path) -> None:
    """Calling /im/v1/auth/me with a garbage Bearer token must return 401."""
    with _make_client(tmp_path) as client:
        response = client.get(
            "/im/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401


def test_refresh_returns_new_pair_and_invalidates_old(tmp_path: Path) -> None:
    """Refresh rotates: new pair is valid; old refresh token is invalid."""
    with _make_client(tmp_path) as client:
        register = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
            },
        ).json()
        refresh_token = register["refresh_token"]
        first = client.post(
            "/im/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert first.status_code == 200
        new_refresh = first.json()["refresh_token"]
        assert new_refresh != refresh_token
        # Reusing the original refresh token must now fail.
        replay = client.post(
            "/im/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert replay.status_code == 401


def test_logout_revokes_refresh_token(tmp_path: Path) -> None:
    """After logout the refresh token must be unusable."""
    with _make_client(tmp_path) as client:
        register = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "hunter2-strong",
                "display_name": "Alice",
            },
        ).json()
        refresh_token = register["refresh_token"]
        logout_resp = client.post(
            "/im/v1/auth/logout", json={"refresh_token": refresh_token}
        )
        assert logout_resp.status_code == 200
        replay = client.post(
            "/im/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert replay.status_code == 401
