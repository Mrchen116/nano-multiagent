"""Projection regressions for durable channel-apply failures."""

from __future__ import annotations

from pathlib import Path

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
    pair = generate_channel_key_pair(private_seed=b"p" * 32)
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


def test_cache_failure_remains_failed_across_reload_until_same_revision_applies(
    tmp_path: Path,
) -> None:
    """A current runtime status cannot hide a failed durable manifest commit."""
    store, channel_id = _store_with_channel(tmp_path)
    store.record_status(
        {
            "node_id": "node-a",
            "channel_id": channel_id,
            "channel_revision": 1,
            "runtime_incarnation": "inc-a",
            "status_sequence": 1,
            "instance_started": True,
            "connection_state": "connected",
            "diagnostics_state": "complete",
            "checks": [],
        }
    )
    store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=1,
        outcome="retryable_failed",
        applied_channel_ids=(channel_id,),
        removal_outcomes=(),
        failures=(
            {
                "error_code": "cache_commit_failed",
                "error_message": "disk is full",
            },
        ),
    )

    reloaded = ChannelControlStore(tmp_path / "im.db")
    failed = reloaded.list_channels(owner_id="owner-a", agent_id="agent-a")[0]
    assert failed.sync_state == "failed"
    assert failed.observed is not None
    assert failed.observed["connection_state"] == "connected"
    assert failed.apply_error == {
        "code": "cache_commit_failed",
        "message": "disk is full",
    }

    reloaded.record_reconcile_result(
        node_id="node-a",
        manifest_revision=1,
        outcome="applied",
        applied_channel_ids=(channel_id,),
        removal_outcomes=(),
        failures=(),
    )
    applied = reloaded.list_channels(owner_id="owner-a", agent_id="agent-a")[0]
    assert applied.sync_state == "applied"
    assert applied.apply_error is None


def test_first_apply_failure_is_visible_before_any_runtime_status(
    tmp_path: Path,
) -> None:
    """A durable head failure does not depend on a runtime observation existing."""
    store, channel_id = _store_with_channel(tmp_path)
    store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=1,
        outcome="retryable_failed",
        applied_channel_ids=(),
        removal_outcomes=(),
        failures=(
            {
                "error_code": "channel_start_failed",
                "error_message": "credential rejected",
            },
        ),
    )

    failed = store.list_channels(owner_id="owner-a", agent_id="agent-a")[0]
    assert failed.observed is None
    assert failed.sync_state == "failed"
    assert failed.apply_error == {
        "code": "channel_start_failed",
        "message": "credential rejected",
    }

    store.record_reconcile_result(
        node_id="node-a",
        manifest_revision=1,
        outcome="applied",
        applied_channel_ids=(channel_id,),
        removal_outcomes=(),
        failures=(),
    )
    recovered = store.list_channels(owner_id="owner-a", agent_id="agent-a")[0]
    assert recovered.observed is None
    assert recovered.sync_state == "pending"
    assert recovered.apply_error is None
