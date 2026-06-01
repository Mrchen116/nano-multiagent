"""R3 tests: PA inbound_pipeline permission_request SSE→IM forwarding + permission_response routing.

C1 (Red) — these tests should fail until R3 implementation is complete:

1. kernel_event_observer forwards permission_request SSE as node.streaming_delta kind=permission_request
2. IMConnectionManager handles node.streaming_delta with kind=permission_response and calls callback
3. KernelApiClient.submit_message accepts and sends origin= parameter
4. Heartbeat scheduler passes origin=heartbeat when submitting runs
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: kernel_event_observer forwards permission_request → node.streaming_delta
# ---------------------------------------------------------------------------

class _FakeManager:
    """Minimal IMConnectionManager double for observer tests."""

    def __init__(self) -> None:
        self.connected = True
        self.sent: list[tuple[str, dict]] = []
        self._sent_tasks: list = []

    async def send_json(self, message_type: str, payload: Mapping[str, Any]) -> None:
        self.sent.append((message_type, dict(payload)))

    async def send_json_await_ack(self, message_type: str, payload: Mapping[str, Any]) -> dict:
        self.sent.append((message_type, dict(payload)))
        return {"payload": {"message_id": "msg-from-ack"}}


def _make_observer_with_run_ctx(run_id: str, conversation_id: str, message_id: str, agent_id: str):
    """Build a kernel_event_observer with a pre-seeded run context."""
    from personal_assistant.main import _build_kernel_event_observer

    manager = _FakeManager()
    run_context_store: dict[str, dict[str, str]] = {
        run_id: {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "agent_id": agent_id,
        }
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
    )
    return observer, manager, run_context_store


class TestKernelObserverPermissionRequest:
    """Observer forwards permission_request SSE → node.streaming_delta kind=permission_request."""

    @pytest.mark.asyncio
    async def test_permission_request_forwarded_to_im(self) -> None:
        observer, manager, _ = _make_observer_with_run_ctx(
            run_id="run-1",
            conversation_id="conv-1",
            message_id="msg-1",
            agent_id="agent-alpha",
        )

        event = {
            "run_id": "run-1",
            "event": "permission_request",
            "request_id": "req-abc",
            "tool_name": "bash",
            "tool_input": {"command": "rm -rf /tmp/old"},
            "question": "Allow bash?",
            "options": [
                {"id": "allow_once", "label": "Allow once", "description": "Allow this single action"},
                {"id": "deny", "label": "Deny", "description": "Block this action"},
            ],
        }
        result = observer(event)
        if asyncio.iscoroutine(result):
            await result
        # Drain pending tasks (fire-and-forget tasks from loop.create_task)
        await asyncio.sleep(0)

        # Check that the manager received the permission_request streaming delta
        sent_types = [msg_type for msg_type, _ in manager.sent]
        assert "node.streaming_delta" in sent_types, f"expected node.streaming_delta, got {sent_types}"

        delta_payloads = [p for t, p in manager.sent if t == "node.streaming_delta"]
        perm_req_payloads = [p for p in delta_payloads if p.get("kind") == "permission_request"]
        assert len(perm_req_payloads) >= 1, f"no permission_request kind found in: {delta_payloads}"

        payload = perm_req_payloads[0]
        assert payload["message_id"] == "msg-1"
        assert "permission_request" in payload
        perm_data = payload["permission_request"]
        assert perm_data["request_id"] == "req-abc"
        assert perm_data["tool_name"] == "bash"

    @pytest.mark.asyncio
    async def test_permission_request_without_message_id_skipped(self) -> None:
        """If no message_id in run_ctx yet, permission_request should not error and not send."""
        from personal_assistant.main import _build_kernel_event_observer

        manager = _FakeManager()
        run_context_store: dict[str, dict[str, str]] = {
            "run-1": {
                "conversation_id": "conv-1",
                "message_id": "",  # not yet assigned
                "agent_id": "agent-alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        event = {
            "run_id": "run-1",
            "event": "permission_request",
            "request_id": "req-no-msg",
            "tool_name": "bash",
            "tool_input": {},
            "question": "Allow?",
            "options": [],
        }
        result = observer(event)
        if asyncio.iscoroutine(result):
            await result
        await asyncio.sleep(0)
        # No node.streaming_delta should have been sent
        delta_payloads = [p for t, p in manager.sent if t == "node.streaming_delta" and p.get("kind") == "permission_request"]
        assert len(delta_payloads) == 0

    @pytest.mark.asyncio
    async def test_permission_resolved_forwarded_to_im(self) -> None:
        """permission_resolved SSE → node.streaming_delta kind=permission_resolved."""
        observer, manager, _ = _make_observer_with_run_ctx(
            run_id="run-2",
            conversation_id="conv-1",
            message_id="msg-2",
            agent_id="agent-beta",
        )

        event = {
            "run_id": "run-2",
            "event": "permission_resolved",
            "request_id": "req-xyz",
            "decision": "allow_once",
        }
        result = observer(event)
        if asyncio.iscoroutine(result):
            await result
        await asyncio.sleep(0)

        delta_payloads = [p for t, p in manager.sent if t == "node.streaming_delta"]
        resolved_payloads = [p for p in delta_payloads if p.get("kind") == "permission_resolved"]
        assert len(resolved_payloads) >= 1, f"no permission_resolved kind found in: {delta_payloads}"

        payload = resolved_payloads[0]
        assert payload["message_id"] == "msg-2"
        assert payload["request_id"] == "req-xyz"
        assert payload["decision"] == "allow_once"


# ---------------------------------------------------------------------------
# Test 2: IMConnectionManager handles permission_response from IM
# ---------------------------------------------------------------------------

class _FakeWebSocket:
    """Minimal websocket double for im_connection tests."""

    def __init__(self, messages: list[dict]) -> None:
        self._queue = list(messages)
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self._queue:
            raise StopAsyncIteration("no more messages")
        return json.dumps(self._queue.pop(0))

    async def close(self) -> None:
        pass


class TestIMConnectionPermissionResponse:
    """IMConnectionManager handles node.streaming_delta kind=permission_response."""

    @pytest.mark.asyncio
    async def test_permission_response_calls_callback(self) -> None:
        """When IM pushes node.streaming_delta kind=permission_response, PA callback is called."""
        from personal_assistant.ws.im_connection import IMConnectionManager, IMConnectionConfig
        from personal_assistant.reporter.upstream_reporter import UpstreamReporter
        from personal_assistant.channels.web_relay_adapter import WebRelayAdapter

        received: list[dict] = []

        def permission_response_handler(payload: Mapping[str, Any]) -> None:
            received.append(dict(payload))

        # Build a minimal IMConnectionManager with a permission_response_handler
        # This test will FAIL until the handler parameter is added
        config = IMConnectionConfig(url="ws://localhost:8011")
        reporter = MagicMock(spec=UpstreamReporter)
        reporter.node_id = "node-1"
        relay_adapter = MagicMock(spec=WebRelayAdapter)

        # The manager needs a permission_response_handler parameter
        manager = IMConnectionManager(
            config=config,
            reporter=reporter,
            relay_adapter=relay_adapter,
            permission_response_handler=permission_response_handler,
            connect=AsyncMock(),
        )

        frame = {
            "type": "node.streaming_delta",
            "payload": {
                "kind": "permission_response",
                "request_id": "req-1",
                "decision": "allow_once",
                "message_id": "msg-1",
            },
        }
        ws = _FakeWebSocket([frame])
        manager._websocket = ws
        manager._connected = True

        await manager._listen_once()

        assert len(received) == 1
        assert received[0]["request_id"] == "req-1"
        assert received[0]["decision"] == "allow_once"


# Test 3 (TestKernelApiClientOrigin) deleted in refactor-387 M3:
# KernelApiClient was removed. The origin field is now passed via kernel.submit()
# RunOrigin enum in _KernelClientShim.submit_message.


# ---------------------------------------------------------------------------
# Test 4: Heartbeat scheduler passes origin=heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeatOrigin:
    """Heartbeat scheduler passes origin='heartbeat' when submitting runs."""

    @pytest.mark.asyncio
    async def test_heartbeat_submit_passes_origin(self, tmp_path: Path) -> None:
        """HeartbeatScheduler._submit_run passes origin='heartbeat' to kernel."""
        from datetime import datetime, timezone

        from personal_assistant.scheduler.heartbeat_scheduler import (
            HeartbeatScheduler,
            HeartbeatSchedulerStateStore,
        )
        from personal_assistant.config.local_store import AgentWorkspaceConfig

        submit_calls: list[dict] = []

        class _FakeKernel:
            async def create_session(self, *, workspace_root, product_id, title=None, metadata=None):
                return {"session_id": "sess-1"}

            def get_session(self, *, session_id):
                return {"session_id": session_id, "status": "active", "metadata": {"workspace_root": str(tmp_path)}}

            def submit_message(self, *, session_id, texts, **kwargs):
                submit_calls.append({"session_id": session_id, "texts": texts, **kwargs})
                return {"run_id": "run-hb-1", "anchor_sequence": 1}

        agent = AgentWorkspaceConfig(agent_id="alpha", workspace_root=tmp_path, title="Alpha")
        state_store = HeartbeatSchedulerStateStore(state_path=tmp_path / "hb_state.json")
        scheduler = HeartbeatScheduler(
            kernel_client=_FakeKernel(),
            agents=(agent,),
            state_store=state_store,
        )

        # Create a HEARTBEAT.md so the scheduler has something to evaluate.
        # Use a past @at datetime so the run is immediately due.
        heartbeat_file = tmp_path / "HEARTBEAT.md"
        heartbeat_file.write_text("# HEARTBEAT\n\nat: 2020-01-01T00:00:00+00:00\n\nCheck the workspace.\n")

        await scheduler.tick()

        assert len(submit_calls) == 1
        # origin should be "heartbeat"
        assert submit_calls[0].get("origin") == "heartbeat", (
            f"expected origin='heartbeat', got: {submit_calls[0]}"
        )
