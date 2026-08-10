"""Durable Gateway configuration-boundary outbox regressions."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import (
    BoundaryDispatchAcked,
    BoundaryDispatchIdle,
    BoundaryDispatchPermanentlyRejected,
    BoundaryDispatchReady,
    BoundaryDispatchRetryableFailure,
    BoundaryDispatchWait,
    ConversationBindingRequest,
    GatewaySessionBinder,
)
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
)


def _intent(
    *,
    boundary_id: str = "boundary-1",
    runtime_fingerprint: str = "runtime-b",
    profile_version: int = 7,
) -> BoundaryIntent:
    return BoundaryIntent(
        boundary_id=boundary_id,
        node_id="node-1",
        conversation_id="conversation-1",
        agent_id="agent-1",
        before_message_id="message-1",
        runtime_fingerprint=runtime_fingerprint,
        fingerprint_schema="runtime-v1",
        profile_version=profile_version,
        applied_at="2026-07-21T12:00:00Z",
    )


def _binder(
    tmp_path: Path,
    *,
    db_path: Path | None = None,
    retry_initial_seconds: float = 1.0,
) -> tuple[LiveAgentCatalog, GatewaySessionBinder, object, object]:
    workspace = tmp_path / "agent-1"
    workspace.mkdir(exist_ok=True)
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-1", workspace_root=workspace),)
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=object(),
        db_path=db_path or tmp_path / "session_bindings.sqlite3",
        boundary_retry_initial_seconds=retry_initial_seconds,
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
    binding = binder.persist_applied_runtime(
        result.binding,
        runtime_fingerprint="runtime-a",
        fingerprint_schema="runtime-v1",
        profile_version=6,
        agent=agent,
    )
    return catalog, binder, binding, agent


def test_applied_runtime_and_boundary_survive_gateway_restart(tmp_path: Path) -> None:
    """A crash after actual application preserves the unsent anchored fact."""

    db_path = tmp_path / "session_bindings.sqlite3"
    catalog, binder, binding, agent = _binder(tmp_path, db_path=db_path)

    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=_intent(),
        agent=agent,
    )

    restarted = GatewaySessionBinder(catalog=catalog, kernel=object(), db_path=db_path)
    restored = restarted.lookup("web_relay:conversation-1:agent-1")

    assert restored is not None
    assert restored.applied_runtime_fingerprint == "runtime-b"
    assert restored.applied_profile_version == 7
    assert restarted.next_boundary_dispatch() == BoundaryDispatchReady(_intent())


def test_ack_deletes_only_its_durable_boundary(tmp_path: Path) -> None:
    """A success ACK consumes its own intent while later facts remain retryable."""

    _catalog, binder, binding, agent = _binder(tmp_path)
    first = _intent(boundary_id="boundary-1")
    second = _intent(
        boundary_id="boundary-2",
        runtime_fingerprint="runtime-c",
        profile_version=8,
    )
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=first,
        agent=agent,
    )
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-c",
        fingerprint_schema="runtime-v1",
        profile_version=8,
        boundary=second,
        agent=agent,
    )

    binder.complete_boundary_dispatch("boundary-1", BoundaryDispatchAcked())

    assert binder.next_boundary_dispatch() == BoundaryDispatchReady(second)


def test_error_ack_keeps_boundary_for_retry_or_diagnosis(tmp_path: Path) -> None:
    """An IM error cannot silently erase an actual-applied boundary fact."""

    _catalog, binder, binding, agent = _binder(tmp_path)
    intent = _intent()
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=intent,
        agent=agent,
    )

    binder.complete_boundary_dispatch(
        "boundary-1",
        BoundaryDispatchPermanentlyRejected(reason="anchor is not owned by agent"),
    )

    assert isinstance(binder.next_boundary_dispatch(), BoundaryDispatchIdle)
    assert binder._repository.quarantined_boundaries() == (intent,)  # noqa: SLF001


def test_retry_backoff_survives_gateway_restart(tmp_path: Path) -> None:
    """A retryable wire failure retains its deferred durable delivery deadline."""

    db_path = tmp_path / "session_bindings.sqlite3"
    catalog, binder, binding, agent = _binder(
        tmp_path, db_path=db_path, retry_initial_seconds=5
    )
    intent = _intent()
    binder.persist_applied_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=intent,
        agent=agent,
    )
    binder.complete_boundary_dispatch(
        intent.boundary_id,
        BoundaryDispatchRetryableFailure(reason="IM connection interrupted"),
    )

    restarted = GatewaySessionBinder(
        catalog=catalog,
        kernel=object(),
        db_path=db_path,
        boundary_retry_initial_seconds=5,
    )

    plan = restarted.next_boundary_dispatch()
    assert isinstance(plan, BoundaryDispatchWait)
    assert 0 < plan.delay_seconds <= 5
