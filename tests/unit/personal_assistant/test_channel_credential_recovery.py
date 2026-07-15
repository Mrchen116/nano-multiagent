"""Credential-envelope and cache-key recovery regressions."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.gateway.channel_manifest_apply import (
    CredentialEnvelopeContext,
    apply_channel_manifest_payload,
)
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    def __init__(self, events: list[str]) -> None:
        self.name = "feishu:agent-a"
        self._events = events

    def start(self, _handler) -> None:
        self._events.append("start")

    def stop(self) -> None:
        self._events.append("stop")


def _generation(revision: int) -> ChannelGeneration:
    return ChannelGeneration(
        provider_identity_fingerprint="fp-a",
        provider_identity_revision=1,
        channel_revision=revision,
        credential_revision=revision,
    )


def _spec(*, revision: int, key_id: str) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        credentials={"app_secret": "opened"},
        provider_runtime={},
        generation=_generation(revision),
        credential_envelope={"ciphertext": f"sealed-{revision}"},
        credential_key_id=key_id,
    )


def _manifest(*, revision: int, key_id: str) -> ChannelManifest:
    return ChannelManifest(
        owner_id="owner-a",
        node_id="node-a",
        manifest_revision=revision,
        channels=(_spec(revision=revision, key_id=key_id),),
    )


def test_cache_key_loss_quarantines_ciphertext_and_allows_gateway_start(
    tmp_path: Path,
) -> None:
    """A foreign key cache is retained as evidence and becomes a recovery status."""
    path = tmp_path / "channel-manifest-v1.json"
    writer = ChannelManifestStore(path, node_id="node-a", key_id="key-old")
    writer.commit_manifest(_manifest(revision=3, key_id="key-old"))
    original_bytes = path.read_bytes()
    statuses = []
    events: list[str] = []
    reader = ChannelManifestStore(path, node_id="node-a", key_id="key-new")
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda _spec, _binder, _status: _Adapter(events)
        },
        status_sink=statuses.append,
        manifest_store=reader,
        credential_opener=lambda _item: (_ for _ in ()).throw(
            AssertionError("foreign credentials must not be opened")
        ),
    )

    snapshots = asyncio.run(manager.start_cached())

    assert events == []
    assert snapshots[-1].connection_state == "failed"
    assert snapshots[-1].status_code == "credential_reentry_required"
    quarantined = list(tmp_path.glob("channel-manifest-v1.json.credential-reentry.*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == original_bytes
    assert reader.load_manifest() is None


def test_one_bad_envelope_rejects_complete_manifest_without_stopping_safe_runtime(
    tmp_path: Path,
) -> None:
    """A partial decode never turns an omitted desired item into a deletion."""
    path = tmp_path / "channel-manifest-v1.json"
    store = ChannelManifestStore(path, node_id="node-a", key_id="key-a")
    events: list[str] = []
    statuses = []
    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda _spec, _binder, _status: _Adapter(events)
        },
        status_sink=statuses.append,
        manifest_store=store,
    )
    initial = asyncio.run(manager.reconcile(_manifest(revision=1, key_id="key-a")))
    assert initial.outcome == "applied"
    body = {
        "owner_id": "owner-a",
        "node_id": "node-a",
        "manifest_revision": 2,
        "channels": [
            {
                "channel_id": "ch-a",
                "agent_id": "agent-a",
                "provider": "feishu",
                "enabled": True,
                "config": {"app_id": "cli_changed"},
                "provider_runtime": {},
                "credential_envelope": {"ciphertext": "wrong-key"},
                "credential_key_id": "key-foreign",
                "provider_identity_fingerprint": "fp-a",
                "provider_identity_revision": 1,
                "channel_revision": 2,
                "credential_revision": 2,
            }
        ],
        "removals": [],
    }

    def opener(_context: CredentialEnvelopeContext):
        raise AssertionError("key mismatch must fail before decrypt")

    result = asyncio.run(
        apply_channel_manifest_payload(
            body=body,
            node_id="node-a",
            credential_key_id="key-a",
            credential_opener=opener,
            manager=manager,
        )
    )

    assert result["outcome"] == "retryable_failed"
    assert result["failures"] == [
        {
            "channel_id": "ch-a",
            "error_code": "credential_reentry_required",
            "error_message": "Channel credentials must be entered again.",
        }
    ]
    assert events == ["start"]
    cached = store.load_manifest()
    assert cached is not None and cached.manifest_revision == 1
    assert store.last_applied_manifest_revision == 1
    assert statuses[-1].generation == _generation(2)
    assert statuses[-1].status_code == "credential_reentry_required"

