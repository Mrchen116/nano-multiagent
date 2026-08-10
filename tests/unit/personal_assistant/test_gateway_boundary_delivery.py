"""Gateway boundary outbox delivery behavior."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.boundary_outbox import BoundaryOutboxDispatcher
from personal_assistant.gateway.session_binder import (
    BoundaryDispatchIdle,
    ConversationBindingRequest,
    GatewaySessionBinder,
)
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
)
from personal_assistant.ws.im_connection import IMFrameRejectedError


def _intent(*, boundary_id: str = "boundary-1") -> BoundaryIntent:
    return BoundaryIntent(
        boundary_id=boundary_id,
        node_id="node-1",
        conversation_id="conversation-1",
        agent_id="agent-1",
        before_message_id="message-1",
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        applied_at="2026-07-21T12:00:00Z",
    )


class _Connection:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, object]]] = []

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        self.sent.append((message_type, payload))
        return {"message_type": message_type, "boundary_id": payload["boundary_id"]}


def _binder(
    tmp_path: Path,
    *,
    retry_initial_seconds: float = 1.0,
    retry_max_seconds: float = 60.0,
) -> tuple[GatewaySessionBinder, object, object]:
    workspace = tmp_path / "agent-1"
    workspace.mkdir(exist_ok=True)
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-1", workspace_root=workspace),)
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=object(),
        db_path=tmp_path / "bindings.sqlite3",
        boundary_retry_initial_seconds=retry_initial_seconds,
        boundary_retry_max_seconds=retry_max_seconds,
    )
    agent = catalog.require("agent-1")
    result = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conversation-1",
            agent_id="agent-1",
            kernel_session_id="session-1",
            guard=binder.capture_write_guard(agent),
        ),
        agent,
    )
    assert result.binding is not None
    return binder, result.binding, agent


def test_reconnect_drain_acknowledges_each_durable_boundary(tmp_path: Path) -> None:
    """A reconnect drains persisted items through the ACK-gated wire protocol."""

    binder, binding, agent = _binder(tmp_path)
    intent = _intent()
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint=intent.runtime_fingerprint,
        fingerprint_schema=intent.fingerprint_schema,
        profile_version=intent.profile_version,
        boundary=intent,
        agent=agent,
    )
    connection = _Connection()

    asyncio.run(BoundaryOutboxDispatcher(binder=binder).drain(connection))

    assert connection.sent == [("agent.config.boundary", asdict(intent))]
    assert isinstance(binder.next_boundary_dispatch(), BoundaryDispatchIdle)


class _RejectedConnection:
    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        raise IMFrameRejectedError(
            "IM rejected agent.config.boundary frame (anchor_not_found): message missing",
            code="anchor_not_found",
        )


def test_deterministic_ack_rejection_quarantines_without_deleting(
    tmp_path: Path,
) -> None:
    """An anchor rejection remains inspectable rather than disappearing on retry."""

    binder, binding, agent = _binder(tmp_path)
    intent = _intent()
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint=intent.runtime_fingerprint,
        fingerprint_schema=intent.fingerprint_schema,
        profile_version=intent.profile_version,
        boundary=intent,
        agent=agent,
    )

    asyncio.run(BoundaryOutboxDispatcher(binder=binder).drain(_RejectedConnection()))

    assert isinstance(binder.next_boundary_dispatch(), BoundaryDispatchIdle)
    assert binder._repository.quarantined_boundaries() == (intent,)  # noqa: SLF001


class _RetryThenAcknowledgeConnection:
    def __init__(self) -> None:
        self.attempted_boundary_ids: list[str] = []
        self._first_attempt = True

    async def send_json_await_ack(
        self, _message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        boundary_id = str(payload["boundary_id"])
        self.attempted_boundary_ids.append(boundary_id)
        if self._first_attempt:
            self._first_attempt = False
            raise RuntimeError("IM connection interrupted")
        return {"boundary_id": boundary_id}


def test_retryable_delivery_failure_is_durably_deferred_and_retried(
    tmp_path: Path,
) -> None:
    """A retryable failure waits by durable backoff without erasing later facts."""

    binder, binding, agent = _binder(
        tmp_path,
        retry_initial_seconds=0,
        retry_max_seconds=0,
    )
    first = _intent(boundary_id="boundary-1")
    second = _intent(boundary_id="boundary-2")
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint=first.runtime_fingerprint,
        fingerprint_schema=first.fingerprint_schema,
        profile_version=first.profile_version,
        boundary=first,
        agent=agent,
    )
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint=second.runtime_fingerprint,
        fingerprint_schema=second.fingerprint_schema,
        profile_version=second.profile_version,
        boundary=second,
        agent=agent,
    )
    connection = _RetryThenAcknowledgeConnection()

    async def deliver() -> None:
        task = BoundaryOutboxDispatcher(
            binder=binder,
        ).schedule_drain(connection)
        await task

    asyncio.run(deliver())

    assert connection.attempted_boundary_ids == [
        "boundary-1",
        "boundary-2",
        "boundary-1",
    ]
    assert isinstance(binder.next_boundary_dispatch(), BoundaryDispatchIdle)


def test_new_boundary_is_delivered_on_the_current_registered_connection(
    tmp_path: Path,
) -> None:
    """A runtime replacement drains immediately without requiring a reconnect."""

    binder, binding, agent = _binder(tmp_path)
    intent = _intent()
    connection = _Connection()

    async def deliver() -> None:
        dispatcher = BoundaryOutboxDispatcher(binder=binder)
        await dispatcher.schedule_drain(connection)
        binder.persist_applied_runtime_with_boundary(
            binding,
            runtime_fingerprint=intent.runtime_fingerprint,
            fingerprint_schema=intent.fingerprint_schema,
            profile_version=intent.profile_version,
            boundary=intent,
            agent=agent,
        )
        task = dispatcher.notify_pending()
        assert task is not None
        await task

    asyncio.run(deliver())

    assert connection.sent == [("agent.config.boundary", asdict(intent))]
    assert isinstance(binder.next_boundary_dispatch(), BoundaryDispatchIdle)
