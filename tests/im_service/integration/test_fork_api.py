"""feat-445-M1 R4: POST /im/v1/conversations/{id}/fork route wiring + error mapping."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from .conftest import authorize, register_user


def test_fork_unknown_conversation_returns_404(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user = register_user(client, username="alice")
        authorize(client, user)
        resp = client.post(
            "/im/v1/conversations/does-not-exist/fork",
            json={"fork_message_id": "whatever"},
        )
        assert resp.status_code == 404, resp.text


def test_fork_requires_auth(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        resp = client.post(
            "/im/v1/conversations/some-conv/fork",
            json={"fork_message_id": "m1"},
        )
        assert resp.status_code in (401, 403), resp.text
