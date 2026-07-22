"""Durable Gateway configuration-boundary outbox regressions."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
    PersistentSessionBindingStore,
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


def _binding(store: PersistentSessionBindingStore):
    return store.bind(
        session_key="web_relay:conversation-1:agent-1",
        kernel_session_id="session-1",
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id="conversation-1",
        ),
        applied_runtime_fingerprint="runtime-a",
        applied_fingerprint_schema="runtime-v1",
        applied_profile_version=6,
    )


def test_applied_runtime_and_boundary_survive_gateway_restart(tmp_path: Path) -> None:
    """A crash after actual application preserves the unsent anchored fact."""

    db_path = tmp_path / "session_bindings.sqlite3"
    store = PersistentSessionBindingStore(db_path=db_path)
    binding = _binding(store)

    store.apply_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=_intent(),
    )

    restarted = PersistentSessionBindingStore(db_path=db_path)
    restored = restarted.get("web_relay:conversation-1:agent-1")

    assert restored is not None
    assert restored.applied_runtime_fingerprint == "runtime-b"
    assert restored.applied_profile_version == 7
    assert restarted.pending_boundaries() == (_intent(),)


def test_ack_deletes_only_its_durable_boundary(tmp_path: Path) -> None:
    """A success ACK consumes its own intent while later facts remain retryable."""

    store = PersistentSessionBindingStore(db_path=tmp_path / "session_bindings.sqlite3")
    binding = _binding(store)
    first = _intent(boundary_id="boundary-1")
    second = _intent(
        boundary_id="boundary-2",
        runtime_fingerprint="runtime-c",
        profile_version=8,
    )
    store.apply_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=first,
    )
    store.apply_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-c",
        fingerprint_schema="runtime-v1",
        profile_version=8,
        boundary=second,
    )

    store.acknowledge_boundary("boundary-1")

    assert store.pending_boundaries() == (second,)


def test_error_ack_keeps_boundary_for_retry_or_diagnosis(tmp_path: Path) -> None:
    """An IM error cannot silently erase an actual-applied boundary fact."""

    store = PersistentSessionBindingStore(db_path=tmp_path / "session_bindings.sqlite3")
    binding = _binding(store)
    intent = _intent()
    store.apply_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=intent,
    )

    store.record_boundary_error("boundary-1", reason="anchor is not owned by agent")

    assert store.pending_boundaries() == ()
    assert store.quarantined_boundaries() == (intent,)


def test_retry_backoff_survives_gateway_restart(tmp_path: Path) -> None:
    """A retryable wire failure retains its deferred durable delivery deadline."""

    db_path = tmp_path / "session_bindings.sqlite3"
    store = PersistentSessionBindingStore(db_path=db_path)
    binding = _binding(store)
    intent = _intent()
    store.apply_runtime_with_boundary(
        binding,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="runtime-v1",
        profile_version=7,
        boundary=intent,
    )
    store.defer_boundary_retry(
        intent.boundary_id,
        reason="IM connection interrupted",
        retry_initial_seconds=5,
        retry_max_seconds=60,
    )

    restarted = PersistentSessionBindingStore(db_path=db_path)

    assert restarted.pending_boundaries() == (intent,)
    assert restarted.delivery_ready_boundaries() == ()
    retry_delay = restarted.next_boundary_retry_delay()
    assert retry_delay is not None
    assert 0 < retry_delay <= 5
