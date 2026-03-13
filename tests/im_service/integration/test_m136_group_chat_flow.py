"""M136 group-chat real creation and multi-agent behavior coverage."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

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

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        self.run_states[run_id] = {"run_id": run_id, "output_text": self.default_output_text.format(text=text)}
        return {"run_id": run_id}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _seed_user(client: TestClient, username: str) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


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
    agents = _agents(tmp_path, "agent-a")
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
        _seed_node_and_profiles(app, agent_ids=("agent-a",))

        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Quiet Group",
                "participant_ids": [user_id, agent_a_user_id],
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
                        "agents": ["agent-a"],
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
            relay_frame = websocket.receive_json()
            relay_adapter.accept_relay(
                {
                    **relay_frame["payload"],
                    "is_group": True,
                    "mentioned_agent_ids": ["agent-a"],
                }
            )

            receipt_frame = websocket.receive_json()
            completed_frame = websocket.receive_json()

    assert kernel_client.send_calls == [{"session_id": "sess-1", "text": "@agent-a stay quiet", "run_id": "run-1"}]
    assert relay_adapter.sent == []
    assert receipt_frame["type"] == "node.delivery_receipt"
    assert receipt_frame["payload"]["delivery_status"] == "sent"
    assert completed_frame["type"] == "node.delivery_receipt"
    assert completed_frame["payload"]["delivery_status"] == "completed"
    assert completed_frame["payload"]["detail"] == "NO_REPLY | suppressed_by=no_reply_token"


def test_group_conversation_creation_and_explicit_agent_mentions_roundtrip(tmp_path: Path) -> None:
    """Create a real group conversation and keep each explicit mention pinned to its addressed agent."""

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
            first_frame = websocket.receive_json()
            relay_adapter.accept_relay(
                {
                    **first_frame["payload"],
                    "is_group": True,
                    "mentioned_agent_ids": ["agent-a"],
                }
            )

            second = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                headers={"Idempotency-Key": "idem-group-b"},
                json={
                    "sender_user_id": user_id,
                    "content": "@agent-b, review the result",
                    "target_node_id": "node-1",
                },
            )
            assert second.status_code == 201
            second_frame = websocket.receive_json()
            relay_adapter.accept_relay(
                {
                    **second_frame["payload"],
                    "is_group": True,
                    "mentioned_agent_ids": ["agent-b"],
                }
            )

    assert [call["title"] for call in kernel_client.create_session_calls] == ["Agent-A", "Agent-B"]
    assert [call["metadata"] for call in kernel_client.create_session_calls] == [
        {
            "agent_id": "agent-a",
            "config_profile_version": 1,
            "system_prompt": "You are agent-a.",
        },
        {
            "agent_id": "agent-b",
            "config_profile_version": 1,
            "system_prompt": "You are agent-b.",
        },
    ]
    assert [call["text"] for call in kernel_client.send_calls] == [
        "@agent-a, please inspect rollout",
        "@agent-b, review the result",
    ]
    assert first_frame["payload"]["agent_id"] == "agent-a"
    assert first_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-a"],
        "config_profile_version": 1,
        "system_prompt": "You are agent-a.",
    }
    assert second_frame["payload"]["agent_id"] == "agent-b"
    assert second_frame["payload"]["metadata"] == {
        "conversation_type": "group",
        "mentioned_agent_ids": ["agent-b"],
        "config_profile_version": 1,
        "system_prompt": "You are agent-b.",
    }
    assert relay_adapter.sent == [
        OutboundMessage(
            channel_name="web_relay",
            text="reply:@agent-a, please inspect rollout",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": first_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-a",
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-a"],
                "config_profile_version": 1,
                "system_prompt": "You are agent-a.",
            },
        ),
        OutboundMessage(
            channel_name="web_relay",
            text="reply:@agent-b, review the result",
            target_chat_id=conversation_id,
            thread_id=None,
            metadata={
                "relay_task_id": second_frame["payload"]["relay_task_id"],
                "idempotency_key": "idem-group-b",
                "conversation_type": "group",
                "mentioned_agent_ids": ["agent-b"],
                "config_profile_version": 1,
                "system_prompt": "You are agent-b.",
            },
        ),
    ]
