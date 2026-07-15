"""Runtime quarantine tests for terminal channel-status acknowledgements."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from personal_assistant.channels.base import InboundHandler, OutboundMessage
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    name = "feishu:agent-a"

    def __init__(self) -> None:
        self.stopped = 0

    def start(self, _on_inbound: InboundHandler) -> None:
        pass

    def stop(self) -> None:
        self.stopped += 1

    def send(self, _outbound: OutboundMessage) -> None:
        pass


def _spec(revision: int = 1) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        credentials={"app_secret": "secret"},
        provider_runtime={},
        generation=ChannelGeneration(
            provider_identity_fingerprint="fp-a",
            provider_identity_revision=1,
            channel_revision=revision,
            credential_revision=1,
        ),
    )


def test_removed_ack_quarantines_only_the_matching_cached_generation() -> None:
    """A delayed terminal ACK cannot stop a newer replacement incarnation."""
    adapters: list[_Adapter] = []

    def factory(_spec, _binder, _status_handler):
        adapter = _Adapter()
        adapters.append(adapter)
        return adapter

    registry = ChannelRegistry()
    manager = ChannelManager(
        registry=registry,
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=lambda _snapshot: None,
    )
    first = _spec()
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(first,)))
    )
    second = replace(first, generation=replace(first.generation, channel_revision=2))
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=2, channels=(second,)))
    )

    asyncio.run(
        manager.handle_status_result(
            channel_id="ch-a",
            channel_revision=1,
            outcome="terminal_channel_removed",
        )
    )
    assert registry.get("feishu:agent-a") is adapters[1]

    asyncio.run(
        manager.handle_status_result(
            channel_id="ch-a",
            channel_revision=2,
            outcome="terminal_channel_removed",
        )
    )
    assert registry.get("feishu:agent-a") is None
    assert adapters[1].stopped == 1


def test_fatal_owner_mismatch_quarantines_every_managed_runtime() -> None:
    """Ownership drift fails closed across the node's managed channel set."""
    adapters: list[_Adapter] = []

    def factory(_spec, _binder, _status_handler):
        adapter = _Adapter()
        adapters.append(adapter)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=lambda _snapshot: None,
    )
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(_spec(),)))
    )

    asyncio.run(
        manager.handle_status_result(
            channel_id="ch-a",
            channel_revision=1,
            outcome="fatal_owner_mismatch",
        )
    )
    assert adapters[0].stopped == 1

