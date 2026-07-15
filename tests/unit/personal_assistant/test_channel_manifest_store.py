"""Behavior tests for the encrypted managed-channel cache and result outbox."""

from __future__ import annotations

import asyncio
from pathlib import Path
import stat

import pytest

from personal_assistant.channels.base import InboundHandler, OutboundMessage
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ChannelRemovalIntent,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_manifest_store import (
    ChannelManifestStore,
    ChannelManifestStoreError,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_stop_once: bool = False,
    ) -> None:
        self.name = name
        self._events = events
        self._fail_stop_once = fail_stop_once

    def start(self, _on_inbound: InboundHandler) -> None:
        self._events.append(f"start:{self.name}")

    def stop(self) -> None:
        self._events.append(f"stop:{self.name}")
        if self._fail_stop_once:
            self._fail_stop_once = False
            raise RuntimeError("worker exit timed out")

    def send(self, _outbound: OutboundMessage) -> None:
        self._events.append(f"send:{self.name}")


def _spec(*, channel_revision: int = 1) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_cache"},
        credentials={"app_secret": "plaintext-must-not-persist"},
        credential_envelope={"algorithm": "v1", "ciphertext": "sealed-secret"},
        credential_key_id="key-a",
        provider_runtime={"owner_open_id": "ou-owner"},
        generation=ChannelGeneration(
            provider_identity_fingerprint="fp-a",
            provider_identity_revision=1,
            channel_revision=channel_revision,
            credential_revision=1,
        ),
    )


def _manifest(
    *,
    revision: int,
    channels: tuple[ManagedChannelSpec, ...],
    removals: tuple[ChannelRemovalIntent, ...] = (),
) -> ChannelManifest:
    return ChannelManifest(
        owner_id="owner-a",
        node_id="node-a",
        manifest_revision=revision,
        channels=channels,
        removals=removals,
    )


def test_manifest_cache_is_atomic_secret_free_and_node_key_scoped(
    tmp_path: Path,
) -> None:
    """The durable cache stores only envelopes and rejects another node or key."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")

    store.commit_manifest(_manifest(revision=7, channels=(_spec(),)))

    serialized = path.read_text(encoding="utf-8")
    assert "plaintext-must-not-persist" not in serialized
    assert "sealed-secret" in serialized
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    loaded = store.load_manifest()
    assert loaded is not None
    assert loaded.manifest_revision == 7
    assert loaded.channels[0].credential_envelope["ciphertext"] == "sealed-secret"
    assert not list(tmp_path.glob("*.tmp"))

    with pytest.raises(ChannelManifestStoreError, match="node_id mismatch"):
        ChannelManifestStore(path, node_id="node-b", key_id="key-a").load_manifest()
    with pytest.raises(ChannelManifestStoreError, match="key_id mismatch"):
        ChannelManifestStore(path, node_id="node-a", key_id="key-b").load_manifest()


def test_removal_outcome_survives_new_revision_until_per_token_terminal_ack(
    tmp_path: Path,
) -> None:
    """A lost removal ACK cannot be overwritten by an unrelated newer head result."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    store.commit_manifest(_manifest(revision=4, channels=()))
    store.record_reconcile_result(
        manifest_revision=4,
        outcome="applied",
        applied_channel_ids=(),
        removal_outcomes=(
            {
                "removal_token": "rm-token-a",
                "channel_id": "ch-a",
                "outcome": "already_absent",
            },
        ),
        failures=(),
    )
    store.record_reconcile_result(
        manifest_revision=5,
        outcome="applied",
        applied_channel_ids=("ch-b",),
        removal_outcomes=(),
        failures=(),
    )

    pending = ChannelManifestStore(
        path, node_id="node-a", key_id="key-a"
    ).pending_reconcile_result()
    assert pending is not None
    assert pending["manifest_revision"] == 5
    assert pending["removal_outcomes"] == [
        {
            "removal_token": "rm-token-a",
            "channel_id": "ch-a",
            "outcome": "already_absent",
        }
    ]

    store.ack_reconcile_result(
        head_outcome="accepted",
        removal_token_outcomes=[],
    )
    assert store.pending_reconcile_result()["removal_outcomes"]
    store.ack_reconcile_result(
        head_outcome="already_applied",
        removal_token_outcomes=[
            {"removal_token": "rm-token-a", "outcome": "already_applied_by_head"}
        ],
    )
    assert store.pending_reconcile_result() is None


