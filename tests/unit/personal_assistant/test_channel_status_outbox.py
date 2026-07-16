"""Durability tests for the managed-channel status outbox."""

from __future__ import annotations

import json
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


def test_new_incarnations_replace_old_status_state_without_retired_growth(
    tmp_path: Path,
) -> None:
    """Only the current incarnation is durable after repeated runtime restarts."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")

    for index in range(40):
        incarnation = f"inc-{index}"
        store.record_channel_status(
            _status(f"barrier-{index}", sequence=1, incarnation=incarnation)
        )
        store.record_channel_status(
            _status(f"snapshot-{index}", sequence=2, incarnation=incarnation)
        )

    state = json.loads(path.read_text(encoding="utf-8"))
    entry = state["status_outbox"]["ch-a"]
    assert set(entry) == {
        "barrier",
        "channel_revision",
        "inflight",
        "latest",
        "runtime_incarnation",
    }
    assert entry["runtime_incarnation"] == "inc-39"
    assert entry["barrier"]["request_id"] == "barrier-39"
    assert entry["latest"]["request_id"] == "snapshot-39"
    assert "barrier-0" not in path.read_text(encoding="utf-8")

    restarted = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    assert [item["request_id"] for item in restarted.pending_channel_statuses()] == [
        "barrier-39"
    ]


def test_late_old_incarnation_ack_is_idempotent_and_cannot_unlock_current(
    tmp_path: Path,
) -> None:
    """An ACK for replaced state is a no-op while the current barrier still gates."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    store.record_channel_status(_status("old-barrier", sequence=1, incarnation="old"))
    store.record_channel_status(_status("old-latest", sequence=2, incarnation="old"))
    store.record_channel_status(_status("new-barrier", sequence=1, incarnation="new"))
    store.record_channel_status(_status("new-latest", sequence=2, incarnation="new"))
    assert (
        store.record_channel_status(
            _status("old-after-new", sequence=3, incarnation="old")
        )
        is None
    )

    assert (
        store.apply_channel_status_result(request_id="old-barrier", outcome="accepted")
        is None
    )
    assert (
        store.apply_channel_status_result(
            request_id="old-latest", outcome="terminal_stale_revision"
        )
        is None
    )
    assert [item["request_id"] for item in store.pending_channel_statuses()] == [
        "new-barrier"
    ]

    current = store.apply_channel_status_result(
        request_id="new-barrier", outcome="accepted"
    )
    assert current is not None
    assert current.next_payload is not None
    assert current.next_payload["request_id"] == "new-latest"

    restarted = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    assert [item["request_id"] for item in restarted.pending_channel_statuses()] == [
        "new-latest"
    ]
    restarted.apply_channel_status_result(
        request_id="new-latest", outcome="already_current"
    )
    assert restarted.pending_channel_statuses() == ()


def test_restart_prunes_legacy_retired_statuses_from_disk(tmp_path: Path) -> None:
    """Reading pending state migrates legacy retired ACK bookkeeping away."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    store.record_channel_status(_status("current", sequence=1))
    state = json.loads(path.read_text(encoding="utf-8"))
    state["status_outbox"]["ch-a"]["retired"] = {
        "old": _status("old", sequence=1, incarnation="old")
    }
    path.write_text(json.dumps(state), encoding="utf-8")

    restarted = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    assert [item["request_id"] for item in restarted.pending_channel_statuses()] == [
        "current"
    ]
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert "retired" not in persisted["status_outbox"]["ch-a"]
