"""Protect authenticated work transport, conversation scope and live permission routing."""

import threading
import pytest
from fastapi.testclient import TestClient
from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.nodes import NodeRepository
from .conftest import authorize, register_user, seed_user_under_owner


@pytest.mark.parametrize("recover_im", [False, True])
def test_work_http_journal_query_and_permission_share_real_ownership(
    tmp_path, recover_im
):
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        stranger = register_user(client, username="stranger")
        authorize(client, owner)
        db = app.state.connection
        NodeRepository(db).upsert_node(
            node_id="node", node_name="Node", owner_id=owner.owner_id
        )
        AgentProfileRepository(db).create_profile(
            agent_id="global",
            owner_id=owner.owner_id,
            node_id="node",
            display_name="Global",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model=None,
            workspace_root=None,
            work_mode="global",
        )
        agent_user = seed_user_under_owner(
            client, username="agent:global", owner_id=owner.owner_id
        )
        conversations = ConversationRepository(db)
        visible = conversations.create_conversation(
            title="Public",
            participant_ids=[owner.id, agent_user],
            caller_owner_id=owner.owner_id,
        )
        private = conversations.create_conversation(
            title="Private",
            participant_ids=[owner.id, stranger.id],
            caller_owner_id=owner.owner_id,
        )
        message = MessageRepository(db).create_message(
            conversation_id=visible.id,
            sender_user_id=owner.id,
            sender_type="user",
            content="Remember the real constraint",
            attachments=[],
        )
        base = "/im/v1/agents/global/work"

        def event(seq, kind, payload, turn="turn"):
            return dict(
                seq=seq,
                event_id=f"event-{seq}",
                root_agent_id="global",
                session_id="main",
                turn_id=turn,
                type=kind,
                observed_at="2026-09-09T00:00:00Z",
                payload=payload,
            )

        with client.websocket_connect("/im/ws/gateway") as ws:
            ws.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node",
                        "agents": ["global"],
                        "agent_work_modes": {"global": "global"},
                        "capabilities": {},
                    },
                }
            )
            assert ws.receive_json()["type"] == "ack"
            # Global main execution stays in the journal; an isolated cron's
            # explicit final delivery still uses the owner-direct message route.
            delivery = {
                "node_id": "node",
                "kind": "turn_start",
                "agent_id": "global",
                "to_user_id": owner.id,
                "run_id": "cron-final",
            }
            ws.send_json({"type": "node.streaming_delta", "payload": delivery})
            assert (
                ws.receive_json()["payload"]["code"] == "global_work_requires_journal"
            )
            ws.send_json(
                {
                    "type": "node.streaming_delta",
                    "payload": {**delivery, "delivery_source": "cron"},
                }
            )
            cron_ack = ws.receive_json()
            assert cron_ack["type"] == "ack"
            assert cron_ack["payload"]["message_id"]
            events = [
                event(1, "session_registered", {"scope": "global_main"}, None),
                event(2, "turn_started", {"origin": "user", "model": "fixture"}),
                event(
                    3,
                    "permission_request",
                    {
                        "request_id": "permit",
                        "tool_name": "bash",
                        "tool_input": {"command": "pwd"},
                        "question": "Allow?",
                        "options": [
                            {
                                "id": "allow_once",
                                "label": "Allow once",
                                "description": "",
                            },
                            {"id": "deny", "label": "Deny", "description": ""},
                        ],
                    },
                ),
            ]
            batch = {
                "node_id": "node",
                "journal_id": "j",
                "from_seq": 1,
                "events": events,
            }
            ws.send_json({"type": "agent.work.append", "payload": batch})
            assert ws.receive_json() == {
                "type": "agent.work.ack",
                "payload": {"journal_id": "j", "through_seq": 3},
            }
            view = client.get(base).json()
            assert view["node_connection_state"] == "online"
            assert view["main_execution"] == "waiting_permission"
            assert view["turns"][0]["items"][0]["payload"]["tool_input"] == {
                "command": "pwd"
            }
            ws.send_json({"type": "agent.work.append", "payload": batch})
            assert ws.receive_json()["payload"]["through_seq"] == 3
            assert len(client.get(base).json()["turns"][0]["items"]) == 1
            renamed = client.patch(
                f"/im/v1/conversations/{visible.id}", json={"title": "My custom chat"}
            )
            assert renamed.status_code == 200
            assert renamed.json()["title"] == "My custom chat"
            ws.send_json(
                {
                    "type": "conversation.query",
                    "payload": {
                        "node_id": "node",
                        "request_id": "names",
                        "agent_id": "global",
                        "session_id": "main",
                        "action": "describe",
                        "targets": [visible.id, private.id],
                    },
                }
            )
            names = ws.receive_json()["payload"]
            assert names["ok"] is True
            rows = names["result"]["conversations"]
            assert [row["target"] for row in rows] == [visible.id]
            assert rows[0]["name"] == "My custom chat"
            assert any(
                p["id"] == owner.id and p["name"] == owner.display_name
                for p in rows[0]["participants"]
            )
            assert "messages" not in names["result"]
            for target, expected in [(visible.id, True), (private.id, False)]:
                ws.send_json(
                    {
                        "type": "conversation.query",
                        "payload": {
                            "node_id": "node",
                            "request_id": "read",
                            "agent_id": "global",
                            "session_id": "main",
                            "action": "read",
                            "target": target,
                            "limit": 20,
                        },
                    }
                )
                result = ws.receive_json()["payload"]
                assert result["ok"] is expected
                if expected:
                    assert result["result"]["messages"][0]["message_id"] == message.id
                    assert result["result"]["messages"][0]["content"] == [
                        {"type": "text", "text": "Remember the real constraint"}
                    ]
                else:
                    assert result["error"] == "target_not_accessible"
            assert (
                client.post(
                    f"{base}/permissions/permit", json={"decision": "allow_always"}
                ).status_code
                == 409
            )
            if recover_im:
                app.state.work_repository.mark_active_unknown()
                ws.send_json({"type": "agent.work.append", "payload": batch})
                assert ws.receive_json()["payload"]["through_seq"] == 3
                assert client.get(base).json()["turns"][0]["status"] == "unknown"
                assert (
                    app.state.work_repository.pending_permission("global", "permit")[
                        "session_id"
                    ]
                    == "main"
                )
            holder = {}
            worker = threading.Thread(
                target=lambda: holder.setdefault(
                    "response",
                    client.post(
                        f"{base}/permissions/permit",
                        json={"decision": "deny", "reason": "keep current files"},
                    ),
                )
            )
            worker.start()
            control = ws.receive_json()
            assert control == {
                "type": "agent.work.permission",
                "payload": {
                    "request_id": "permit",
                    "root_agent_id": "global",
                    "session_id": "main",
                    "decision": "deny",
                    "reason": "keep current files",
                },
            }
            ws.send_json(
                {
                    "type": "agent.work.permission.result",
                    "payload": {"node_id": "node", "request_id": "permit", "ok": True},
                }
            )
            assert ws.receive_json()["type"] == "ack"
            worker.join(2)
            assert holder["response"].status_code == 200
            ws.send_json(
                {
                    "type": "agent.work.append",
                    "payload": {
                        "node_id": "node",
                        "journal_id": "j",
                        "from_seq": 4,
                        "events": [
                            event(
                                4,
                                "permission_resolved",
                                {"request_id": "permit", "decision": "deny"},
                            )
                        ],
                    },
                }
            )
            assert ws.receive_json()["payload"]["through_seq"] == 4
            assert (
                client.post(
                    f"{base}/permissions/permit", json={"decision": "deny"}
                ).status_code
                == 409
            )
            assert (
                client.patch(
                    "/im/v1/agents/global/config",
                    json={
                        "profile_version": 1,
                        "display_name": "Global",
                        "group_reply_policy": "ALWAYS",
                        "work_mode": "single_thread",
                    },
                ).status_code
                == 409
            )
            assert client.get(f"{base}/sessions/unrelated/turns").status_code == 404
            authorize(client, stranger)
            assert client.get(base).status_code == 404
            authorize(client, owner)
        assert client.get(base).json()["node_connection_state"] == "offline"
        assert client.get("/im/v1/agents/global/config").json()["work_mode"] == "global"


