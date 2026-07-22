"""Contract tests for IM gateway websocket protocol envelopes."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.ws.gateway_protocol import (
    parse_delivery_receipt_event,
    parse_node_report_event,
    parse_relay_message_frame,
    parse_streaming_delta_event,
)
from tests.im_service._auth_helpers import register_and_authorize


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


def test_streaming_delta_parser_ignores_unrelated_bad_structured_fields() -> None:
    event = parse_streaming_delta_event(
        {
            "kind": "message_completed",
            "message_id": "assistant-msg-1",
            "final_content": "done",
            "tool_call": "stale-bad-field",
            "permission_request": [],
        }
    )

    assert event.kind == "message_completed"
    assert event.message_id == "assistant-msg-1"
    assert event.tool_call is None
    assert event.permission_request is None


def test_streaming_delta_parser_ignores_unrelated_bad_text_fields() -> None:
    event = parse_streaming_delta_event(
        {
            "kind": "message_delta",
            "message_id": "assistant-msg-1",
            "delta_text": "next",
            "agent_id": 1,
            "reason": [],
        }
    )

    assert event.kind == "message_delta"
    assert event.message_id == "assistant-msg-1"
    assert event.delta_text == "next"
    assert event.agent_id is None
    assert event.reason is None


def test_streaming_delta_parser_reads_message_discard_tombstone() -> None:
    event = parse_streaming_delta_event(
        {
            "kind": "message_discarded",
            "message_id": "assistant-msg-1",
            "run_id": "run-1",
            "reason": "no_reply_token",
        }
    )

    assert event.kind == "message_discarded"
    assert event.message_id == "assistant-msg-1"
    assert event.run_id == "run-1"
    assert event.reason == "no_reply_token"


def test_node_report_parser_ignores_legacy_unstructured_detail_and_usage() -> None:
    event = parse_node_report_event(
        {
            "node_id": "node-1",
            "run_id": "run-1",
            "status": "completed",
            "detail": "phase=final",
            "usage": {"prompt_tokens": "10", "completion_tokens": 2},
        }
    )

    assert event.node_id == "node-1"
    assert event.run_id == "run-1"
    assert event.status == "completed"
    assert event.detail is None
    assert event.usage is None


def test_gateway_websocket_rejects_invalid_message_shape(tmp_path: Path) -> None:
    """Keep invalid websocket payload errors stable for protocol clients."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        register_and_authorize(client)
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
        register_and_authorize(client)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json({"type": "unknown.type", "payload": {}})
            response = websocket.receive_json()

    assert response == {
        "type": "error",
        "payload": {
            "code": "unsupported_message_type",
            "message": "unknown.type",
            "message_type": "unknown.type",
        },
    }


