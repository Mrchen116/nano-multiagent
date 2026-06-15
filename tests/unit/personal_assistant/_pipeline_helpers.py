"""Shared test doubles for inbound pipeline tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

from personal_assistant.channels.base import OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig


def _make_stream_event(data: dict[str, Any], *, seq: int = 1) -> dict[str, Any]:
    """Build a flattened event dict matching the real Kernel.stream() contract.

    Kernel.stream() now yields flattened dicts (sdk-fix-r3).  Test doubles
    must produce the same shape so pipeline consumption works without patching.
    """
    flat = dict(data)
    flat.setdefault("sequence_num", seq)
    return flat


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
            {
                "workspace_root": workspace_root,
                "product_id": product_id,
                "title": title,
                "metadata": metadata,
            }
        )
        self._session_metadata_by_id[session_id] = {
            **dict(metadata or {}),
            "workspace_root": workspace_root,
        }
        self.session_events.setdefault(session_id, [])
        return {"session_id": session_id}

    def get_session(self, *, session_id: str, **_kwargs):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": "now",
            "metadata": dict(metadata),
        }

    def seed_session(
        self, *, session_id: str, metadata: dict[str, object] | None = None
    ) -> None:
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls=None,
        priority="next",
        **_kwargs,
    ):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        text = texts[-1] if texts else ""
        call: dict = {"session_id": session_id, "texts": texts, "run_id": run_id}
        if image_urls is not None:
            call["image_urls"] = image_urls
        self.send_calls.append(call)
        self.run_states.setdefault(
            run_id,
            {"run_id": run_id, "status": "completed", "output_text": f"reply:{text}"},
        )
        self.session_events.setdefault(session_id, [])
        self._last_run_id_by_session[session_id] = run_id
        return {
            "run_id": run_id,
            "anchor_sequence": 1,
            "injected": False,
            "status": "queued",
        }

    async def stream_session(
        self, *, session_id: str, last_event_id=None, workspace_root=None, **_kwargs
    ):
        del last_event_id
        del workspace_root
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
                yield {
                    "event": "assistant_message",
                    "run_id": run_id,
                    "content": output_text,
                }
            status = state.get("status", "completed")
            run_status: dict[str, object] = {
                "event": "run_status",
                "run_id": run_id,
                "status": status,
            }
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
    """Kernel client double that exposes submit_message + stream_session (feat-338 SSE path).

    Legacy test double kept for backward compatibility. New tests should use _FakeSseKernel.
    """

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
            {
                "workspace_root": workspace_root,
                "product_id": product_id,
                "title": title,
                "metadata": metadata,
            }
        )
        self._session_metadata_by_id[session_id] = {
            **dict(metadata or {}),
            "workspace_root": workspace_root,
        }
        return {"session_id": session_id}

    def get_session(self, *, session_id: str, **_kwargs):
        metadata = self._session_metadata_by_id.get(session_id)
        if metadata is None:
            raise RuntimeError(f"missing session: {session_id}")
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": "now",
            "metadata": dict(metadata),
        }

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, object]] | None = None,
        priority: str = "next",
        **_kwargs,
    ):
        run_id = f"run-{len(self.submit_calls) + 1}"
        call: dict[str, object] = {
            "session_id": session_id,
            "texts": texts,
            "run_id": run_id,
            "priority": priority,
        }
        if image_urls is not None:
            call["image_urls"] = image_urls
        self.submit_calls.append(call)
        self.run_states[run_id] = {"run_id": run_id, "status": "completed"}
        return {
            "run_id": run_id,
            "anchor_sequence": 1,
            "injected": False,
            "status": "queued",
        }

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
        workspace_root: str
        | None = None,  # Refs #64: accepted to match updated kernel client API
        **_kwargs: object,
    ):
        del session_id
        del last_event_id
        del workspace_root
        for event in self._events:
            yield dict(event)

    def interrupt_session(self, *, session_id: str, **_kwargs):
        del session_id
        return {"status": "interrupted"}

    def append_message(self, *, session_id: str, role: str, content: str, **_kwargs):
        del session_id, role, content
        return {"status": "appended"}


@dataclass
class _FakeSession:
    """Minimal session stub returned by _FakeKernel.create_session."""

    session_id: str
    workspace_root: str | None = None


class _FakeKernel:
    """Kernel SDK double for inbound pipeline tests (refactor-387 M3+).

    Exposes the same observable attributes as _FakeKernelClient so existing
    test assertions (create_session_calls, send_calls, etc.) continue to work
    after tests migrate from kernel_client= to kernel=.

    The public interface mirrors agent.sdk.Kernel:
      - create_session (async)
      - submit (sync)
      - stream (returns AsyncIterator)
      - interrupt (sync)
      - get_session (sync)
    """

    def __init__(self) -> None:
        # Observable attributes kept compatible with _FakeKernelClient
        self.create_session_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.run_states: dict[str, list[dict[str, str]] | dict[str, str]] = {}
        self.session_events: dict[str, list[list[dict[str, Any]]]] = {}
        self._session_metadata_by_id: dict[str, dict[str, Any]] = {}
        self._session_index = 0
        self._run_index = 0
        self._last_run_id_by_session: dict[str, str] = {}
        self._sessions: dict[str, _FakeSession] = {}
        self.interrupted_sessions: list[str] = []
        # interrupt_calls mirrors interrupted_sessions for backwards compat with old test assertions.
        self.interrupt_calls: list[dict[str, str]] = []
        # submit_calls is an alias for send_calls, kept for backwards compat.
        # Both point to the same list — updating one updates the other.
        self.submit_calls: list[dict[str, Any]] = self.send_calls
        # Settable to override the default "reply:{text}" output for all runs.
        self.default_output_text: str | None = None

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
        # Store in the format matching old _FakeKernelClient.create_session_calls
        self.create_session_calls.append(
            {
                "workspace_root": ws_str,
                "product_id": "personal_assistant",
                "title": title,
                "metadata": metadata,
            }
        )
        # workspace_root is stored separately from metadata to mirror the real
        # Kernel.get_session contract: workspace_root is a top-level key, not
        # injected into metadata (refactor-387 regression fix).
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])
        session = _FakeSession(session_id=session_id, workspace_root=ws_str)
        self._sessions[session_id] = session
        return session

    def seed_session(
        self, *, session_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Pre-populate a session for session-reuse tests."""
        self._session_metadata_by_id[session_id] = dict(metadata or {})
        self.session_events.setdefault(session_id, [])
        ws = (metadata or {}).get("workspace_root")
        self._sessions.setdefault(
            session_id,
            _FakeSession(session_id=session_id, workspace_root=ws),
        )

    def get_session(
        self, session_id: str, *, workspace_root: str | None = None
    ) -> dict[str, Any]:
        """Return session payload mirroring real Kernel.get_session: workspace_root at top level."""
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"missing session: {session_id}")
        metadata = self._session_metadata_by_id.get(session_id, {})
        return {
            "session_id": session_id,
            "status": "active",
            # Top-level workspace_root — matches Kernel.get_session contract.
            "workspace_root": session.workspace_root or "",
            "metadata": dict(metadata),
        }

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: Any = None,
        workspace_root: Path | None = None,
        trace_id: str | None = None,
    ) -> MagicMock:
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        # Extract texts from parts for backwards-compatible send_calls
        texts = [p["text"] for p in parts if p.get("type") == "text"]
        image_urls = [
            {"url": p["image_url"]} for p in parts if p.get("type") == "image"
        ]
        call: dict[str, Any] = {
            "session_id": session_id,
            "texts": texts,
            "run_id": run_id,
        }
        if image_urls:
            call["image_urls"] = image_urls
        self.send_calls.append(call)
        last_text = texts[-1] if texts else ""
        output = (
            self.default_output_text
            if self.default_output_text is not None
            else f"reply:{last_text}"
        )
        self.run_states.setdefault(
            run_id, {"run_id": run_id, "status": "completed", "output_text": output}
        )
        self.session_events.setdefault(session_id, [])
        self._last_run_id_by_session[session_id] = run_id
        record = MagicMock()
        record.run_id = run_id
        return record

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield flattened event dicts — matching the real Kernel.stream() contract."""
        batches = self.session_events.get(session_id, [])
        run_id = self._last_run_id_by_session.get(session_id)
        run_states = self.run_states
        _batches_copy = list(batches)
        _seq = [1]  # mutable counter for sequence numbers

        def _next_seq() -> int:
            n = _seq[0]
            _seq[0] += 1
            return n

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for batch in _batches_copy:
                for event in batch:
                    yield _make_stream_event(dict(event), seq=_next_seq())
            if run_id is not None:
                raw_state = run_states.get(run_id, {})
                if isinstance(raw_state, list):
                    state = raw_state[-1] if raw_state else {}
                else:
                    state = raw_state
                output_text = state.get("output_text", "")
                if output_text:
                    yield _make_stream_event(
                        {
                            "event": "assistant_message",
                            "run_id": run_id,
                            "content": output_text,
                        },
                        seq=_next_seq(),
                    )
                status = state.get("status", "completed")
                run_status: dict[str, Any] = {
                    "event": "run_status",
                    "run_id": run_id,
                    "status": status,
                }
                usage = state.get("usage")
                if usage is not None:
                    run_status["usage"] = usage
                yield _make_stream_event(run_status, seq=_next_seq())

        return _gen()

    def interrupt(self, session_id: str) -> str | None:
        self.interrupted_sessions.append(session_id)
        self.interrupt_calls.append({"session_id": session_id})
        return None

    def close(self) -> None:
        pass


class _FakeSseKernel(_FakeKernel):
    """Kernel SDK double for SSE stream tests — pre-seeds a fixed events sequence.

    Equivalent to _FakeSseKernelClient but uses the Kernel SDK interface.
    The given events are returned by stream() for any session.
    """

    def __init__(self, *, events: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._preset_events: list[dict[str, Any]] = list(events or [])

    def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield flattened event dicts — matching the real Kernel.stream() contract."""
        preset = list(self._preset_events)

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for seq, event in enumerate(preset, start=1):
                yield _make_stream_event(dict(event), seq=seq)

        return _gen()


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    agent_a.mkdir()
    agent_b.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=agent_a, title="Agent A"
        ),
        AgentWorkspaceConfig(
            agent_id="agent-b", workspace_root=agent_b, title="Agent B"
        ),
    )
