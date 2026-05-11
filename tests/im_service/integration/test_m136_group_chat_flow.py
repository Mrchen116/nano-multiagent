"""M136 group-chat real creation and multi-agent behavior coverage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.application.event_service import EventService
from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository
from personal_assistant.channels.base import OutboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeKernelClient:
    """Record gateway calls and synthesize agent-tagged replies."""

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self.default_output_text = "reply:{text}"
        self._session_index = 0
        self._run_index = 0

    def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ):
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title, "metadata": metadata}
        )
        return {"session_id": session_id}

    def send_message_async(self, *, session_id: str, texts: list[str], image_urls=None):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        rendered_text = "\n".join(texts)
        self.send_calls.append({"session_id": session_id, "text": rendered_text, "run_id": run_id})
        self.run_states[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "output_text": self.default_output_text.format(text=rendered_text),
        }
        return {"run_id": run_id}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _seed_user(client: TestClient, username: str) -> str:
    """Auth-aware seeding: first call registers + authorizes; subsequent calls seed under tenant."""
    from tests.im_service._auth_helpers import authorize, register_user, seed_user_under_owner

    if client.headers.get("Authorization") is None:
        user = register_user(client, username=username, display_name=username.title())
        authorize(client, user)
        return user.id
    me = client.get("/im/v1/me").json()
    return seed_user_under_owner(
        client, username=username, display_name=username.title(), owner_id=me["owner_id"]
    )



def _send_delivery_receipt(
    websocket,
    *,
    relay_payload: dict[str, object],
    delivery_status: str,
    detail: str | None,
) -> dict[str, object]:
    websocket.send_json(
        {
            "type": "node.delivery_receipt",
            "payload": {
                "node_id": "node-1",
                "relay_task_id": relay_payload["relay_task_id"],
                "delivery_status": delivery_status,
                "detail": detail,
            },
        }
    )
    while True:
        frame = websocket.receive_json()
        if frame.get("type") == "ack":
            return frame
        # Group completion may enqueue peer background-context relay frames. They are
        # legitimate side effects for other agents, but this helper only waits for the
        # receipt ack corresponding to the relay under test.
        assert frame.get("type") == "relay.message"
        assert frame.get("payload", {}).get("metadata", {}).get("background_context_only") is True
        continue



def _seed_node_and_profiles(app, *, owner_id: str = "", agent_ids: tuple[str, ...]) -> None:
    nodes = NodeRepository(app.state.connection)
    nodes.upsert_node(node_id="node-1", node_name="MacBook")
    profiles = AgentProfileRepository(app.state.connection)
    for agent_id in agent_ids:
        profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner_id,
            display_name=agent_id,
            description=f"profile for {agent_id}",
            system_prompt=f"You are {agent_id}.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-1", agent_id),
        )
    app.state.connection.commit()


def _agents(tmp_path: Path, *agent_ids: str) -> tuple[AgentWorkspaceConfig, ...]:
    agents: list[AgentWorkspaceConfig] = []
    for agent_id in agent_ids:
        workspace_root = tmp_path / agent_id
        workspace_root.mkdir()
        agents.append(
            AgentWorkspaceConfig(agent_id=agent_id, workspace_root=workspace_root, title=agent_id.title())
        )
    return tuple(agents)


def test_group_message_with_mention_and_no_reply_token_stays_silent(tmp_path: Path) -> None:
    """A mentioned group relay that returns NO_REPLY must complete without outbound chat text."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    kernel_client.default_output_text = "NO_REPLY"
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a", "agent-b")
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        agent_b_user_id = _seed_user(client, "agent:agent-b")
        _seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Quiet Group",
                "participant_ids": [user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a", "agent-b"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            posted = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-no-reply"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-a stay quiet",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame
                for frame in relay_frames
            }
            relay_adapter.accept_relay(relay_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(relay_frame_by_agent["agent-b"]["payload"])
            sent_ack = _send_delivery_receipt(
                websocket,
                relay_payload=relay_frame_by_agent["agent-a"]["payload"],
                delivery_status="sent",
                detail=None,
            )
            completed_ack = _send_delivery_receipt(
                websocket,
                relay_payload=relay_frame_by_agent["agent-a"]["payload"],
                delivery_status="completed",
                detail="NO_REPLY | suppressed_by=no_reply_token",
            )

        event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()

    accepted_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "relay.accepted"
    ]
    completed_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "relay.completed"
    ]
    assert kernel_client.send_calls == [{"session_id": "sess-1", "text": "[Alice] @agent-a stay quiet", "run_id": "run-1"}]
    assert relay_adapter.sent == []
    assert sent_ack["type"] == "ack"
    assert completed_ack["type"] == "ack"
    assert [payload["detail"] for payload in accepted_payloads] == [None]
    assert [payload["detail"] for payload in completed_payloads] == ["NO_REPLY | suppressed_by=no_reply_token"]


