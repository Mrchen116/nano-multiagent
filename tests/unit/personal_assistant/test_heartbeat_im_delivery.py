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
from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import GatewayConversationPersistence
from IM.infra.repositories import (
    ConversationRepository,
    EventRepository,
    MessageRepository,
    UsageMetricsRepository,
    UserRepository,
)
from IM.ws.gateway_handler import GatewayHandler
from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.inbound_models import RelayLifecycleUpdate
from personal_assistant.gateway.runtime_delivery.context import (
    OwnerDirectTarget,
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from personal_assistant.gateway.runtime_protocol import ShadowConversationRef


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


class _StreamingKernel:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self._events = events
        self.stream_calls: list[tuple[str, int]] = []

    async def stream(self, session_id: str, after_sequence: int = 0):
        self.stream_calls.append((session_id, after_sequence))
        for event in self._events:
            yield event


# ---------------------------------------------------------------------------
# Helper: build GatewayHandler wired to FK-enforced DB
# ---------------------------------------------------------------------------


def _build_im_db_and_handler(tmp_path: Path):  # noqa: ANN202
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    msg_repo = MessageRepository(connection)
    evt_repo = EventRepository(connection)
    bridge = EventBridge(message_repository=msg_repo, event_repository=evt_repo)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=msg_repo,
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


def test_owner_direct_context_store_suppresses_heartbeat_ok(tmp_path: Path) -> None:
    """Typed owner-direct delivery must keep HEARTBEAT_OK fully silent."""

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano-ok", display_name="Nano OK")
    users.create_user(username="agent:epsilon", display_name="Epsilon")

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["epsilon"], "capabilities": {}},
        )
    )

    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-hb-ok-1",
            agent_id="epsilon",
            kernel_session_id="sess-hb-ok",
            delivery_target=RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id=owner.id, agent_id="epsilon")
            ),
        )
    )
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=context_store,
    )

    async def _run() -> None:
        coro = observer(
            {"run_id": "run-hb-ok-1", "event": "run_status", "status": "running"}
        )
        if asyncio.iscoroutine(coro):
            await coro
        coro = observer(
            {
                "run_id": "run-hb-ok-1",
                "event": "assistant_message",
                "content": "HEARTBEAT_OK",
            }
        )
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    assert fake_manager.sent_frames == []
    assert ConversationRepository(connection).list_conversations() == []


def test_owner_direct_context_store_ack_backfills_and_continues_delta(
    tmp_path: Path,
) -> None:
    """Typed owner-direct delivery must store turn_start ack ids before delta."""

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano-ack", display_name="Nano Ack")
    users.create_user(username="agent:zeta", display_name="Zeta")

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["zeta"], "capabilities": {}},
        )
    )

    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-hb-ack-1",
            agent_id="zeta",
            kernel_session_id="sess-hb-ack",
            delivery_target=RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id=owner.id, agent_id="zeta")
            ),
        )
    )
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=context_store,
    )

    async def _run() -> None:
        coro = observer(
            {
                "run_id": "run-hb-ack-1",
                "event": "assistant_message",
                "content": "Daily summary: all good.",
                "message_id": "kernel-hb-ack",
            }
        )
        if asyncio.iscoroutine(coro):
            await coro

    asyncio.run(_run())

    legacy_ctx = context_store.legacy_contexts["run-hb-ack-1"]
    assert legacy_ctx["message_id"]
    assert legacy_ctx["conversation_id"]
    assert legacy_ctx["kernel_message_id"] == "kernel-hb-ack"
    assert [frame[1]["kind"] for frame in fake_manager.sent_frames] == [
        "turn_start",
        "message_delta",
    ]
    messages = MessageRepository(connection).list_messages(
        conversation_id=legacy_ctx["conversation_id"]
    )
    assert len(messages) == 1


