"""Contract tests for human chat flow error handling."""
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from tests.im_service._auth_helpers import authorize, register_user


def test_messages_return_404_for_unknown_conversation(tmp_path: Path) -> None:
    """Keep not-found semantics stable for未知会话下的消息/元数据接口。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        messages_resp = client.get("/im/v1/conversations/missing/messages")
        detail_resp = client.get("/im/v1/conversations/missing")
        patch_resp = client.patch("/im/v1/conversations/missing", json={"is_pinned": True})

    assert messages_resp.status_code == 404
    assert messages_resp.json()["detail"] == "conversation_id not found"
    assert detail_resp.status_code == 404
    assert detail_resp.json()["detail"] == "conversation_id not found"
    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "conversation_id not found"
