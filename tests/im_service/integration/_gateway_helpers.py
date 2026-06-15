"""Shared helpers for IM ↔ Gateway integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from IM.infra.repositories import AgentProfileRepository, NodeRepository
from personal_assistant.config.local_store import AgentWorkspaceConfig


def _make_stream_event(data: dict[str, Any], *, seq: int = 1) -> dict[str, Any]:
    """Build a flattened event dict matching the real Kernel.stream() contract.

    Kernel.stream() now yields flattened dicts (sdk-fix-r3).
    """
    flat = dict(data)
    flat.setdefault("sequence_num", seq)
    return flat


@dataclass
class _FakeSession:
    """Minimal session stub returned by _FakeKernel.create_session."""

    session_id: str


class _FakeKernel:
    """Record gateway->kernel calls and synthesize deterministic replies.

    Implements the Kernel SDK interface (refactor-387 M3+):
      - create_session (async) → _FakeSession
      - submit (sync) → RunRecord mock
      - stream (returns AsyncIterator)
      - get_session (sync)

    NO_REPLY output is triggered when session metadata matches the suppression
    system_prompt + profile_version combination, mirroring kernel behavior.

    Observable attributes kept compatible with old _FakeKernelClient so test
    assertions on create_session_calls / send_calls continue to work:
      - create_session_calls: [{workspace_root, product_id, title, metadata}]
      - send_calls: [{session_id, text, run_id}]  (text = joined parts texts)
    """

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str] | list[dict[str, str]]] = {}
        self.session_events: dict[str, list[list[dict[str, object]]]] = {}
        self._session_metadata_by_id: dict[str, dict[str, Any]] = {}
        self._session_index = 0
        self._run_index = 0
        self._get_run_calls: dict[str, int] = {}
        self._stream_calls: dict[str, int] = {}

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: Path | None = None,
        skills: list[str] | None = None,
        tool_allowlist: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> _FakeSession:
        self._session_index += 1
        session_id = f"sess-{self._session_index}"
        ws_str = str(workspace_root) if workspace_root else ""
        # Store in backwards-compatible format matching old create_session_calls assertions.
        self.create_session_calls.append(
            {
                "workspace_root": ws_str,
                "product_id": "personal_assistant",
                "title": title,
                "metadata": metadata,
            }
        )
        self._session_metadata_by_id[session_id] = {
            **(metadata or {}),
            "workspace_root": ws_str,
        }
        self.session_events.setdefault(session_id, [])
        return _FakeSession(session_id=session_id)

    def get_session(
        self, session_id: str, *, workspace_root: Any = None, **_kwargs
    ) -> dict[str, Any]:
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        # workspace_root is exposed as a top-level key to match Kernel.get_session
        # contract (df319bee fix) — _binding_matches_workspace_root reads the top-level
        # key directly; without it the session-reuse path silently bypasses the check.
        ws = metadata.get("workspace_root", "")
        return {
            "session_id": session_id,
            "status": "active",
            "workspace_root": ws,
            "created_at": "now",
            "metadata": dict(metadata),
        }

    def seed_session(
        self, *, session_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Pre-populate a session for session-reuse tests."""
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: Any = None,
        workspace_root: Path | None = None,
        trace_id: str | None = None,
    ) -> Any:
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        # Extract texts from parts and join as legacy send_calls["text"].
        texts = [p["text"] for p in parts if p.get("type") == "text"]
        rendered_text = "\n".join(texts)
        self.send_calls.append(
            {"session_id": session_id, "text": rendered_text, "run_id": run_id}
        )
        session_metadata = self._session_metadata_by_id.get(session_id, {})
        output_text = f"gateway-reply:{rendered_text}"
        # Determine NO_REPLY based on session system_prompt + profile_version, not message text.
        # This mirrors kernel behavior: prompt instructs the model to say NO_REPLY.
        system_prompt = session_metadata.get("system_prompt", "")
        profile_version = session_metadata.get("config_profile_version")
        if (
            system_prompt
            == "When mentioned in a group chat, reply exactly with NO_REPLY."
            and profile_version == 2
        ):
            output_text = "NO_REPLY"
        elif (
            system_prompt
            == "When mentioned in a group chat, reply exactly with NO_REPLY."
        ):
            output_text = "ALPHA_ACK_M170"
        self.run_states[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "output_text": output_text,
        }
        # Pre-seed stream events: pipeline consumes stream instead of polling get_run.
        sse_events: list[dict] = [
            {"event": "assistant_message", "run_id": run_id, "content": output_text},
            {
                "event": "run_status",
                "run_id": run_id,
                "status": "completed",
                "output_text": output_text,
            },
        ]
        self.session_events.setdefault(session_id, []).append(sse_events)
        record = MagicMock()
        record.run_id = run_id
        return record

    def stream(self, session_id: str, *, after_sequence: int = 0):
        """Yield flattened event dicts — matching the real Kernel.stream() contract."""
        # Each submit call appends one batch; advance per-session index across calls.
        batches = self.session_events.get(session_id, [])
        index = self._stream_calls.get(session_id, 0)
        self._stream_calls[session_id] = index + 1
        _batch = batches[index] if index < len(batches) else []

        async def _gen():
            for seq, event in enumerate(_batch, start=1):
                yield _make_stream_event(dict(event), seq=seq)

        return _gen()

    def interrupt(self, session_id: str) -> None:
        pass

    def close(self) -> None:
        pass


