"""Durability tests for the managed-channel status outbox."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore


def _status(
    request_id: str,
    *,
    sequence: int,
    incarnation: str = "inc-a",
    revision: int = 1,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "node_id": "node-a",
        "channel_id": "ch-a",
        "channel_revision": revision,
        "runtime_incarnation": incarnation,
        "status_sequence": sequence,
        "instance_started": sequence == 1,
        "connection_state": "connecting" if sequence == 1 else "connected",
        "diagnostics_state": "unknown",
        "checks": [],
    }


def test_barrier_survives_restart_and_gates_coalesced_latest_status(
    tmp_path: Path,
) -> None:
    """Offline seq>1 state cannot overtake an unacknowledged incarnation barrier."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    store.record_channel_status(_status("status-1", sequence=1))
    store.record_channel_status(_status("status-2", sequence=2))
    store.record_channel_status(_status("status-3", sequence=3))

    restarted = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    assert [item["request_id"] for item in restarted.pending_channel_statuses()] == [
        "status-1"
    ]

    barrier_ack = restarted.apply_channel_status_result(
        request_id="status-1", outcome="accepted"
    )
    assert barrier_ack is not None
    assert barrier_ack.channel_id == "ch-a"
    assert barrier_ack.channel_revision == 1
    assert [item["request_id"] for item in restarted.pending_channel_statuses()] == [
        "status-3"
    ]

    restarted.apply_channel_status_result(
        request_id="status-3", outcome="already_current"
    )
    assert restarted.pending_channel_statuses() == ()


def test_terminal_and_retryable_results_have_distinct_outbox_effects(
    tmp_path: Path,
) -> None:
    """Terminal drift drops a generation while store-busy retains it for retry."""
    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id="key-a",
    )
    store.record_channel_status(_status("status-1", sequence=1))
    store.record_channel_status(_status("status-2", sequence=2))

    retry = store.apply_channel_status_result(
        request_id="status-1", outcome="retryable_store_busy"
    )
    assert retry is not None and retry.outcome == "retryable_store_busy"
    assert [item["request_id"] for item in store.pending_channel_statuses()] == [
        "status-1"
    ]

    terminal = store.apply_channel_status_result(
        request_id="status-1", outcome="terminal_stale_revision"
    )
    assert terminal is not None and terminal.outcome == "terminal_stale_revision"
    assert store.pending_channel_statuses() == ()

