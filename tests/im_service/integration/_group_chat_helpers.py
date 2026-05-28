"""Shared helpers for group chat integration tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.repositories import AgentProfileRepository, NodeRepository
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig


class _FakeKernelClient:
    """Record gateway calls and synthesize agent-tagged replies."""

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self.session_events: dict[str, list[list[dict[str, object]]]] = {}
        self.default_output_text = "reply:{text}"
        self._session_index = 0
        self._run_index = 0
        self._stream_calls: dict[str, int] = {}

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

    def submit_message(self, *, session_id: str, texts: list[str], image_urls=None, **_kwargs):
        # Renamed from send_message_async to match KernelApiClient.submit_message in src/
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        rendered_text = "\n".join(texts)
        self.send_calls.append({"session_id": session_id, "text": rendered_text, "run_id": run_id})
        output_text = self.default_output_text.format(text=rendered_text)
        self.run_states[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "output_text": output_text,
        }
        # Pre-seed SSE events: pipeline consumes SSE stream instead of polling get_run.
        sse_events: list[dict] = [
            {"event": "assistant_message", "run_id": run_id, "content": output_text},
            {"event": "run_status", "run_id": run_id, "status": "completed", "output_text": output_text},
        ]
        self.session_events.setdefault(session_id, []).append(sse_events)
        return {"run_id": run_id}

    async def stream_session(self, *, session_id: str, last_event_id: int | None = None):
        # Async generator matching KernelApiClient.stream_session.
        batches = self.session_events.get(session_id, [])
        index = self._stream_calls.get(session_id, 0)
        self._stream_calls[session_id] = index + 1
        if index < len(batches):
            for event in batches[index]:
                yield event

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def seed_user(client: TestClient, username: str) -> str:
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


def send_delivery_receipt(
    websocket,
    *,
    relay_payload: dict[str, object],
    delivery_status: str,
    detail: str | None,
) -> dict[str, object]:
    """Send a delivery receipt and wait for the ack frame."""
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
        # Group completion enqueues a relay per peer agent (bugfix-358: dumb fanout,
        # no background_context_only flag; Gateway decides trigger vs buffer from
        # mentioned_agent_ids). This helper just consumes such frames while waiting
        # for the receipt ack corresponding to the relay under test.
        assert frame.get("type") == "relay.message"
        continue


def seed_node_and_profiles(app, *, owner_id: str = "", agent_ids: tuple[str, ...]) -> None:
    """Register node-1 and upsert profiles for the given agent_ids."""
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


def make_agent_configs(tmp_path: Path, *agent_ids: str) -> tuple[AgentWorkspaceConfig, ...]:
    """Create workspace directories and AgentWorkspaceConfig for each agent_id."""
    agents: list[AgentWorkspaceConfig] = []
    for agent_id in agent_ids:
        workspace_root = tmp_path / agent_id
        workspace_root.mkdir()
        agents.append(
            AgentWorkspaceConfig(agent_id=agent_id, workspace_root=workspace_root, title=agent_id.title())
        )
    return tuple(agents)
