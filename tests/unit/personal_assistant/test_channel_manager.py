"""Behavior tests for dynamic external-channel lifecycle ownership."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Callable

from personal_assistant.channels.base import InboundHandler, OutboundMessage
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    FeishuActivationPolicy,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry


class _Adapter:
    def __init__(self, name: str, events: list[str], *, fail_start: bool = False) -> None:
        self.name = name
        self.events = events
        self.fail_start = fail_start
        self.stopped = 0

    def start(self, _on_inbound: InboundHandler) -> None:
        self.events.append(f"start:{self.name}")
        if self.fail_start:
            raise RuntimeError("invalid credentials")

    def stop(self) -> None:
        self.events.append(f"stop:{self.name}")
        self.stopped += 1

    def send(self, _outbound: OutboundMessage) -> None:
        self.events.append(f"send:{self.name}")


def _spec(
    *,
    channel_id: str = "ch-a",
    agent_id: str = "agent-a",
    app_id: str = "cli_a",
    channel_revision: int = 1,
    credential_revision: int = 1,
    identity_revision: int = 1,
    metadata: dict[str, str] | None = None,
) -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id=channel_id,
        agent_id=agent_id,
        provider="feishu",
        enabled=True,
        config={"app_id": app_id},
        credentials={"app_secret": f"secret-{app_id}"},
        provider_runtime=metadata or {},
        generation=ChannelGeneration(
            provider_identity_fingerprint=f"fp-{app_id}",
            provider_identity_revision=identity_revision,
            channel_revision=channel_revision,
            credential_revision=credential_revision,
        ),
    )


def test_reconcile_replaces_runtime_with_stable_name_and_generation_cas() -> None:
    """App replacement stops old traffic before a new stable runtime becomes active."""
    events: list[str] = []
    adapters: list[_Adapter] = []
    binders: list[Callable[[dict[str, str]], dict[str, str] | None]] = []
    statuses = []
    metadata_reports = []
    activated: list[str] = []

    def factory(spec, binder, status_handler):
        del status_handler
        adapter = _Adapter(f"feishu:{spec.agent_id}", events)
        adapters.append(adapter)
        binders.append(binder)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=statuses.append,
        metadata_sink=metadata_reports.append,
        activation_policy=FeishuActivationPolicy(activated.append),
    )
    original = _spec()
    first = asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(original,)))
    )

    assert first.applied_channel_ids == ("ch-a",)
    assert manager.registry.get("feishu:agent-a") is adapters[0]
    assert activated == ["agent-a"]
    assert statuses[0].status_sequence == 1
    assert statuses[0].instance_started is True
    old_incarnation = statuses[0].runtime_incarnation
    assert binders[0]({"owner_open_id": "ou_first"}) == {
        "owner_open_id": "ou_first"
    }
    assert binders[0]({"owner_open_id": "ou_second"}) == {
        "owner_open_id": "ou_first"
    }

    replacement = _spec(
        app_id="cli_b",
        channel_revision=2,
        credential_revision=2,
        identity_revision=2,
    )
    second = asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=2, channels=(replacement,)))
    )

    assert second.applied_channel_ids == ("ch-a",)
    assert events == [
        "start:feishu:agent-a",
        "stop:feishu:agent-a",
        "start:feishu:agent-a",
    ]
    assert adapters[0].stopped == 1
    assert manager.registry.get("feishu:agent-a") is adapters[1]
    assert binders[0]({"bot_open_id": "ou_old_bot"}) is None
    assert binders[1]({"owner_open_id": "ou_new_owner"}) == {
        "owner_open_id": "ou_new_owner"
    }
    assert metadata_reports[-1].generation == replacement.generation
    new_barrier = statuses[1]
    assert new_barrier.runtime_incarnation != old_incarnation
    assert new_barrier.status_sequence == 1
    assert manager.accept_status(
        channel_id="ch-a",
        generation=original.generation,
        runtime_incarnation=old_incarnation,
        status_sequence=99,
        connection_state="connected",
    ) is False
    assert manager.accept_status(
        channel_id="ch-a",
        generation=replacement.generation,
        runtime_incarnation=new_barrier.runtime_incarnation,
        status_sequence=2,
        connection_state="connected",
    ) is True
    assert manager.accept_status(
        channel_id="ch-a",
        generation=replacement.generation,
        runtime_incarnation=new_barrier.runtime_incarnation,
        status_sequence=1,
        connection_state="failed",
    ) is False


def test_replacement_start_failure_cuts_old_send_path_and_surfaces_failure() -> None:
    """A rejected replacement never leaves the superseded credential listener routable."""
    events: list[str] = []
    adapters: list[_Adapter] = []
    calls = 0
    statuses = []

    def factory(spec, _binder, _status_handler):
        nonlocal calls
        calls += 1
        adapter = _Adapter(
            f"feishu:{spec.agent_id}", events, fail_start=calls == 2
        )
        adapters.append(adapter)
        return adapter

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=statuses.append,
    )
    original = _spec()
    asyncio.run(
        manager.reconcile(ChannelManifest(manifest_revision=1, channels=(original,)))
    )
    failed = asyncio.run(
        manager.reconcile(
            ChannelManifest(
                manifest_revision=2,
                channels=(
                    replace(
                        original,
                        credentials={"app_secret": "replacement"},
                        generation=replace(
                            original.generation,
                            channel_revision=2,
                            credential_revision=2,
                        ),
                    ),
                ),
            )
        )
    )

    assert failed.failed_channel_ids == ("ch-a",)
    assert manager.registry.get("feishu:agent-a") is None
    assert events[-3:] == [
        "stop:feishu:agent-a",
        "start:feishu:agent-a",
        "stop:feishu:agent-a",
    ]
    assert adapters[1].stopped == 1
    assert statuses[-1].connection_state == "failed"
    assert statuses[-1].status_code == "runtime_start_failed"


def test_active_status_forwards_structured_diagnostic_checks() -> None:
    """Provider diagnostics remain attached to the monotonic runtime status."""
    statuses = []
    status_handlers = []

    def factory(spec, _binder, status_handler):
        status_handlers.append(status_handler)
        return _Adapter(f"feishu:{spec.agent_id}", [])

    manager = ChannelManager(
        registry=ChannelRegistry(),
        on_inbound=lambda _message: None,
        provider_factories={"feishu": factory},
        status_sink=statuses.append,
    )
    asyncio.run(
        manager.reconcile(
            ChannelManifest(manifest_revision=1, channels=(_spec(),))
        )
    )

    assert status_handlers[0](
        status_sequence=2,
        connection_state="connected",
        diagnostics_state="limited",
        checks=(
            {
                "check_id": "feishu.receive_group_message",
                "state": "missing",
                "required": {
                    "accepted_scope_sets": [["im:message.group_msg"]],
                    "recommended_scopes": ["im:message.group_msg"],
                },
                "effect": "Group background context is incomplete.",
                "remediation": "Grant the recommended scope and publish the app.",
            },
        ),
    ) is True
    assert statuses[-1].diagnostics_state == "limited"
    assert statuses[-1].checks[0]["check_id"] == (
        "feishu.receive_group_message"
    )


def test_activation_policy_adds_feishu_doc_once_for_explicit_allowlist() -> None:
    """Legacy and managed Feishu activation share one idempotent skill policy."""
    skills = {"agent-a": ["planning"], "agent-open": []}
    saved: list[tuple[str, tuple[str, ...]]] = []

    policy = FeishuActivationPolicy(
        lambda agent_id: None,
        load_skills=lambda agent_id: tuple(skills[agent_id]),
        save_skills=lambda agent_id, value: (
            skills.__setitem__(agent_id, list(value)),
            saved.append((agent_id, tuple(value))),
        ),
    )
    policy.ensure("agent-a")
    policy.ensure("agent-a")
    policy.ensure("agent-open")

    assert skills["agent-a"] == ["planning", "feishu-doc"]
    assert skills["agent-open"] == []
    assert saved == [("agent-a", ("planning", "feishu-doc"))]