def test_stream_run_to_completion_seeds_typed_store_seen_by_observer(
    tmp_path: Path,
) -> None:
    """Heartbeat/cron stream helper must seed the same typed store observer reads."""

    from personal_assistant.main import _stream_run_to_completion

    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano-stream", display_name="Nano Stream")
    users.create_user(username="agent:theta", display_name="Theta")

    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["theta"], "capabilities": {}},
        )
    )

    run_id = "run-hb-stream-typed"
    session_id = "sess-hb-stream-typed"
    context_store = RunDeliveryContextStore()
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=context_store,
    )
    kernel = _StreamingKernel(
        [
            {"run_id": run_id, "event": "run_status", "status": "running"},
            {
                "run_id": run_id,
                "event": "assistant_message",
                "content": "Daily summary from stream.",
                "message_id": "kernel-stream-msg",
            },
            {"run_id": run_id, "event": "turn_end", "completed": True},
            {"run_id": run_id, "event": "run_status", "status": "completed"},
        ]
    )

    final_text, popped_ctx = asyncio.run(
        _stream_run_to_completion(
            run_id=run_id,
            kernel_session_id=session_id,
            agent_id="theta",
            owner_user_id=owner.id,
            kernel=kernel,
            run_context_store=context_store,
            observer=observer,
            stream_anchor=7,
        )
    )

    assert final_text == "Daily summary from stream."
    assert popped_ctx is not None
    assert popped_ctx["conversation_id"]
    assert popped_ctx["message_id"]
    assert popped_ctx["kernel_message_id"] == "kernel-stream-msg"
    assert context_store.get(run_id) is None
    assert run_id not in context_store.legacy_contexts
    assert kernel.stream_calls == [(session_id, 7)]
    assert [frame[1]["kind"] for frame in fake_manager.sent_frames] == [
        "turn_start",
        "message_delta",
        "message_completed",
    ]


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


def test_group_no_reply_leaves_zero_agent_rows_in_fk_enforced_db(
    tmp_path: Path,
) -> None:
    """Group NO_REPLY rolls its eager placeholder back through the real IM handler."""
    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="group-user", display_name="Group User")
    agent_user = users.create_user(username="agent:quiet", display_name="Quiet")
    conv = ConversationRepository(connection).create_conversation(
        title="quiet group", participant_ids=[owner.id, agent_user.id]
    )
    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["quiet"], "capabilities": {}},
        )
    )

    run_id = "run-group-no-reply-1"
    run_context_store = RunDeliveryContextStore()
    run_context_store.seed(
        RunDeliveryContext(
            run_id=run_id,
            agent_id="quiet",
            kernel_session_id="sess-group-1",
            delivery_target=RunDeliveryTarget.shadow(
                ShadowConversationRef(conversation_id=conv.id)
            ),
            visibility_policy=ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS,
        )
    )
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        started = observer(
            {"run_id": run_id, "event": "run_status", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "run_id": run_id,
                "event": "assistant_message",
                "message_id": "kernel-msg-quiet",
                "content": "NO_REPLY",
            }
        )
        ended = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        assert asyncio.iscoroutine(ended)
        await ended

    asyncio.run(_run())

    assert MessageRepository(connection).list_messages(conversation_id=conv.id) == []
    assert [payload["kind"] for _, payload in fake_manager.sent_frames] == [
        "turn_start",
        "message_discarded",
    ]


