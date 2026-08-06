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
    def reconcile_all_agents(self, *, latest_memory_version: object) -> None:
        assert latest_memory_version is not None


class _Reporter:
    def send_heartbeat(self, **_kwargs: object) -> dict[str, object]:
        return {}


class _Outbox:
    def __init__(self) -> None:
        self.connections: list[object] = []

    def schedule_drain(self, connection: object) -> None:
        self.connections.append(connection)


@pytest.mark.asyncio
async def test_slow_agent_reconcile_does_not_block_receive_path() -> None:
    """A slow IM profile read must not delay relay delivery after registration."""
    started = asyncio.Event()
    release = asyncio.Event()

    class _SlowAgentConfigSync:
        def reconcile_all_agents(self, *, latest_memory_version: object) -> None:
            assert latest_memory_version is not None
            loop.call_soon_threadsafe(started.set)
            asyncio.run_coroutine_threadsafe(release.wait(), loop).result()

    loop = asyncio.get_running_loop()
    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_Bootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_SlowAgentConfigSync(),
        agent_ids=[],
        boundary_outbox=_Outbox(),
    )

    await asyncio.wait_for(coordinator.on_connected(object()), timeout=0.1)
    await asyncio.wait_for(started.wait(), timeout=0.1)
    release.set()
    assert coordinator._agent_reconcile_task is not None  # noqa: SLF001
    await coordinator._agent_reconcile_task  # noqa: SLF001


@pytest.mark.asyncio
async def test_slow_node_bootstrap_does_not_block_receive_path() -> None:
    """Node binding HTTP work must not hold the registered WebSocket receive owner."""

    started = asyncio.Event()
    release = asyncio.Event()
    outbox = _Outbox()

    class _SlowBootstrap:
        def ensure_node_binding(self, *, node_id: str) -> None:
            assert node_id == "node-1"
            loop.call_soon_threadsafe(started.set)
            asyncio.run_coroutine_threadsafe(release.wait(), loop).result()

    loop = asyncio.get_running_loop()
    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_SlowBootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_AgentConfigSync(),
        agent_ids=[],
        boundary_outbox=outbox,
    )
    connection = object()

    await asyncio.wait_for(coordinator.on_connected(connection), timeout=0.1)
    assert outbox.connections == [connection]
    await asyncio.wait_for(started.wait(), timeout=0.1)
    release.set()
    assert coordinator._node_bootstrap_task is not None  # noqa: SLF001
    await coordinator._node_bootstrap_task  # noqa: SLF001


@pytest.mark.asyncio
async def test_reconnect_coalesces_profile_reconcile_without_losing_latest_pass() -> (
    None
):
    """An overlapping reconnect requests one follow-up reconcile, not a stale writer."""

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class _SlowAgentConfigSync:
        def reconcile_all_agents(self, *, latest_memory_version: object) -> None:
            nonlocal calls
            assert latest_memory_version is not None
            calls += 1
            if calls == 1:
                loop.call_soon_threadsafe(started.set)
                asyncio.run_coroutine_threadsafe(release.wait(), loop).result()

    loop = asyncio.get_running_loop()
    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_Bootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_SlowAgentConfigSync(),
        agent_ids=[],
        boundary_outbox=_Outbox(),
    )

    await coordinator.on_connected(object())
    await asyncio.wait_for(started.wait(), timeout=0.1)
    original_task = coordinator._agent_reconcile_task  # noqa: SLF001
    await coordinator.on_connected(object())
    assert coordinator._agent_reconcile_task is original_task  # noqa: SLF001
    release.set()
    assert original_task is not None
    await original_task
    assert calls == 2


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


@pytest.mark.asyncio
async def test_new_ready_snapshot_wakes_recovery_without_websocket_reconnect() -> None:
    """A later terminal snapshot is retried by the existing single recovery owner."""

    attempts = 0
    second_recovery = asyncio.Event()

    async def recover() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("first snapshot PUT failed")
        if attempts == 3:
            second_recovery.set()

    coordinator = ConnectionReadyCoordinator(
        node_id="node-1",
        bootstrap_client=_Bootstrap(),
        reporter=_Reporter(),
        managed_channel_bindings=_ManagedChannels(),
        sync_client=_SyncClient(),
        agent_config_sync=_AgentConfigSync(),
        agent_ids=[],
        boundary_outbox=_Outbox(),
        recover_external_shadows=recover,
    )

    await coordinator.on_connected(object())
    await asyncio.sleep(0)
    assert attempts == 1

    coordinator.notify_external_shadows_pending()

    await asyncio.wait_for(second_recovery.wait(), timeout=1.2)
    assert attempts == 3
