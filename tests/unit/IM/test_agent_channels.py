"""Behavior tests for the independent IM channel-control transaction owner."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from IM.infra.channel_control_store import (
    ChannelControlError,
    ChannelControlStore,
    ChannelRemovalView,
)
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


def test_delete_persists_removal_until_applied_and_preserves_shadow_history(
    tmp_path: Path,
) -> None:
    """DELETE removes desired credentials, not its durable shadow conversation history."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)
    with connect(tmp_path / "im.db") as connection:
        connection.execute(
            "INSERT INTO users(id, username, display_name, owner_id, created_at) "
            "VALUES ('user-a', 'user-a', 'User A', 'owner-a', '2026-07-15T00:00:00Z')"
        )
        connection.execute(
            """
            INSERT INTO conversations(
                id, title, type, owner_id, creator_id, config_agent_id,
                external_source, external_chat_id, created_at
            ) VALUES (
                'conv-a', 'Feishu chat', 'direct', 'owner-a', 'user-a', 'agent-a',
                'feishu:agent-a', 'oc-a', '2026-07-15T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO messages(
                id, conversation_id, sender_user_id, sender_type, content,
                delivery_status, created_at
            ) VALUES (
                'msg-a', 'conv-a', 'user-a', 'user', 'history stays',
                'delivered', '2026-07-15T00:00:00Z'
            )
            """
        )

    deleted = store.delete_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        channel_id=created.channel.channel_id,
        expected_revision=1,
    )

    assert deleted.manifest.channels == ()
    assert len(deleted.manifest.removals) == 1
    removal = deleted.removal
    assert removal.apply_state == "pending"
    assert removal.deletion_manifest_revision == 2
    assert store.list_channels(owner_id="owner-a", agent_id="agent-a") == [
        removal
    ]
    assert isinstance(removal, ChannelRemovalView)
    with pytest.raises(ChannelControlError) as duplicate:
        _create(store)
    assert duplicate.value.code == "channel_deletion_pending"
    with connect(tmp_path / "im.db") as connection:
        assert connection.execute(
            "SELECT content FROM messages WHERE id = 'msg-a'"
        ).fetchone()[0] == "history stays"


def test_failed_removal_retries_same_revision_then_hides_only_after_result(
    tmp_path: Path,
) -> None:
    """Stop failures survive reload while an applied result ends the deleting view."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)
    deleted = store.delete_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        channel_id=created.channel.channel_id,
        expected_revision=1,
    )
    intent = deleted.manifest.removals[0]

    failed_ack = store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=2,
        outcome="retryable_failed",
        applied_channel_ids=(),
        removal_outcomes=(
            {
                "removal_token": intent.removal_token,
                "channel_id": intent.channel_id,
                "outcome": "failed",
                "error_code": "runtime_stop_failed",
                "error_message": "worker exit timed out",
            },
        ),
        failures=(),
    )
    failed = store.list_channels(owner_id="owner-a", agent_id="agent-a")[0]
    assert failed.apply_state == "failed"
    assert failed.apply_error == {
        "code": "runtime_stop_failed",
        "message": "worker exit timed out",
    }
    assert failed_ack["removal_token_outcomes"][0]["outcome"] == "accepted"
    retried = store.retry_removal(
        owner_id="owner-a",
        agent_id="agent-a",
        channel_id=intent.channel_id,
    )
    assert retried.manifest_revision == 2
    assert retried.removals == (intent,)

    applied_ack = store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=2,
        outcome="applied",
        applied_channel_ids=(),
        removal_outcomes=(
            {
                "removal_token": intent.removal_token,
                "channel_id": intent.channel_id,
                "outcome": "applied",
            },
        ),
        failures=(),
    )
    assert applied_ack["head_outcome"] == "accepted"
    assert store.list_channels(owner_id="owner-a", agent_id="agent-a") == []


def test_pruned_receipt_replay_is_terminal_only_after_applied_head(
    tmp_path: Path,
) -> None:
    """A token lost beyond retention terminates from the covered node applied head."""
    store, _ = _seed_store(tmp_path)
    created = _create(store)
    deleted = store.delete_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        channel_id=created.channel.channel_id,
        expected_revision=1,
    )
    intent = deleted.manifest.removals[0]
    store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=2,
        outcome="applied",
        applied_channel_ids=(),
        removal_outcomes=(
            {
                "removal_token": intent.removal_token,
                "channel_id": intent.channel_id,
                "outcome": "applied",
            },
        ),
        failures=(),
    )
    with connect(tmp_path / "im.db") as connection:
        connection.execute(
            "UPDATE agent_channel_removals SET expires_at = '2000-01-01T00:00:00Z'"
        )
    assert store.prune_applied_removals() == 1
    replacement = _create(store)
    assert replacement.manifest.manifest_revision == 3

    replay = store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=3,
        outcome="applied",
        applied_channel_ids=(),
        removal_outcomes=(
            {
                "removal_token": intent.removal_token,
                "channel_id": intent.channel_id,
                "outcome": "applied",
                "deletion_manifest_revision": 2,
            },
        ),
        failures=(),
    )
    assert replay["removal_token_outcomes"] == [
        {
            "removal_token": intent.removal_token,
            "outcome": "already_applied_by_head",
        }
    ]
