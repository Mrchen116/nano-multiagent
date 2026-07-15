"""Behavior tests for the independent IM channel-control transaction owner."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from IM.infra.channel_control_store import ChannelControlError, ChannelControlStore
from IM.infra.channel_credentials import generate_channel_key_pair
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import AgentProfileRepository, NodeRepository


def _seed_store(tmp_path: Path) -> tuple[ChannelControlStore, str]:
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    nodes = NodeRepository(connection)
    nodes.upsert_node(
        node_id="node-a", node_name="Node A", owner_id="owner-a", status="online"
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
    pair = generate_channel_key_pair(private_seed=b"d" * 32)
    store = ChannelControlStore(db_path)
    store.register_node_public_key(
        owner_id="owner-a",
        node_id="node-a",
        key_id=pair.key_id,
        algorithm="X25519-HKDF-SHA256-AES-256-GCM",
        public_key=pair.public_key,
    )
    return store, pair.private_key


def _create(store: ChannelControlStore):
    return store.create_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_original"},
        secret={"app_secret": "top-secret"},
    )


def test_create_is_atomic_and_persists_only_an_envelope(tmp_path: Path) -> None:
    """Desired state and its complete manifest commit together without plaintext."""
    store, _ = _seed_store(tmp_path)
    result = _create(store)

    assert result.channel.channel_revision == 1
    assert result.channel.credential_revision == 1
    assert result.channel.secret_configured is True
    assert result.channel.sync_state == "pending"
    assert result.manifest.manifest_revision == 1
    assert [item.channel_id for item in result.manifest.channels] == [
        result.channel.channel_id
    ]
    assert result.manifest.channels[0].channel_revision == 1

    connection = sqlite3.connect(tmp_path / "im.db")
    row = connection.execute(
        "SELECT config_json, credential_envelope_json FROM agent_channels"
    ).fetchone()
    head = connection.execute(
        "SELECT manifest_revision FROM channel_manifest_heads WHERE node_id = ?",
        ("node-a",),
    ).fetchone()
    connection.close()
    assert row is not None and head == (1,)
    assert "top-secret" not in row[0]
    assert "top-secret" not in row[1]


def test_parallel_old_revision_allows_exactly_one_atomic_update(
    tmp_path: Path,
) -> None:
    """Independent SQLite connections serialize two writers using one old token."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)

    def update(app_id: str):
        try:
            return store.update_channel(
                owner_id="owner-a",
                agent_id="agent-a",
                channel_id=created.channel.channel_id,
                expected_revision=1,
                enabled=True,
                config={"app_id": app_id},
                credential_mode="replace",
                secret={"app_secret": f"secret-for-{app_id}"},
            )
        except ChannelControlError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, ["cli_one", "cli_two"]))

    successes = [item for item in outcomes if not isinstance(item, Exception)]
    conflicts = [item for item in outcomes if isinstance(item, ChannelControlError)]
    assert len(successes) == 1
    assert [item.code for item in conflicts] == ["channel_revision_conflict"]
    winner = successes[0]
    assert winner.channel.channel_revision == 2
    assert winner.channel.credential_revision == 2
    assert winner.manifest.manifest_revision == 2
    assert winner.manifest.channels[0].channel_revision == 2
    latest = store.list_channels(owner_id="owner-a", agent_id="agent-a")
    assert latest == [winner.channel]


def test_keep_preserves_envelope_but_app_id_change_requires_replace(
    tmp_path: Path,
) -> None:
    """Credential retention is explicit and cannot cross a Feishu application identity."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)
    kept = store.update_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        channel_id=created.channel.channel_id,
        expected_revision=1,
        enabled=False,
        config={"app_id": "cli_original"},
        credential_mode="keep",
    )
    assert kept.channel.channel_revision == 2
    assert kept.channel.credential_revision == 1

    with pytest.raises(ChannelControlError) as error:
        store.update_channel(
            owner_id="owner-a",
            agent_id="agent-a",
            channel_id=created.channel.channel_id,
            expected_revision=2,
            enabled=True,
            config={"app_id": "cli_replacement"},
            credential_mode="keep",
        )
    assert error.value.code == "channel_credentials_required"


def test_owner_scope_hides_channels_and_missing_key_fails_closed(tmp_path: Path) -> None:
    """Tenant isolation and absent node keys never leak channel or credential data."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)
    assert store.list_channels(owner_id="owner-b", agent_id="agent-a") == []
    with pytest.raises(ChannelControlError) as hidden:
        store.update_channel(
            owner_id="owner-b",
            agent_id="agent-a",
            channel_id=created.channel.channel_id,
            expected_revision=1,
            enabled=True,
            config={"app_id": "cli_original"},
            credential_mode="keep",
        )
    assert hidden.value.code == "channel_not_found"

    with connect(tmp_path / "im.db") as connection:
        connection.execute("DELETE FROM node_credential_keys WHERE node_id = ?", ("node-a",))
    with pytest.raises(ChannelControlError) as no_key:
        store.update_channel(
            owner_id="owner-a",
            agent_id="agent-a",
            channel_id=created.channel.channel_id,
            expected_revision=1,
            enabled=True,
            config={"app_id": "cli_original"},
            credential_mode="replace",
            secret={"app_secret": "replacement"},
        )
    assert no_key.value.code == "channel_credential_key_unavailable"
