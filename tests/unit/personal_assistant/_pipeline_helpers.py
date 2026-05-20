"""Shared test doubles for inbound pipeline tests."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.channels.base import OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started_with = None
        self.stopped = 0
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):
        self.started_with = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        self.stopped += 1


class _FakeKernelClient:
    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, object | None]] = []
        self.send_calls: list[dict[str, object]] = []
        self.run_states: dict[str, list[dict[str, str]] | dict[str, str]] = {}
        self.session_events: dict[str, list[list[dict[str, object]]]] = {}
        self._session_metadata_by_id: dict[str, dict[str, object]] = {}
        self._session_index = 0
        self._run_index = 0
        self._get_run_calls: dict[str, int] = {}
        self._stream_calls: dict[str, int] = {}
        self._last_run_id_by_session: dict[str, str] = {}

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
        self._session_metadata_by_id[session_id] = {**dict(metadata or {}), "workspace_root": workspace_root}
        self.session_events.setdefault(session_id, [])
        return {"session_id": session_id}

    def get_session(self, *, session_id: str):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {"session_id": session_id, "status": "active", "created_at": "now", "metadata": dict(metadata)}

    def seed_session(self, *, session_id: str, metadata: dict[str, object] | None = None) -> None:
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])

    def submit_message(self, *, session_id: str, texts: list[str], image_urls=None, priority="next"):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        text = texts[-1] if texts else ""
        call: dict = {"session_id": session_id, "texts": texts, "run_id": run_id}
        if image_urls is not None:
            call["image_urls"] = image_urls
        self.send_calls.append(call)
        self.run_states.setdefault(run_id, {"run_id": run_id, "status": "completed", "output_text": f"reply:{text}"})
        self.session_events.setdefault(session_id, [])
        self._last_run_id_by_session[session_id] = run_id
        return {"run_id": run_id, "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(self, *, session_id: str, last_event_id=None):
        del last_event_id
        batches = self.session_events.get(session_id, [])
        for batch in batches:
            for event in batch:
                yield dict(event)
        run_id = self._last_run_id_by_session.get(session_id)
        if run_id is not None:
            raw_state = self.run_states.get(run_id, {})
            if isinstance(raw_state, list):
                state = raw_state[-1] if raw_state else {}
            else:
                state = raw_state
            output_text = state.get("output_text", "")
            if output_text:
                yield {"event": "assistant_message", "run_id": run_id, "content": output_text}
            status = state.get("status", "completed")
            run_status: dict[str, object] = {"event": "run_status", "run_id": run_id, "status": status}
            usage = state.get("usage")
            if usage is not None:
                run_status["usage"] = usage
            yield run_status

    def get_run(self, *, run_id: str):
        payload = self.run_states[run_id]
        if isinstance(payload, list):
            index = self._get_run_calls.get(run_id, 0)
            self._get_run_calls[run_id] = index + 1
            if index >= len(payload):
                return payload[-1]
            return payload[index]
        return payload


class _FakeSseKernelClient:
    """Kernel client double that exposes submit_message + stream_session (feat-338 SSE path)."""

    def __init__(self, *, events: list[dict[str, object]] | None = None) -> None:
        self.create_session_calls: list[dict[str, object | None]] = []
        self.submit_calls: list[dict[str, object]] = []
        self._events: list[dict[str, object]] = list(events or [])
        self._session_index = 0
        self._session_metadata_by_id: dict[str, dict[str, object]] = {}
        self.run_states: dict[str, dict[str, object]] = {}

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
        self._session_metadata_by_id[session_id] = {**dict(metadata or {}), "workspace_root": workspace_root}
        return {"session_id": session_id}

    def get_session(self, *, session_id: str):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {"session_id": session_id, "status": "active", "created_at": "now", "metadata": dict(metadata)}

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, object]] | None = None,
        priority: str = "next",
    ):
        run_id = f"run-{len(self.submit_calls) + 1}"
        call: dict[str, object] = {"session_id": session_id, "texts": texts, "run_id": run_id, "priority": priority}
        if image_urls is not None:
            call["image_urls"] = image_urls
        self.submit_calls.append(call)
        self.run_states[run_id] = {"run_id": run_id, "status": "completed"}
        return {"run_id": run_id, "anchor_sequence": 1, "injected": False, "status": "queued"}

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
    ):
        del session_id
        del last_event_id
        for event in self._events:
            yield dict(event)

    def interrupt_session(self, *, session_id: str):
        del session_id
        return {"status": "interrupted"}

    def append_message(self, *, session_id: str, role: str, content: str):
        del session_id, role, content
        return {"status": "appended"}


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    agent_a.mkdir()
    agent_b.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agent_a, title="Agent A"),
        AgentWorkspaceConfig(agent_id="agent-b", workspace_root=agent_b, title="Agent B"),
    )
