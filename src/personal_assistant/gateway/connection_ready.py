"""Coordinate Gateway convergence after IM accepts node registration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.boundary_outbox import BoundaryOutboxDispatcher
from personal_assistant.gateway.im_bootstrap import (
    GatewayStartupError,
    IMBootstrapClient,
    emit_gateway_feedback,
)
from personal_assistant.gateway.managed_channel_control import (
    ManagedChannelBindings,
    ManagedChannelConnectionSender,
)
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

_log = logging.getLogger("personal_assistant.gateway.connection_ready")


class ConnectionReadyCoordinator:
    """Apply post-register convergence in the established cross-owner order.

    The connection sender is supplied by ``IMConnectionManager`` only after its
    registration ACK. This avoids capturing a manager before composition completes.

    Args:
        node_id: Registered Gateway node identity.
        bootstrap_client: Owner of IM HTTP node binding.
        reporter: Reporter that produces a degraded heartbeat on binding failure.
        managed_channel_bindings: Managed-channel register-ready operations.
        sync_client: Snapshot source for locally observed profile versions.
        agent_config_sync: Owner of live Agent profile reconciliation.
        agent_ids: Configured Agent identities to reconcile.
        boundary_outbox: Durable configuration-boundary delivery owner.
        recover_external_shadows: Replays external anchors pending from a prior process.
    """

    def __init__(
        self,
        *,
        node_id: str,
        bootstrap_client: IMBootstrapClient,
        reporter: UpstreamReporter,
        managed_channel_bindings: ManagedChannelBindings,
        sync_client: ConfigSyncClient,
        agent_config_sync: IMAgentConfigSync,
        agent_ids: Iterable[str],
        boundary_outbox: BoundaryOutboxDispatcher,
        recover_external_shadows: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._node_id = node_id
        self._bootstrap_client = bootstrap_client
        self._reporter = reporter
        self._managed_channel_bindings = managed_channel_bindings
        self._sync_client = sync_client
        self._agent_config_sync = agent_config_sync
        self._agent_ids = tuple(agent_ids)
        self._boundary_outbox = boundary_outbox
        self._recover_external_shadows = recover_external_shadows
        self._shadow_recovery_task: asyncio.Task[None] | None = None

    async def on_connected(self, connection: ManagedChannelConnectionSender) -> None:
        """Converge binding, managed channels, and Agent profiles after registration."""
        try:
            await asyncio.to_thread(
                self._bootstrap_client.ensure_node_binding,
                node_id=self._node_id,
            )
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, GatewayStartupError):
                summary = exc.summary
                next_step = exc.next_step
            else:
                summary = f"node {self._node_id} binding failed: {exc}"
                next_step = None
            heartbeat_last_error = (
                f"{summary}; next step: {next_step}" if next_step else summary
            )
            _log.warning("IM node binding failed during reconnect: %s", summary)
            emit_gateway_feedback("ERROR", summary, next_step)
            try:
                await connection.send_json(
                    "node.heartbeat",
                    self._reporter.send_heartbeat(
                        status="degraded", last_error=heartbeat_last_error
                    ),
                )
            except Exception as heartbeat_exc:  # noqa: BLE001
                _log.warning(
                    "failed to send degraded IM heartbeat after binding failure: %s",
                    heartbeat_exc,
                )
        await self._managed_channel_bindings.reconcile_after_register(connection)
        memory_versions = {
            agent_id: version
            for agent_id in self._agent_ids
            if (version := self._sync_client.latest_profile_version(agent_id))
            is not None
        }
        await asyncio.to_thread(
            self._agent_config_sync.reconcile_all_agents,
            memory_versions=memory_versions,
        )
        # The dispatcher is independent of shadow replay and must start before a
        # slow or failed recovery can delay ordinary boundary delivery.
        self._boundary_outbox.schedule_drain(connection)
        if self._recover_external_shadows is not None:
            if (
                self._shadow_recovery_task is not None
                and not self._shadow_recovery_task.done()
            ):
                self._shadow_recovery_task.cancel()
            self._shadow_recovery_task = asyncio.create_task(
                self._recover_external_shadows_until_success()
            )

    async def _recover_external_shadows_until_success(self) -> None:
        """Replay external shadows off the receive path and retry transient failure."""
        assert self._recover_external_shadows is not None
        while True:
            try:
                await self._recover_external_shadows()
                return
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _log.exception(
                    "external shadow recovery failed; retrying on this connection"
                )
                await asyncio.sleep(1.0)