def test_same_revision_retries_failed_stop_and_only_then_commits_empty_cache(
    tmp_path: Path,
) -> None:
    """A failed stop remains visible and retryable without inventing a revision."""
    events: list[str] = []
    adapters: list[_Adapter] = []

    def factory(spec, _binder, _status_handler):
        adapter = _Adapter(
            f"feishu:{spec.agent_id}",
            events,
            fail_stop_once=not adapters,
        )
        adapters.append(adapter)
        return adapter

    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id="key-a",
    )
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=lambda _status: None,
        manifest_store=store,
    )
    asyncio.run(manager.reconcile(_manifest(revision=1, channels=(_spec(),))))
    removal = ChannelRemovalIntent(
        removal_token="rm-token-a",
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        deletion_manifest_revision=2,
    )

    failed = asyncio.run(
        manager.reconcile(_manifest(revision=2, channels=(), removals=(removal,)))
    )
    assert failed.outcome == "retryable_failed"
    assert failed.removal_outcomes[0].outcome == "failed"
    assert failed.removal_outcomes[0].error_code == "runtime_stop_failed"
    assert store.load_manifest().manifest_revision == 1

    applied = asyncio.run(
        manager.reconcile(_manifest(revision=2, channels=(), removals=(removal,)))
    )
    assert applied.outcome == "applied"
    assert applied.removal_outcomes[0].outcome == "applied"
    assert store.load_manifest().manifest_revision == 2
    assert events == [
        "start:feishu:agent-a",
        "stop:feishu:agent-a",
        "stop:feishu:agent-a",
    ]


def test_cache_commit_failure_is_visible_and_same_revision_can_retry(
    tmp_path: Path,
) -> None:
    """Stopping a runtime is not removal success until the empty cache is durable."""

    class FailingCommitStore(ChannelManifestStore):
        fail_next_commit = False

        def commit_manifest(self, manifest: ChannelManifest) -> None:
            if self.fail_next_commit:
                self.fail_next_commit = False
                raise ChannelManifestStoreError("disk is full")
            super().commit_manifest(manifest)

    events: list[str] = []
    store = FailingCommitStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id="key-a",
    )
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda spec, _binder, _status: _Adapter(
                f"feishu:{spec.agent_id}", events
            )
        },
        status_sink=lambda _status: None,
        manifest_store=store,
    )
    asyncio.run(manager.reconcile(_manifest(revision=1, channels=(_spec(),))))
    store.fail_next_commit = True
    removal = ChannelRemovalIntent(
        removal_token="rm-cache-failure",
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        deletion_manifest_revision=2,
    )

    failed = asyncio.run(
        manager.reconcile(_manifest(revision=2, channels=(), removals=(removal,)))
    )
    assert failed.outcome == "retryable_failed"
    assert failed.removal_outcomes[0].error_code == "cache_commit_failed"
    assert store.load_manifest().manifest_revision == 1

    retried = asyncio.run(
        manager.reconcile(_manifest(revision=2, channels=(), removals=(removal,)))
    )
    assert retried.outcome == "applied"
    assert retried.removal_outcomes[0].outcome == "applied"
    assert store.load_manifest().manifest_revision == 2


def test_cached_start_opens_envelope_without_im_and_explicit_absence_is_terminal(
    tmp_path: Path,
) -> None:
    """Gateway starts cached enabled channels and confirms never-seen removals."""
    path = tmp_path / "channel-manifest-v1.json"
    writer = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    writer.commit_manifest(_manifest(revision=3, channels=(_spec(),)))
    events: list[str] = []
    opened: list[str] = []

    def opener(spec):
        opened.append(str(spec.credential_envelope["ciphertext"]))
        return {"app_secret": "opened-at-runtime"}

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda spec, _binder, _status: _Adapter(
                f"feishu:{spec.agent_id}", events
            )
        },
        status_sink=lambda _status: None,
        manifest_store=ChannelManifestStore(
            path, node_id="node-a", key_id="key-a"
        ),
        credential_opener=opener,
    )

    snapshots = asyncio.run(manager.start_cached())

    assert opened == ["sealed-secret"]
    assert len(snapshots) == 1
    assert events == ["start:feishu:agent-a"]

    fresh_store = ChannelManifestStore(
        tmp_path / "fresh-cache.json", node_id="node-a", key_id="key-a"
    )
    fresh_manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={},
        status_sink=lambda _status: None,
        manifest_store=fresh_store,
    )
    removal = ChannelRemovalIntent(
        removal_token="rm-never-seen",
        channel_id="ch-never-seen",
        agent_id="agent-a",
        provider="feishu",
        deletion_manifest_revision=1,
    )
    report = asyncio.run(
        fresh_manager.reconcile(
            _manifest(revision=1, channels=(), removals=(removal,))
        )
    )
    assert report.removal_outcomes[0].outcome == "already_absent"