def test_history_cursor_is_bounded_and_keeps_snapshot_across_reopen(tmp_path):
    from uuid import uuid4
    from IM.application.work_conversations import WorkConversationQuery
    from IM.infra.repositories.agent_work import AgentWorkRepository

    app = create_app(db_path=tmp_path / "history.db")
    with TestClient(app) as client:
        owner = register_user(client, username="history-owner")
        db = app.state.connection
        NodeRepository(db).upsert_node(
            node_id="node", node_name="Node", owner_id=owner.owner_id
        )
        AgentProfileRepository(db).create_profile(
            agent_id="global",
            owner_id=owner.owner_id,
            node_id="node",
            display_name="Global",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model=None,
            workspace_root=None,
            work_mode="global",
        )
        agent_user = seed_user_under_owner(
            client, username="agent:global", owner_id=owner.owner_id
        )
        room = ConversationRepository(db).create_conversation(
            title="History",
            participant_ids=[owner.id, agent_user],
            caller_owner_id=owner.owner_id,
        )
        work = app.state.work_repository
        work.append(
            node_id="node",
            journal_id="history",
            from_seq=1,
            events=[
                dict(
                    seq=1,
                    event_id="register",
                    root_agent_id="global",
                    session_id="main",
                    turn_id=None,
                    type="session_registered",
                    observed_at="2026-09-09T00:00:00Z",
                    payload={"scope": "global_main"},
                )
            ],
        )
        ids = [uuid4().hex for _ in range(10000)]
        with db:
            db.executemany(
                "INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES (?,?,?,'user',?,'completed',?)",
                [
                    (key, room.id, owner.id, "old constraint", f"2026-09-09T{i:05d}")
                    for i, key in enumerate(ids)
                ],
            )
        params = dict(
            node_id="node",
            agent_id="global",
            session_id="main",
            action="read",
            target=room.id,
            limit=1,
        )
        query = WorkConversationQuery(db, work)
        first = query.query(**params)
        assert first["messages"][0]["message_id"] == ids[-1]
        assert len(first["next_cursor"]) < 256
        MessageRepository(db).create_message(
            conversation_id=room.id,
            sender_user_id=owner.id,
            sender_type="user",
            content="new arrival",
            attachments=[],
        )
        # A new query/repository instance still resolves the durable snapshot.
        reopened = WorkConversationQuery(db, AgentWorkRepository(db))
        second = reopened.query(**params, cursor=first["next_cursor"])
        assert second["messages"][0]["message_id"] == ids[-2]
        assert len(second["next_cursor"]) < 256
        assert (
            db.execute("SELECT COUNT(*) FROM agent_work_query_snapshots").fetchone()[0]
            == 1
        )
        with pytest.raises(ValueError, match="invalid_cursor"):
            reopened.query(
                **{**params, "target": "another"}, cursor=first["next_cursor"]
            )
        with db:
            db.execute(
                "DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?",
                (room.id, agent_user),
            )
        with pytest.raises(ValueError, match="target_not_accessible"):
            reopened.query(**params, cursor=second["next_cursor"])