def test_group_conversation_creation_and_explicit_agent_mentions_roundtrip(tmp_path: Path) -> None:
    """Create a real group conversation and keep typed plus picker mentions pinned to their addressed agents."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a", "agent-b")
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        agent_b_user_id = _seed_user(client, "agent:agent-b")
        _seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Kernel Ops Group",
                "participant_ids": [user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert conversation.status_code == 201
        body = conversation.json()
        assert body["type"] == "group"
        conversation_id = body["id"]

        listed = client.get("/im/v1/conversations")
        assert listed.status_code == 200
        listed_items = listed.json()["items"]
        assert any(item["id"] == conversation_id and item["type"] == "group" for item in listed_items)

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a", "agent-b"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            first = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-a"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-a, please inspect rollout",
                    "target_node_id": "node-1",
                },
            )
            assert first.status_code == 201
            first_frames = [websocket.receive_json(), websocket.receive_json()]
            first_frame_by_agent = {
                frame["payload"]["agent_id"]: frame
                for frame in first_frames
            }
            relay_adapter.accept_relay(first_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(first_frame_by_agent["agent-b"]["payload"])

            second = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-b"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent:agent-b review the result",
                    "target_node_id": "node-1",
                },
            )
            assert second.status_code == 201
            second_frames = [websocket.receive_json(), websocket.receive_json()]
            second_frame_by_agent = {
                frame["payload"]["agent_id"]: frame
                for frame in second_frames
            }
            relay_adapter.accept_relay(second_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(second_frame_by_agent["agent-b"]["payload"])

    first_frame = first_frame_by_agent["agent-a"]
    second_frame = second_frame_by_agent["agent-b"]
    assert [call["title"] for call in kernel_client.create_session_calls] == ["Agent-A", "Agent-B"]
    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "config_profile_version": 1,
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": agent_a_user_id, "display_name": "A"},
                {"type": "agent", "agent_id": agent_b_user_id, "display_name": "B"},
            ],
        },
        {
            "agent_id": "agent-b",
            "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
            "config_profile_version": 1,
            "conversation_type": "group",
            "participant_agent_ids": ["agent-a", "agent-b"],
            "external_chat_id": conversation_id,
            "participants": [
                {"type": "user", "user_id": user_id, "display_name": "Alice"},
                {"type": "agent", "agent_id": agent_a_user_id, "display_name": "A"},
                {"type": "agent", "agent_id": agent_b_user_id, "display_name": "B"},
            ],
        },
    ]
    assert [call["text"] for call in kernel_client.send_calls] == [
        "[Alice] @agent-a, please inspect rollout",
        "[Alice] @agent:agent-b review the result",
    ]
    assert first_frame["payload"]["agent_id"] == "agent-a"
    assert first_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }
    assert second_frame["payload"]["agent_id"] == "agent-b"
    assert second_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-b"],
        "participant_agent_ids": ["agent-a", "agent-b"],
        "config_profile_version": 1,
    }
    assert relay_adapter.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="reply:[Alice] @agent-a, please inspect rollout",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": first_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-a:agent-a",
                "message_id": first_frame["payload"]["message"]["id"],
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-a"],
                "participant_agent_ids": ["agent-a", "agent-b"],
                "config_profile_version": 1,
                "sender_display_name": "Alice",
                "participants": [
                    {"id": user_id, "display_name": "Alice", "type": "user"},
                    {"id": agent_a_user_id, "display_name": "A", "type": "agent"},
                    {"id": agent_b_user_id, "display_name": "B", "type": "agent"},
                ],
            },
        ),
        OutboundMessage(
            channel_name="web_relay",
            text="reply:[Alice] @agent:agent-b review the result",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": second_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-b:agent-b",
                "message_id": second_frame["payload"]["message"]["id"],
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-b"],
                "participant_agent_ids": ["agent-a", "agent-b"],
                "config_profile_version": 1,
                "sender_display_name": "Alice",
                "participants": [
                    {"id": user_id, "display_name": "Alice", "type": "user"},
                    {"id": agent_a_user_id, "display_name": "A", "type": "agent"},
                    {"id": agent_b_user_id, "display_name": "B", "type": "agent"},
                ],
            },
        ),
    ]


def test_group_message_mentioning_two_agents_exposes_distinct_sse_identity_for_running_and_report_events(
    tmp_path: Path,
) -> None:
    """Backfill per-agent identity into SSE relay.processing/report events for one dual-mention turn."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-q", "agent-a")
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-q",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")
        agent_q_user_id = _seed_user(client, "agent:agent-q")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        _seed_node_and_profiles(app, agent_ids=("agent-q", "agent-a"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Dual Mention SSE Identity",
                "participant_ids": [user_id, agent_q_user_id, agent_a_user_id],
            },
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-q", "agent-a"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            posted = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-dual-sse"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-q @agent-a please review this rollout together",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame
                for frame in relay_frames
            }
            assert set(relay_frame_by_agent) == {"agent-q", "agent-a"}

            for agent_id, run_id in (("agent-q", "run-q"), ("agent-a", "run-a")):
                relay_payload = relay_frame_by_agent[agent_id]["payload"]
                _send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="sent",
                    detail=f"run_id={run_id}",
                )
                websocket.send_json(
                    {
                        "type": "node.report",
                        "payload": {
                            "node_id": "node-1",
                            "run_id": run_id,
                            "status": "running",
                            "agent_id": agent_id,
                            "conversation_id": conversation_id,
                            "message_id": relay_payload["message"]["id"],
                            "summary": f"{agent_id} is preparing a summary",
                        },
                    }
                )
                assert websocket.receive_json() == {
                    "type": "ack",
                    "payload": {"message_type": "node.report", "node_id": "node-1"},
                }
                websocket.send_json(
                    {
                        "type": "node.report",
                        "payload": {
                            "node_id": "node-1",
                            "run_id": run_id,
                            "status": "completed",
                            "agent_id": agent_id,
                            "conversation_id": conversation_id,
                            "message_id": relay_payload["message"]["id"],
                            "summary": f"{agent_id} finished the review",
                        },
                    }
                )
                assert websocket.receive_json() == {
                    "type": "ack",
                    "payload": {"message_type": "node.report", "node_id": "node-1"},
                }

        event_service = EventService(events=client.app.state.event_repository)
        enriched = event_service.list_events(conversation_id=conversation_id, after_event_id=0, limit=200)
        sse_events = [
            (ev.event_type, json.loads(ev.payload_json))
            for ev in enriched
            if ev.event_type in ("relay.processing", "relay.report")
        ]

    processing_payloads = [payload for event_type, payload in sse_events if event_type == "relay.processing"]
    report_payloads = [payload for event_type, payload in sse_events if event_type == "relay.report"]
    assert {payload["agent_id"] for payload in processing_payloads} == {"agent-q", "agent-a"}
    assert {payload["relay_task_id"] for payload in processing_payloads} == {
        relay_frame_by_agent["agent-q"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
    }
    assert {payload["agent_id"] for payload in report_payloads} == {"agent-q", "agent-a"}
    assert {payload["relay_task_id"] for payload in report_payloads} == {
        relay_frame_by_agent["agent-q"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
    }



def test_group_message_mentioning_two_agents_persists_distinct_completion_events(tmp_path: Path) -> None:
    """Keep per-agent receipt identity distinct when one group message mentions two agents."""

    app = create_app(db_path=tmp_path / "im.db")
    kernel_client = _FakeKernelClient()
    relay_adapter = WebRelayAdapter()
    agents = _agents(tmp_path, "agent-a", "agent-b")
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    relay_adapter.start(lambda inbound: asyncio.run(pipeline.handle_inbound(inbound)))

    with TestClient(app) as client:
        user_id = _seed_user(client, "alice")
        agent_a_user_id = _seed_user(client, "agent:agent-a")
        agent_b_user_id = _seed_user(client, "agent:agent-b")
        _seed_node_and_profiles(app, agent_ids=("agent-a", "agent-b"))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Dual Mention Group",
                "participant_ids": [user_id, agent_a_user_id, agent_b_user_id],
            },
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "MacBook",
                        "version": "1.0.0",
                        "agents": ["agent-a", "agent-b"],
                        "capabilities": {"relay": True},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            posted = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-dual"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-a @agent-b please review this rollout together",
                    "target_node_id": "node-1",
                },
            )
            assert posted.status_code == 201
            relay_frames = [websocket.receive_json(), websocket.receive_json()]
            relay_frame_by_agent = {
                frame["payload"]["agent_id"]: frame
                for frame in relay_frames
            }
            assert set(relay_frame_by_agent) == {"agent-a", "agent-b"}

            relay_adapter.accept_relay(relay_frame_by_agent["agent-a"]["payload"])
            relay_adapter.accept_relay(relay_frame_by_agent["agent-b"]["payload"])

            for agent_id in ("agent-a", "agent-b"):
                relay_payload = relay_frame_by_agent[agent_id]["payload"]
                sent_ack = _send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="sent",
                    detail=f"run_id={agent_id}",
                )
                completed_ack = _send_delivery_receipt(
                    websocket,
                    relay_payload=relay_payload,
                    delivery_status="completed",
                    detail=f"reply from {agent_id}",
                )
                assert sent_ack["type"] == "ack"
                assert completed_ack["type"] == "ack"

        event_rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()

    completed_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "relay.completed"
    ]
    delivered_payloads = [
        json.loads(row["payload_json"])
        for row in event_rows
        if row["event_type"] == "message.delivered"
    ]
    assert [call["text"] for call in kernel_client.send_calls] == [
        "[Alice] @agent-a @agent-b please review this rollout together",
        "[Alice] @agent-a @agent-b please review this rollout together",
    ]
    assert {payload["agent_id"] for payload in completed_payloads} == {"agent-a", "agent-b"}
    assert {payload["relay_task_id"] for payload in completed_payloads} == {
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-b"]["payload"]["relay_task_id"],
    }
    assert [payload["detail"] for payload in sorted(completed_payloads, key=lambda payload: payload["agent_id"])] == [
        "reply from agent-a",
        "reply from agent-b",
    ]
    assert {payload["agent_id"] for payload in delivered_payloads} == {"agent-a", "agent-b"}
    assert {payload["relay_task_id"] for payload in delivered_payloads} == {
        relay_frame_by_agent["agent-a"]["payload"]["relay_task_id"],
        relay_frame_by_agent["agent-b"]["payload"]["relay_task_id"],
    }
