"""Projection tests for channel runtime status causality and IM timestamps."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from IM.infra.channel_control_store import ChannelControlStore
from IM.infra.channel_credentials import generate_channel_key_pair
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository


def _store_with_channel(tmp_path: Path) -> tuple[ChannelControlStore, str]:
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    NodeRepository(connection).upsert_node(
        node_id="node-a", node_name="Node A", owner_id="owner-a", status="offline"
    )
    AgentProfileRepository(connection).upsert_profile(
        agent_id="agent-a",
        owner_id="owner-a",
        node_id="node-a",
        display_name="Agent A",
        description="",
        system_prompt="You are Agent A.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    connection.close()
    pair = generate_channel_key_pair(private_seed=b"s" * 32)
    store = ChannelControlStore(db_path)
    store.register_node_public_key(
        owner_id="owner-a",
        node_id="node-a",
        key_id=pair.key_id,
        algorithm="X25519-HKDF-SHA256-AES-256-GCM",
        public_key=pair.public_key,
    )
    channel = store.create_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        secret={"app_secret": "secret"},
    ).channel
    return store, channel.channel_id


def _status(channel_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": "node-a",
        "channel_id": channel_id,
        "channel_revision": 1,
        "runtime_incarnation": "inc-a",
        "status_sequence": 1,
        "instance_started": True,
        "connection_state": "connected",
        "diagnostics_state": "complete",
        "checks": [],
        "received_at": "1999-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_incarnation_barrier_sequence_and_im_received_time_are_authoritative(
    tmp_path: Path,
) -> None:
    store, channel_id = _store_with_channel(tmp_path)
    assert store.record_status(_status(channel_id)) == "accepted"
    assert (
        store.record_status(
            _status(channel_id, status_sequence=1, instance_started=False)
        )
        == "already_current"
    )
    assert (
        store.record_status(
            _status(
                channel_id,
                runtime_incarnation="inc-b",
                status_sequence=2,
                instance_started=False,
            )
        )
        == "already_current"
    )
    assert (
        store.record_status(_status(channel_id, runtime_incarnation="inc-b"))
        == "accepted"
    )

    observed = store.list_channels(owner_id="owner-a", agent_id="agent-a")[0].observed
    assert observed is not None
    assert observed["status_updated_at"] != "1999-01-01T00:00:00Z"
    assert observed["status_stale"] is True
    with connect(tmp_path / "im.db") as connection:
        status = connection.execute(
            "SELECT runtime_incarnation, status_sequence "
            "FROM agent_channel_status WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
    assert status is not None
    assert tuple(status) == ("inc-b", 1)


def test_node_owner_drift_returns_fatal_outcome(tmp_path: Path) -> None:
    store, channel_id = _store_with_channel(tmp_path)
    with connect(tmp_path / "im.db") as connection:
        connection.execute(
            "UPDATE nodes SET owner_id = 'owner-b' WHERE node_id = 'node-a'"
        )

    assert store.record_status(_status(channel_id)) == "fatal_owner_mismatch"


def test_busy_status_transaction_returns_correlated_retryable_outcome(
    tmp_path: Path,
) -> None:
    store, channel_id = _store_with_channel(tmp_path)

    class _BusyConnection:
        def execute(self, _sql: str, _parameters: object = ()) -> None:
            raise sqlite3.OperationalError("database is locked")

        def close(self) -> None:
            pass

    store._connect = lambda: _BusyConnection()  # type: ignore[method-assign]  # noqa: SLF001

    assert store.record_status(_status(channel_id)) == "retryable_store_busy"