# Legacy alias kept for any remaining import-by-name usages in tests.
_FakeKernelClient = _FakeKernel


def seed_user(
    client: TestClient, username: str, display_name: str | None = None
) -> str:
    """Auth-aware seeding: first call registers + authorizes; subsequent calls seed under tenant."""
    from tests.im_service._auth_helpers import (
        authorize,
        register_user,
        seed_user_under_owner,
    )

    if client.headers.get("Authorization") is None:
        user = register_user(client, username=username, display_name=display_name)
        authorize(client, user)
        return user.id
    me = client.get("/im/v1/me").json()
    return seed_user_under_owner(
        client, username=username, display_name=display_name, owner_id=me["owner_id"]
    )


def seed_node_and_profiles(
    app, *, owner_id: str = "", agent_ids: tuple[str, ...] = ("agent-a",)
) -> None:
    """Register node-1 and upsert agent profiles with default group_reply_policy=manual."""
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


def make_agent_configs(
    tmp_path: Path, *agent_ids: str
) -> tuple[AgentWorkspaceConfig, ...]:
    """Create workspace directories and AgentWorkspaceConfig for each agent_id."""
    agents: list[AgentWorkspaceConfig] = []
    for agent_id in agent_ids:
        workspace_root = tmp_path / agent_id
        workspace_root.mkdir()
        agents.append(
            AgentWorkspaceConfig(
                agent_id=agent_id,
                workspace_root=workspace_root,
                title=agent_id.title(),
                system_prompt=f"You are {agent_id}.",
            )
        )
    return tuple(agents)


def send_delivery_receipt(
    websocket,
    *,
    relay_payload: dict[str, object],
    delivery_status: str,
    detail: str | None,
    extra_frames: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Send a delivery receipt and wait for the ack frame, collecting extra relay.message frames."""
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
    expected_status = "failed" if delivery_status == "failed" else delivery_status
    while True:
        frame = websocket.receive_json()
        if frame.get("type") == "relay.message":
            if extra_frames is not None:
                extra_frames.append(frame)
            continue
        assert frame == {
            "type": "ack",
            "payload": {
                "message_type": "node.delivery_receipt",
                "node_id": "node-1",
                "relay_task_id": relay_payload["relay_task_id"],
                "status": expected_status,
            },
        }
        return frame

    raise AssertionError("unreachable")


def receive_group_relays(websocket) -> dict[str, dict[str, object]]:
    """Return the two per-agent relay frames emitted for one group message."""
    relay_frames = [websocket.receive_json(), websocket.receive_json()]
    return {frame["payload"]["agent_id"]: frame for frame in relay_frames}
