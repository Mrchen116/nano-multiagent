"""Recovery regressions for retryable channel manifest commits."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_manifest_store import (
    ChannelManifestStore,
    ChannelManifestStoreError,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self._events = events

    def start(self, _handler) -> None:
        self._events.append(f"start:{self.name}")

    def stop(self) -> None:
        self._events.append(f"stop:{self.name}")


class _FailRevisionTwoOnceStore(ChannelManifestStore):
    fail_revision_two = True

    def commit_manifest(self, manifest: ChannelManifest) -> None:
        if manifest.manifest_revision == 2 and self.fail_revision_two:
            self.fail_revision_two = False
            raise ChannelManifestStoreError("disk is full")
        super().commit_manifest(manifest)


def _spec(*, revision: int, app_id: str) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": app_id},
        credentials={"app_secret": "never-persist"},
        provider_runtime={},
        generation=ChannelGeneration(
            provider_identity_fingerprint=f"fp-{revision}",
            provider_identity_revision=revision,
            channel_revision=revision,
            credential_revision=revision,
        ),
        credential_envelope={"ciphertext": f"sealed-{revision}"},
        credential_key_id="key-a",
    )


def _manifest(*, revision: int, app_id: str) -> ChannelManifest:
    return ChannelManifest(
        owner_id="owner-a",
        node_id="node-a",
        manifest_revision=revision,
        channels=(_spec(revision=revision, app_id=app_id),),
    )


def test_pending_manifest_retries_after_restart_without_rolling_back_runtime(
    tmp_path: Path,
) -> None:
    """Restart prefers the durable retry candidate over the last applied snapshot."""
    path = tmp_path / "channel-manifest-v1.json"
    store = _FailRevisionTwoOnceStore(path, node_id="node-a", key_id="key-a")
    first_events: list[str] = []
    first = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda spec, _binder, _status: _Adapter(
                f"{spec.config['app_id']}", first_events
            )
        },
        status_sink=lambda _status: None,
        manifest_store=store,
    )
    assert asyncio.run(first.reconcile(_manifest(revision=1, app_id="cli_old"))).outcome == "applied"
    failed = asyncio.run(first.reconcile(_manifest(revision=2, app_id="cli_new")))
    assert failed.outcome == "retryable_failed"
    assert store.load_manifest().manifest_revision == 1
    assert store.load_retry_manifest().manifest_revision == 2

    restarted_store = _FailRevisionTwoOnceStore(
        path, node_id="node-a", key_id="key-a"
    )
    restarted_store.fail_revision_two = False
    restarted_events: list[str] = []
    restarted = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={
            "feishu": lambda spec, _binder, _status: _Adapter(
                f"{spec.config['app_id']}", restarted_events
            )
        },
        status_sink=lambda _status: None,
        manifest_store=restarted_store,
        credential_opener=lambda _item: {"app_secret": "opened"},
    )

    asyncio.run(restarted.start_cached())

    assert restarted_events == ["start:cli_new"]
    assert restarted_store.load_manifest().manifest_revision == 2
    assert restarted_store.load_retry_manifest() is None
    assert restarted_store.last_applied_manifest_revision == 2
    assert "never-persist" not in path.read_text(encoding="utf-8")
