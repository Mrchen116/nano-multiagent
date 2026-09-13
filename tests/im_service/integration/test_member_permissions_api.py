"""Real HTTP/WS member decisions, original-node routing and restart replay."""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.nodes import NodeRepository
from tests.im_service._auth_helpers import authorize, register_user


@contextmanager
def _gateway(client, owner, *, node="worker-node", agent="worker"):
    NodeRepository(client.app.state.connection).upsert_node(
        node_id=node, node_name=node, owner_id=owner.id
    )
    with client.websocket_connect(
        "/im/ws/gateway", headers={"Authorization": f"Bearer {owner.access_token}"}
    ) as ws:
        ws.send_json(
            {
                "type": "node.register",
                "payload": {
                    "node_id": node,
                    "node_name": node,
                    "agents": [agent],
                    "capabilities": {},
                },
            }
        )
        assert ws.receive_json()["type"] == "ack"
        yield ws


def _delta(ws, **payload):
    ws.send_json(
        {
            "type": "node.streaming_delta",
            "payload": {
                "node_id": "worker-node",
                "run_id": "original-run",
                **payload,
            },
        }
    )
    return ws.receive_json()


def _card(client, owner, bob, ws):
    authorize(client, owner)
    response = client.post(
        "/im/v1/conversations",
        json={
            "type": "group",
            "title": "Shared work",
            "participant_ids": [
                f"user:{owner.id}",
                f"user:{bob.id}",
                "agent:worker",
            ],
        },
    )
    assert response.status_code == 201, response.text
    cid = response.json()["id"]
    started = _delta(ws, kind="turn_start", conversation_id=cid, agent_id="worker")
    assert started["type"] == "ack", started
    mid = started["payload"]["message_id"]
    request = {
        "request_id": "ask-1",
        "tool_name": "bash",
        "question": "Run?",
        "options": [{"id": "allow_once"}, {"id": "allow_always"}, {"id": "deny"}],
    }
    pending = _delta(
        ws, kind="permission_request", message_id=mid, permission_request=request
    )
    assert pending["type"] == "ack", pending
    return cid, mid, request


def _decide(client, member, cid, mid, decision, reason=None):
    return client.post(
        f"/im/v1/conversations/{cid}/permissions/ask-1",
        headers={"Authorization": f"Bearer {member.access_token}"},
        json={"message_id": mid, "decision": decision, "reason": reason},
    )


@pytest.mark.parametrize(
    "choice,reason,expected_reason",
    [
        ("allow_always", None, None),
        ("deny", "  先别动文件  ", "先别动文件"),
        ("deny", "   ", None),
    ],
)
def test_any_member_submits_once_and_only_original_gateway_resolves(
    tmp_path, choice, reason, expected_reason
):
    with TestClient(create_app(db_path=tmp_path / "im.db")) as client:
        owner = register_user(client, username="owner")
        bob = register_user(client, username="bob")
        outsider = register_user(client, username="outsider")
        with _gateway(client, owner) as ws:
            cid, mid, request = _card(client, owner, bob, ws)
            assert _decide(client, outsider, cid, mid, choice).status_code == 404
            assert _decide(client, bob, cid, mid, "invented").status_code == 409
            first = _decide(client, bob, cid, mid, choice, reason)
            assert first.status_code == 200, first.text
            assert first.json()["status"] == "submitted"
            assert first.json()["decided_by"] == bob.id
            forwarded = ws.receive_json()
            assert forwarded["type"] == "node.streaming_delta"
            assert forwarded["payload"]["decision"] == choice
            assert forwarded["payload"]["message_id"] == mid
            assert (forwarded["payload"].get("reason") or None) == expected_reason
            duplicate = _decide(client, owner, cid, mid, "allow_once")
            assert duplicate.json() == first.json()
            assert ws.receive_json()["payload"]["decision"] == choice
            # An outbox replay cannot reopen a card already decided by a member.
            assert (
                _delta(
                    ws,
                    kind="permission_request",
                    message_id=mid,
                    permission_request=request,
                )["type"]
                == "ack"
            )
            saved = client.app.state.message_repository.get_message(message_id=mid)
            assert saved.permission_requests[0]["status"] == "submitted"
            bad = _delta(
                ws,
                kind="permission_resolved",
                message_id=mid,
                request_id="ask-1",
                decision=choice,
                run_id="different-run",
            )
            assert bad["type"] == "error"
            done = _delta(
                ws,
                kind="permission_resolved",
                message_id=mid,
                request_id="ask-1",
                decision=choice,
            )
            assert done["type"] == "ack", done
            assert (
                _decide(client, owner, cid, mid, choice).json()["status"] == "resolved"
            )


def test_offline_decision_survives_im_restart_and_replays_to_original_node(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("IM_JWT_SECRET", "permission-restart-test-secret-32-bytes")
    db = tmp_path / "im.db"
    with TestClient(create_app(db_path=db)) as client:
        owner = register_user(client, username="owner")
        bob = register_user(client, username="bob")
        with _gateway(client, owner) as ws:
            cid, mid, _ = _card(client, owner, bob, ws)
        response = _decide(client, bob, cid, mid, "allow_once")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "submitted"
    with TestClient(create_app(db_path=db)) as restarted:
        with _gateway(restarted, owner) as ws:
            replay = ws.receive_json()
            assert replay["type"] == "node.streaming_delta"
            assert replay["payload"]["message_id"] == mid
            assert replay["payload"]["request_id"] == "ask-1"
            assert replay["payload"]["decision"] == "allow_once"
            assert (
                _delta(
                    ws,
                    kind="permission_resolved",
                    message_id=mid,
                    request_id="ask-1",
                    decision="allow_once",
                )["type"]
                == "ack"
            )


def test_registered_gateway_cannot_write_another_nodes_agent_message(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "im.db")) as client:
        owner = register_user(client, username="owner")
        bob = register_user(client, username="bob")
        with _gateway(client, owner) as worker:
            cid, mid, _ = _card(client, owner, bob, worker)
            with _gateway(client, bob, node="other-node", agent="other-agent") as other:
                for payload in (
                    {
                        "kind": "turn_start",
                        "conversation_id": cid,
                        "agent_id": "worker",
                    },
                    {
                        "kind": "message_delta",
                        "message_id": mid,
                        "delta_text": "forged",
                    },
                    {
                        "kind": "permission_request",
                        "message_id": mid,
                        "permission_request": {"request_id": "forged", "options": []},
                    },
                ):
                    response = _delta(other, node_id="other-node", **payload)
                    assert response["type"] == "error", response
                message = client.app.state.message_repository.get_message(
                    message_id=mid
                )
                assert message.content == ""
                assert len(message.permission_requests) == 1
