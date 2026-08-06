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
        self._node_bootstrap_task: asyncio.Task[None] | None = None
        self._agent_reconcile_task: asyncio.Task[None] | None = None
        self._agent_reconcile_generation = 0
        self._shadow_recovery_task: asyncio.Task[None] | None = None
        self._shadow_recovery_generation = 0

    async def on_connected(self, connection: ManagedChannelConnectionSender) -> None:
        """Converge binding, managed channels, and Agent profiles after registration."""
        self._schedule_node_bootstrap(connection)
        await self._managed_channel_bindings.reconcile_after_register(connection)
        self._schedule_agent_reconcile()
        # The dispatcher is independent of all convergence work and must start before a
        # slow or failed recovery can delay ordinary boundary delivery.
        self._boundary_outbox.schedule_drain(connection)
        self.notify_external_shadows_pending()

    def _schedule_node_bootstrap(
        self, connection: ManagedChannelConnectionSender
    ) -> None:
        if (
            self._node_bootstrap_task is not None
            and not self._node_bootstrap_task.done()
        ):
            return
        self._node_bootstrap_task = asyncio.create_task(
            self._ensure_node_binding(connection),
            name="personal-assistant-node-binding",
        )
        self._node_bootstrap_task.add_done_callback(self._node_bootstrap_done)

    async def _ensure_node_binding(
        self, connection: ManagedChannelConnectionSender
    ) -> None:
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

    def _schedule_agent_reconcile(self) -> None:
        self._agent_reconcile_generation += 1
        if (
            self._agent_reconcile_task is not None
            and not self._agent_reconcile_task.done()
        ):
            return
        self._agent_reconcile_task = asyncio.create_task(
            self._reconcile_agents_until_current(),
            name="personal-assistant-agent-profile-reconcile",
        )
        self._agent_reconcile_task.add_done_callback(self._agent_reconcile_done)

    async def _reconcile_agents_until_current(self) -> None:
        while True:
            generation = self._agent_reconcile_generation
            await asyncio.to_thread(
                self._agent_config_sync.reconcile_all_agents,
                latest_memory_version=self._sync_client.latest_profile_version,
            )
            if generation == self._agent_reconcile_generation:
                return

    @staticmethod
    def _node_bootstrap_done(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            _log.warning("IM node bootstrap failed", exc_info=True)

    @staticmethod
    def _agent_reconcile_done(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            _log.warning("Agent profile reconciliation failed", exc_info=True)

    def notify_external_shadows_pending(self) -> None:
        """Wake the single recovery owner after a new terminal snapshot becomes ready."""

        if self._recover_external_shadows is None:
            return
        self._shadow_recovery_generation += 1
        if self._shadow_recovery_task is None or self._shadow_recovery_task.done():
            self._shadow_recovery_task = asyncio.create_task(
                self._recover_external_shadows_until_success()
            )

    async def _recover_external_shadows_until_success(self) -> None:
        """Replay external shadows off the receive path and retry transient failure."""
        assert self._recover_external_shadows is not None
        while True:
            generation = self._shadow_recovery_generation
            try:
                await self._recover_external_shadows()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _log.exception(
                    "external shadow recovery failed; retrying on this connection"
                )
                await asyncio.sleep(1.0)
                continue
            if generation == self._shadow_recovery_generation:
                return