def test_gateway_boundary_is_idempotent_and_appears_before_its_anchor(
    tmp_path: Path,
) -> None:
    """Persist one non-message configuration boundary through the Gateway wire entrypoint."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_and_authorize(client)
        agent_user_id = ""
        from tests.im_service._auth_helpers import seed_user_under_owner

        agent_user_id = seed_user_under_owner(
            client,
            username="agent:planner",
            owner_id=owner.owner_id,
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Planner",
                "participant_ids": [owner.id, agent_user_id],
            },
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner.id, "content": "use the new runtime"},
        )
        assert anchor.status_code == 201, anchor.text
        anchor_id = anchor.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            frame = {
                "type": "agent.config.boundary",
                "payload": {
                    "boundary_id": "boundary-1",
                    "node_id": "node-1",
                    "conversation_id": conversation_id,
                    "agent_id": "planner",
                    "before_message_id": anchor_id,
                    "runtime_fingerprint": "runtime-sha256",
                    "fingerprint_schema": "v1",
                    "profile_version": 7,
                    "applied_at": "2026-07-21T00:00:00Z",
                },
            }
            websocket.send_json(frame)
            first_ack = websocket.receive_json()
            websocket.send_json(frame)
            second_ack = websocket.receive_json()

        assert first_ack["type"] == "ack"
        assert second_ack["type"] == "ack"
        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"] == [
            {
                "type": "agent_config_changed",
                "id": "boundary-1",
                "conversation_id": conversation_id,
                "agent_id": "planner",
                "before_message_id": anchor_id,
                "applied_at": "2026-07-21T00:00:00Z",
            },
            {
                "type": "message",
                "message": {
                    **anchor.json(),
                },
            },
        ]
        rows = app.state.connection.execute(
            "SELECT COUNT(*) AS count FROM agent_config_boundaries"
        ).fetchone()
        assert rows["count"] == 1


def test_gateway_boundary_accepts_nullable_provenance_once_after_im_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay an offline Gateway intent after IM restarts without duplicating it."""
    monkeypatch.setenv("IM_JWT_SECRET", "nullable-provenance-restart-secret")
    db_path = tmp_path / "im.db"
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        owner = register_and_authorize(client)
        authorization = client.headers["Authorization"]
        from tests.im_service._auth_helpers import seed_user_under_owner

        agent_user_id = seed_user_under_owner(
            client,
            username="agent:planner",
            owner_id=owner.owner_id,
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Planner",
                "participant_ids": [owner.id, agent_user_id],
            },
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner.id, "content": "external runtime change"},
        )
        assert anchor.status_code == 201, anchor.text
        frame = {
            "type": "agent.config.boundary",
            "payload": {
                "boundary_id": "nullable-provenance-boundary",
                "node_id": "node-1",
                "conversation_id": conversation_id,
                "agent_id": "planner",
                "before_message_id": anchor.json()["id"],
                "runtime_fingerprint": "runtime-sha256",
                "fingerprint_schema": "v1",
                "profile_version": None,
                "applied_at": "2026-07-22T00:00:00Z",
            },
        }
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            websocket.send_json(frame)
            assert websocket.receive_json()["type"] == "ack"

    restarted_app = create_app(db_path=db_path)
    with TestClient(restarted_app) as client:
        client.headers["Authorization"] = authorization
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            websocket.send_json(frame)
            assert websocket.receive_json()["type"] == "ack"

        timeline = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert timeline.status_code == 200, timeline.text
        assert [item["type"] for item in timeline.json()["items"]] == [
            "agent_config_changed",
            "message",
        ]
        rows = restarted_app.state.connection.execute(
            "SELECT COUNT(*) AS count FROM agent_config_boundaries"
        ).fetchone()
        assert rows["count"] == 1


def test_gateway_boundary_rejects_conflicting_reuse_of_stable_identity(
    tmp_path: Path,
) -> None:
    """A Gateway retry may reuse its identity only for the same durable fact."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_and_authorize(client)
        from tests.im_service._auth_helpers import seed_user_under_owner

        agent_user_id = seed_user_under_owner(
            client,
            username="agent:planner",
            owner_id=owner.owner_id,
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Planner",
                "participant_ids": [owner.id, agent_user_id],
            },
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        first_anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner.id, "content": "first"},
        )
        second_anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner.id, "content": "second"},
        )
        assert first_anchor.status_code == 201, first_anchor.text
        assert second_anchor.status_code == 201, second_anchor.text

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            common = {
                "boundary_id": "stable-boundary-id",
                "node_id": "node-1",
                "conversation_id": conversation_id,
                "agent_id": "planner",
                "runtime_fingerprint": "runtime-a",
                "fingerprint_schema": "v1",
                "profile_version": 1,
                "applied_at": "2026-07-21T00:00:00Z",
            }
            websocket.send_json(
                {
                    "type": "agent.config.boundary",
                    "payload": {
                        **common,
                        "before_message_id": first_anchor.json()["id"],
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            websocket.send_json(
                {
                    "type": "agent.config.boundary",
                    "payload": {
                        **common,
                        "before_message_id": second_anchor.json()["id"],
                    },
                }
            )
            rejected = websocket.receive_json()

    assert rejected == {
        "type": "error",
        "payload": {
            "code": "invalid_message",
            "message": "boundary_id conflicts with persisted boundary",
        },
    }


def test_gateway_websocket_error_correlates_rejected_agent_message(
    tmp_path: Path,
) -> None:
    """A connected Gateway must know which queued frame an IM error rejects."""

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        register_and_authorize(client)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": []},
                }
            )
            assert websocket.receive_json() == {
                "type": "ack",
                "payload": {"message_type": "node.register", "node_id": "node-1"},
            }
            websocket.send_json(
                {
                    "type": "agent.message",
                    "payload": {
                        "node_id": "node-1",
                        "from_session_id": "unknown-source",
                        "to": "conversation:missing",
                        "text": "not delivered",
                    },
                }
            )
            response = websocket.receive_json()

    assert response["type"] == "error"
    assert response["payload"] == {
        "code": "invalid_agent_message",
        "message": "username not found: agent:unknown-source",
        "message_type": "agent.message",
    }
