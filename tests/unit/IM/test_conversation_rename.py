"""HTTP contract tests for group conversation rename."""

from pathlib import Path

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# HTTP route tests (PATCH /im/v1/conversations/{id})
# ---------------------------------------------------------------------------


def _make_app(tmp_path: Path) -> object:
    """Build a FastAPI app wired to a fresh temporary DB (no pre-seeded data).

    Returns the app object for use inside ``with TestClient(app) as client:``.
    HTTP tests register and create data through the API so the owner_id tenant
    scoping in conversation routes is consistent with the JWT token.
    """
    from IM.app import create_app

    db_path = tmp_path / "im.db"
    return create_app(db_path=db_path, upload_dir=tmp_path / "uploads")


def _register_and_create_group(client: TestClient) -> tuple[str, str]:
    """Register alice, create a 3-participant group conversation; return (token, convo_id).

    Conversations/messages routes require JWT auth and tenant scoping (R4 of feat-340).
    All HTTP route tests seed data through the API so the registered owner_id matches
    the one used by the route's owner-scoped filter.
    """
    reg = client.post(
        "/im/v1/auth/register",
        json={"username": "alice", "password": "pw12345678", "display_name": "Alice"},
    )
    assert reg.status_code in (200, 201), f"register failed: {reg.text}"
    token = reg.json()["access_token"]
    alice_id = reg.json()["user"]["id"]
    auth = {"Authorization": f"Bearer {token}"}

    conv = client.post(
        "/im/v1/conversations",
        json={"title": "Alice + Bob + Carol", "participant_ids": [alice_id]},
        headers=auth,
    )
    assert conv.status_code in (200, 201), f"create conv failed: {conv.text}"
    return token, conv.json()["id"]


def test_patch_title_returns_updated_conversation(tmp_path: Path) -> None:
    """PATCH /im/v1/conversations/{id} with {title} returns 200 and new title."""
    app = _make_app(tmp_path)

    with TestClient(app) as client:
        token, convo_id = _register_and_create_group(client)
        auth = {"Authorization": f"Bearer {token}"}
        response = client.patch(
            f"/im/v1/conversations/{convo_id}",
            json={"title": "Team Alpha"},
            headers=auth,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Team Alpha"
    assert data["id"] == convo_id


def test_patch_empty_title_returns_400(tmp_path: Path) -> None:
    """PATCH with blank title returns 400 Bad Request."""
    app = _make_app(tmp_path)

    with TestClient(app) as client:
        token, convo_id = _register_and_create_group(client)
        auth = {"Authorization": f"Bearer {token}"}
        response = client.patch(
            f"/im/v1/conversations/{convo_id}",
            json={"title": "   "},
            headers=auth,
        )

    assert response.status_code == 400


def test_patch_title_nonexistent_returns_404(tmp_path: Path) -> None:
    """PATCH on missing conversation_id returns 404."""
    app = _make_app(tmp_path)

    with TestClient(app) as client:
        reg = client.post(
            "/im/v1/auth/register",
            json={
                "username": "alice",
                "password": "pw12345678",
                "display_name": "Alice",
            },
        )
        token = reg.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        response = client.patch(
            "/im/v1/conversations/does-not-exist",
            json={"title": "Whatever"},
            headers=auth,
        )

    assert response.status_code == 404
