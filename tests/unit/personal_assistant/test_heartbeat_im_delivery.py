"""Integration tests for feat-393: heartbeat run → IM direct conversation delivery.

Tests the end-to-end path from kernel_event_observer receiving heartbeat events
through a real FK-enforced IM DB, verifying that:
- heartbeat with real content creates a real message row (FK path satisfied)
- heartbeat with NO_REPLY / empty content creates zero message rows (silent)
- normal chat eager-bubble path is unchanged (regression guard)
- fresh-session per-tick is replaced by stable :heartbeat session reuse

FK constraint guard: uses initialize_schema (PRAGMA foreign_keys=ON) to ensure
any synthetic conversation/message ID would fail at the DB layer, preventing
M138-style fake-green tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from IM.application.event_bridge import EventBridge
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    EventRepository,
    MessageRepository,
    UserRepository,
)
from IM.ws.gateway_handler import GatewayHandler
from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.infra.repositories import UsageMetricsRepository


# ---------------------------------------------------------------------------
# Stubs / test doubles
# ---------------------------------------------------------------------------


class _FakeIMManager:
    """Fake IMConnectionManager that records sent frames and returns scripted acks.

    Crucially, send_json_await_ack routes turn_start frames through the real
    GatewayHandler to get a real IM message_id (not a synthetic one).
    """

    def __init__(self, gateway_handler: GatewayHandler) -> None:
        self._handler = gateway_handler
        self._sent_frames: list[tuple[str, dict]] = []
        self.connected = True

    @property
    def sent_frames(self) -> list[tuple[str, dict]]:
        return list(self._sent_frames)

    async def send_json(self, message_type: str, payload: Mapping[str, Any]) -> None:
        self._sent_frames.append((message_type, dict(payload)))
        # Route streaming_delta frames through real handler to persist to DB
        if message_type == "node.streaming_delta":
            await self._handler.handle_message(
                websocket=_NullWebSocket(),
                message_type=message_type,
                payload=dict(payload),
            )

    async def send_json_await_ack(
        self, message_type: str, payload: Mapping[str, Any]
    ) -> dict[str, object]:
        self._sent_frames.append((message_type, dict(payload)))
        if message_type == "node.streaming_delta":
            response = await self._handler.handle_message(
                websocket=_NullWebSocket(),
                message_type=message_type,
                payload=dict(payload),
            )
            if response is not None:
                return response
        return {}


class _NullWebSocket:
    """Minimal WebSocket stub that discards sent frames (no client connected)."""

    async def send_json(self, payload: dict) -> None:
        pass


# ---------------------------------------------------------------------------
# Helper: build GatewayHandler wired to FK-enforced DB
# ---------------------------------------------------------------------------


def _build_im_db_and_handler(tmp_path: Path):  # noqa: ANN202
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    msg_repo = MessageRepository(connection)
    evt_repo = EventRepository(connection)
    bridge = EventBridge(
        message_repository=msg_repo, event_repository=evt_repo, notify=None
    )
    convs = ConversationRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=convs,
        event_bridge=bridge,
    )
    return connection, handler


# ---------------------------------------------------------------------------
# R2 tests: heartbeat observer produces / suppresses IM messages
# ---------------------------------------------------------------------------


def test_heartbeat_with_content_creates_real_message_row_in_fk_enforced_db(
    tmp_path: Path,
) -> None:
    """Heartbeat run that produces real content → a real message row appears in IM DB.

    This is the M138 fake-green guard: FK is ON; any synthetic message_id would
    fail when the events table tries to reference messages.id.
    """
    from personal_assistant.main import _build_kernel_event_observer

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano", display_name="Nano")
    users.create_user(username="agent:alpha", display_name="Alpha")

    # Register the node so gateway_handler allows streaming_delta from it
    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["alpha"], "capabilities": {}},
        )
    )

    run_context_store: dict[str, dict[str, str]] = {}
    fake_manager = _FakeIMManager(handler)

    # Seed run_context_store with heartbeat variant: to_user_id instead of conversation_id.
    # This is what the heartbeat runner will do after feat-393 (R2 gateway side).
    run_id = "run-hb-content-1"
    run_context_store[run_id] = {
        "conversation_id": "",  # empty: not yet resolved (lazy)
        "message_id": "",  # empty: not yet created (lazy)
        "agent_id": "alpha",
        "to_user_id": owner.id,  # heartbeat variant: owner_id drives canonical conv lookup
        "kernel_session_id": "sess-hb-1",
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        # Simulate kernel events for a heartbeat run that has real content.
        # run_status=running fires first; for heartbeat, observer must NOT send turn_start here.
        coro = observer({"run_id": run_id, "event": "run_status", "status": "running"})
        if asyncio.iscoroutine(coro):
            await coro

        # assistant_message with real content → observer should lazily send turn_start{to_user_id}
        # then message_delta.
        coro = observer(
            {
                "run_id": run_id,
                "event": "assistant_message",
                "content": "Daily summary: all good.",
            }
        )
        if asyncio.iscoroutine(coro):
            await coro

        # turn_end completes the run.
        coro = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    # The IM DB must have a real message row (FK-enforced path passed).
    # Find the canonical direct conversation created by turn_start to_user_id handler.
    convs = ConversationRepository(connection)
    agent_user_row = (
        UserRepository(connection)
        ._connection.execute(  # noqa: SLF001
            "SELECT id FROM users WHERE username = ?", ("agent:alpha",)
        )
        .fetchone()
    )
    assert agent_user_row is not None
    agent_user_id = str(agent_user_row["id"])

    direct_convs = [
        c
        for c in convs.list_conversations()
        if c.type == "direct" and set(c.participant_ids) == {owner.id, agent_user_id}
    ]
    assert len(direct_convs) >= 1, (
        f"heartbeat with content must create canonical direct conversation; "
        f"sent_frames={fake_manager.sent_frames}"
    )
    canonical = sorted(direct_convs, key=lambda c: (c.created_at, c.id))[0]
    messages = MessageRepository(connection).list_messages(conversation_id=canonical.id)
    assert len(messages) >= 1, (
        "heartbeat with content must create a real message row in the FK-enforced IM DB; "
        f"got 0 messages — sent_frames={fake_manager.sent_frames}"
    )


def test_heartbeat_no_reply_produces_zero_message_rows(tmp_path: Path) -> None:
    """Heartbeat run that returns NO_REPLY → zero new message rows in IM DB (silent tick)."""
    from personal_assistant.main import _build_kernel_event_observer

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano2", display_name="Nano2")
    users.create_user(username="agent:beta", display_name="Beta")

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["beta"], "capabilities": {}},
        )
    )

    run_context_store: dict[str, dict[str, str]] = {}
    fake_manager = _FakeIMManager(handler)

    run_id = "run-hb-noreply-1"
    run_context_store[run_id] = {
        "conversation_id": "",
        "message_id": "",
        "agent_id": "beta",
        "to_user_id": owner.id,
        "kernel_session_id": "sess-hb-2",
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        coro = observer({"run_id": run_id, "event": "run_status", "status": "running"})
        if asyncio.iscoroutine(coro):
            await coro
        # NO_REPLY content → observer must not send turn_start; silent
        coro = observer(
            {"run_id": run_id, "event": "assistant_message", "content": "NO_REPLY"}
        )
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    # Verify zero conversations and zero messages created
    all_convs = ConversationRepository(connection).list_conversations()
    assert len(all_convs) == 0, (
        f"NO_REPLY heartbeat must create zero conversations; got {len(all_convs)}: "
        f"sent_frames={fake_manager.sent_frames}"
    )


def test_heartbeat_empty_content_produces_zero_message_rows(tmp_path: Path) -> None:
    """Heartbeat run with empty assistant content → zero message rows (silent tick)."""
    from personal_assistant.main import _build_kernel_event_observer

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano3", display_name="Nano3")
    users.create_user(username="agent:gamma", display_name="Gamma")

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["gamma"], "capabilities": {}},
        )
    )

    run_context_store: dict[str, dict[str, str]] = {}
    fake_manager = _FakeIMManager(handler)

    run_id = "run-hb-empty-1"
    run_context_store[run_id] = {
        "conversation_id": "",
        "message_id": "",
        "agent_id": "gamma",
        "to_user_id": owner.id,
        "kernel_session_id": "sess-hb-3",
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        coro = observer({"run_id": run_id, "event": "run_status", "status": "running"})
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer(
            {"run_id": run_id, "event": "assistant_message", "content": "   "}
        )
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    all_convs = ConversationRepository(connection).list_conversations()
    assert len(all_convs) == 0, (
        f"empty heartbeat must create zero conversations/messages; got {len(all_convs)}: "
        f"sent_frames={fake_manager.sent_frames}"
    )


def test_normal_chat_run_context_store_eager_bubble_unchanged(tmp_path: Path) -> None:
    """Normal chat run_context_store (with conversation_id) keeps eager turn_start (regression guard).

    Heartbeat lazy path must not change the behavior of normal chat runs, which
    seed run_context_store with conversation_id and expect eager bubble creation.
    """
    from personal_assistant.main import _build_kernel_event_observer

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="chat-user", display_name="Chat User")
    agent_user = users.create_user(username="agent:delta", display_name="Delta")
    convs = ConversationRepository(connection)
    conv = convs.create_conversation(
        title="chat", participant_ids=[owner.id, agent_user.id]
    )

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["delta"], "capabilities": {}},
        )
    )

    run_context_store: dict[str, dict[str, str]] = {}
    fake_manager = _FakeIMManager(handler)

    run_id = "run-chat-normal-1"
    # Normal chat seeds conversation_id (not to_user_id)
    run_context_store[run_id] = {
        "conversation_id": conv.id,
        "message_id": "",
        "agent_id": "delta",
        "kernel_session_id": "sess-chat-1",
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        # Eager turn_start should fire immediately on run_status=running
        coro = observer({"run_id": run_id, "event": "run_status", "status": "running"})
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer(
            {"run_id": run_id, "event": "assistant_message", "content": "hello"}
        )
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    # Eager bubble must exist immediately after run_status=running
    messages = MessageRepository(connection).list_messages(conversation_id=conv.id)
    assert len(messages) == 1, (
        f"normal chat eager bubble must persist message immediately; got {len(messages)}"
    )


# ---------------------------------------------------------------------------
# R2 tests: HeartbeatScheduler uses stable :heartbeat session (not fresh-session per tick)
# ---------------------------------------------------------------------------


def test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks(
    tmp_path: Path,
) -> None:
    """HeartbeatScheduler uses a stable per-agent ':heartbeat' session, not a fresh session per tick.

    After feat-393 M1, _submit_run must reuse the same session for successive ticks
    instead of calling create_session on every tick.  This verifies the fresh-session
    roaming is eliminated.
    """
    from datetime import UTC, datetime
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.scheduler.heartbeat_scheduler import (
        HeartbeatScheduler,
        HeartbeatSchedulerStateStore,
    )

    class _FakeKernelClient:
        def __init__(self) -> None:
            self.created_sessions: list[dict] = []
            self.sent_messages: list[dict] = []
            self._session_counter = 0
            self._run_counter = 0

        async def create_session(
            self,
            *,
            workspace_root: str,
            product_id: str,
            title: str | None = None,
            **_kw,
        ) -> dict:
            self._session_counter += 1
            session_id = f"sess-{self._session_counter}"
            self.created_sessions.append({"session_id": session_id})
            return {"session_id": session_id}

        def submit_message(self, *, session_id: str, texts: list[str], **_kw) -> dict:
            self._run_counter += 1
            payload = {"run_id": f"run-{self._run_counter}", "session_id": session_id}
            self.sent_messages.append(payload)
            return payload

    agent_dir = tmp_path / "agent-a"
    agent_dir.mkdir()
    (agent_dir / "HEARTBEAT.md").write_text(
        "interval: 1s\n\n- Check status\n", encoding="utf-8"
    )

    agent = AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agent_dir, heartbeat_enabled=True)
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    from datetime import timedelta

    t0 = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
    await_tick = asyncio.run

    # Tick 1
    await_tick(scheduler.tick(now=t0))
    # Tick 2 — one interval later
    await_tick(scheduler.tick(now=t0 + timedelta(seconds=2)))

    # After feat-393: only one session created (stable :heartbeat session reused)
    assert len(kernel.created_sessions) == 1, (
        f"Expected 1 session (stable :heartbeat reuse); got {len(kernel.created_sessions)} sessions. "
        "fresh-session per tick must be eliminated (feat-393 decision 4)."
    )
    # Both ticks should use the same session_id
    session_ids_used = [msg["session_id"] for msg in kernel.sent_messages]
    assert len(set(session_ids_used)) == 1, (
        f"Both ticks must use the same session_id; got {session_ids_used}"
    )


# ---------------------------------------------------------------------------
# feat-394 decision 3: canonical_session_store populated from session_store
# ---------------------------------------------------------------------------


# feat-394: test removed — the reactive canonical_session_store promotion
# (via turn_start ack → session_store lookup) has been replaced by tick-time
# proactive query (HeartbeatScheduler.tick → session_store.find_direct_by_agent).
# The new behaviour is covered by:
#   tests/unit/personal_assistant/test_heartbeat_m1_abc.py:
#     test_heartbeat_scheduler_uses_find_direct_by_agent_before_submit
