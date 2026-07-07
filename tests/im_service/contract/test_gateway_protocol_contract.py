"""Contract tests for IM gateway websocket protocol envelopes."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.ws.gateway_protocol import (
    parse_delivery_receipt_event,
    parse_node_report_event,
    parse_relay_message_frame,
    parse_streaming_delta_event,
)


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "gateway_runtime_protocol.json"
)


def _fixture() -> dict[str, dict[str, object]]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_gateway_runtime_protocol_fixture_parses_typed_events() -> None:
    """Lock the IM-side parser to relay/streaming/receipt external identity fields."""
    fixture = _fixture()

    relay = parse_relay_message_frame(fixture["relay_message"])
    assert relay.relay_task_id == "relay-task-1"
    assert relay.message_id == "msg-1"
    assert relay.agent_id == "agent-a"
    assert relay.external_source == "feishu"
    assert relay.external_chat_id == "oc_product"
    assert relay.conversation_type == "group"
    assert relay.trigger_source == "im"

    streaming = parse_streaming_delta_event(fixture["streaming_delta"])
    assert streaming.kind == "message_completed"
    assert streaming.run_id == "run-1"
    assert streaming.message_id == "assistant-msg-1"
    assert streaming.delivery_status == "completed"
    assert streaming.token_usage == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
    }

    receipt = parse_delivery_receipt_event(fixture["delivery_receipt"])
    assert receipt.node_id == "node-1"
    assert receipt.relay_task_id == "relay-task-1"
    assert receipt.delivery_status == "completed"
    assert receipt.detail == "fixture reply"
    assert receipt.target == "im-conv-1"

    report = parse_node_report_event(fixture["node_report"])
    assert report.node_id == "node-1"
    assert report.run_id == "run-1"
    assert report.status == "completed"
    assert report.agent_id == "agent-a"
    assert report.session_key == "feishu:oc_product:agent-a"
    assert report.usage == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
    }


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
