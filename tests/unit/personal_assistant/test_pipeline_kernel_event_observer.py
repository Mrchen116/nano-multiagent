"""Unit test for InboundPipeline kernel_event_observer seam (feat-340-M2 R4).

The pipeline doesn't translate kernel events itself — that's IM.application.event_bridge's
job — but it owns the seam where kernel SSE events flow past. M2 adds an observer hook so
bootstrap can wire the bridge in without coupling pipeline to IM.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound: Any) -> None:
        del on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        return None


class _FakeSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


class _StreamingKernel:
    """Kernel SDK double emitting a scripted run event stream (refactor-387 M3+)."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._session_counter = 0
        self.run_id: str = "run-1"
        self._run_counter = 0

    async def create_session(self, **_kwargs: Any) -> _FakeSession:
        self._session_counter += 1
        return _FakeSession(session_id=f"sess-{self._session_counter}")

    def get_session(self, session_id: str, *, workspace_root: Any = None, **_kwargs) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "status": "active",
            "metadata": {"workspace_root": "/tmp"},
        }

    def submit(self, *, session_id: str, parts: Any = None, **_kwargs: Any) -> Any:
        self._run_counter += 1
        from unittest.mock import MagicMock
        record = MagicMock()
        record.run_id = self.run_id
        return record

    def stream(self, session_id: str, *, after_sequence: int = 0) -> Any:
        events = list(self._events)

        async def _gen():
            for ev in events:
                yield dict(ev)

        return _gen()

    def interrupt(self, session_id: str) -> None:
        del session_id


def test_kernel_event_observer_receives_each_run_event_in_order(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(agent_id="a", workspace_root=agent_dir, title="A"),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))

    kernel = _StreamingKernel(
        events=[
            {"run_id": "run-1", "event": "message_update", "delta_text": "hi "},
            {"run_id": "run-1", "event": "tool_start", "tool_call_id": "tc1", "tool_name": "t"},
            {"run_id": "run-1", "event": "tool_end", "tool_call_id": "tc1", "tool_name": "t", "status": "completed"},
            {"run_id": "run-1", "event": "message_update", "delta_text": "world"},
            {"run_id": "run-1", "event": "assistant_message", "content": "hi world"},
            {
                "run_id": "run-1",
                "event": "run_status",
                "status": "completed",
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        ]
    )

    observed: list[Mapping[str, Any]] = []

    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        kernel_event_observer=lambda event: observed.append(dict(event)),
    )

    message = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    asyncio.run(pipeline.handle_inbound(message))

    observed_names = [e.get("event") for e in observed]
    # Every run event reaches the observer in stream order, including the terminal run_status.
    assert observed_names == [
        "message_update",
        "tool_start",
        "tool_end",
        "message_update",
        "assistant_message",
        "run_status",
    ]
