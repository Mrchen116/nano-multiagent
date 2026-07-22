"""Connection-ready recovery must not stall durable boundary delivery."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.connection_ready import ConnectionReadyCoordinator


class _Bootstrap:
    def ensure_node_binding(self, *, node_id: str) -> None:
        assert node_id == "node-1"


class _ManagedChannels:
    async def reconcile_after_register(self, _connection: object) -> None:
        return None


class _SyncClient:
    def latest_profile_version(self, _agent_id: str) -> None:
        return None


class _AgentConfigSync:
    def reconcile_all_agents(self, *, memory_versions: dict[str, int]) -> None:
        assert memory_versions == {}


class _Reporter:
    def send_heartbeat(self, **_kwargs: object) -> dict[str, object]:
        return {}


class _Outbox:
    def __init__(self) -> None:
        self.connections: list[object] = []

    def schedule_drain(self, connection: object) -> None:
        self.connections.append(connection)


@pytest.mark.asyncio
async def test_slow_shadow_recovery_does_not_delay_outbox_schedule() -> None:
    """The receive path remains free while recovery runs behind the connection."""
    started = asyncio.Event()
    release = asyncio.Event()
    outbox = _Outbox()

    async def recover() -> None:
        started.set()
        await release.wait()

    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_Bootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_AgentConfigSync(),
        agent_ids=[],
        boundary_outbox=outbox,
        recover_external_shadows=recover,
    )
    connection = object()

    await asyncio.wait_for(coordinator.on_connected(connection), timeout=0.1)
    assert outbox.connections == [connection]
    await asyncio.wait_for(started.wait(), timeout=0.1)
    release.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_failed_shadow_recovery_retries_without_rescheduling_outbox() -> None:
    """A transient recovery error retries on the existing registered connection."""
    attempts = 0
    recovered = asyncio.Event()
    outbox = _Outbox()

    async def recover() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("IM temporarily unavailable")
        recovered.set()

    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_Bootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_AgentConfigSync(),
        agent_ids=[],
        boundary_outbox=outbox,
        recover_external_shadows=recover,
    )
    connection = object()

    await coordinator.on_connected(connection)
    assert outbox.connections == [connection]
    await asyncio.wait_for(recovered.wait(), timeout=1.2)
    assert attempts == 2
    assert outbox.connections == [connection]