def test_direct_web_no_reply_leaves_zero_agent_rows_in_fk_enforced_db(
    tmp_path: Path,
) -> None:
    """Direct Web IM silence is discarded before it can survive a history refresh."""
    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="direct-user", display_name="Direct User")
    agent_user = users.create_user(username="agent:quiet", display_name="Quiet")
    conv = ConversationRepository(connection).create_conversation(
        title="quiet direct", participant_ids=[owner.id, agent_user.id]
    )
    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["quiet"], "capabilities": {}},
        )
    )

    run_id = "run-direct-web-no-reply-1"
    run_context_store = RunDeliveryContextStore()
    context = run_context_store.seed_from_lifecycle(
        message=InboundMessage(
            channel_name="web_relay",
            text="stay quiet",
            external_user_id=owner.id,
            external_chat_id=conv.id,
            is_group=False,
            agent_id="quiet",
            metadata={"relay_task_id": "relay-1", "message_id": "user-msg-1"},
        ),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="quiet",
            session_key=f"web:{owner.id}:{conv.id}:quiet",
            run_id=run_id,
            kernel_session_id="sess-direct-1",
        ),
        owner_user_id=owner.id,
    )
    assert context is not None
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        started = observer(
            {"run_id": run_id, "event": "run_status", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "run_id": run_id,
                "event": "assistant_message",
                "message_id": "kernel-msg-quiet",
                "content": "NO_REPLY",
            }
        )
        ended = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        assert asyncio.iscoroutine(ended)
        await ended

    asyncio.run(_run())

    assert MessageRepository(connection).list_messages(conversation_id=conv.id) == []
    assert [payload["kind"] for _, payload in fake_manager.sent_frames] == [
        "turn_start",
        "message_discarded",
    ]


def test_direct_web_empty_completion_after_process_leaves_zero_agent_rows(
    tmp_path: Path,
) -> None:
    """Process events do not commit a Web bubble whose successful final text is empty."""
    connection, handler = _build_im_db_and_handler(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="direct-empty-user", display_name="Direct User")
    agent_user = users.create_user(username="agent:quiet-empty", display_name="Quiet")
    conv = ConversationRepository(connection).create_conversation(
        title="quiet direct", participant_ids=[owner.id, agent_user.id]
    )
    asyncio.run(
        handler.handle_message(
            websocket=_NullWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["quiet-empty"],
                "capabilities": {},
            },
        )
    )

    run_id = "run-direct-web-empty-1"
    run_context_store = RunDeliveryContextStore()
    context = run_context_store.seed_from_lifecycle(
        message=InboundMessage(
            channel_name="web_relay",
            text="run a tool, then stay quiet",
            external_user_id=owner.id,
            external_chat_id=conv.id,
            is_group=False,
            agent_id="quiet-empty",
            metadata={"relay_task_id": "relay-1", "message_id": "user-msg-1"},
        ),
        update=RelayLifecycleUpdate(
            phase="accepted",
            agent_id="quiet-empty",
            session_key=f"web:{owner.id}:{conv.id}:quiet-empty",
            run_id=run_id,
            kernel_session_id="sess-direct-empty-1",
        ),
        owner_user_id=owner.id,
    )
    assert context is not None
    fake_manager = _FakeIMManager(handler)
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: fake_manager,
        run_context_store=run_context_store,
    )

    async def _run() -> None:
        started = observer(
            {"run_id": run_id, "event": "run_status", "status": "running"}
        )
        assert asyncio.iscoroutine(started)
        await started
        observer(
            {
                "run_id": run_id,
                "event": "tool_start",
                "call_id": "tool-1",
                "name": "bash",
                "arguments": {"command": "printf OK"},
            }
        )
        observer(
            {
                "run_id": run_id,
                "event": "tool_end",
                "call_id": "tool-1",
                "name": "bash",
                "status": "completed",
                "result": "OK",
            }
        )
        observer(
            {
                "run_id": run_id,
                "event": "assistant_message",
                "message_id": "kernel-msg-quiet-empty",
                "content": "",
                "reasoning_content": "The tool completed; remain silent.",
                "group_id": "kernel-msg-quiet-empty",
            }
        )
        await asyncio.sleep(0)
        ended = observer({"run_id": run_id, "event": "turn_end", "completed": True})
        if asyncio.iscoroutine(ended):
            await ended
        await asyncio.sleep(0)

    asyncio.run(_run())

    assert MessageRepository(connection).list_messages(conversation_id=conv.id) == []
    kinds = [payload["kind"] for _, payload in fake_manager.sent_frames]
    assert kinds[-1] == "message_discarded"


# ---------------------------------------------------------------------------
