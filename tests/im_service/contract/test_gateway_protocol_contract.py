"""Contract tests for IM gateway websocket protocol envelopes."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_gateway_websocket_rejects_invalid_message_shape(tmp_path: Path) -> None:
    """Keep invalid websocket payload errors stable for protocol clients."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_text("not-json")
            response = websocket.receive_json()

    assert response == {
        "type": "error",
        "payload": {"code": "invalid_message", "message": "message must be valid JSON"},
    }


def test_gateway_websocket_rejects_unsupported_message_types(tmp_path: Path) -> None:
    """Keep unsupported websocket type errors stable for protocol clients."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json({"type": "unknown.type", "payload": {}})
            response = websocket.receive_json()

    assert response == {
        "type": "error",
        "payload": {"code": "unsupported_message_type", "message": "unknown.type"},
    }
