"""Own Gateway-specific CronExecutionService construction and polling policy."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from personal_assistant.config.local_store import WORKSPACE_CONFIG_DIRNAME
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.scheduler.cron_execution_service import (
    CronExecutionService,
    CronRunTerminalConsumer,
)
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_scheduler import (
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)
from personal_assistant.scheduler.cron_service_registry import CronServiceRegistry

_log = logging.getLogger("personal_assistant.scheduler.cron_gateway_runtime")


class GatewayCronRuntime:
    """Own Cron service registration, restart recovery, and scheduled polling.

    Args:
        registry: Shared service registry exposed to the cron tool closure.
        agent_catalog: Live agent settings used for dynamic registration and polling.
        kernel: In-process Kernel used by terminal run consumption.
        kernel_client: Gateway Kernel adapter used by CronRunner.
        session_binder: Canonical session binding owner.
        canonical_session_store: Live direct-session mapping for cron runs.
        owner_user_id: Optional IM owner receiving terminal delivery.
        run_context_store: Shared delivery context owner.
        kernel_event_observer: Optional runtime delivery observer.
    """

    def __init__(
        self,
        *,
        registry: CronServiceRegistry,
        agent_catalog: LiveAgentCatalog,
        kernel: Any,
        kernel_client: Any,
        session_binder: GatewaySessionBinder,
        canonical_session_store: dict[str, str],
        owner_user_id: str,
        run_context_store: RunDeliveryContextStore,
        kernel_event_observer_provider: Callable[[], Any | None],
    ) -> None:
        self._registry = registry
        self._agent_catalog = agent_catalog
        self._kernel = kernel
        self._kernel_client = kernel_client
        self._session_binder = session_binder
        self._canonical_session_store = canonical_session_store
        self._owner_user_id = owner_user_id
        self._run_context_store = run_context_store
        self._kernel_event_observer_provider = kernel_event_observer_provider

    def register_agent(
        self,
        agent_id: str,
        workspace_root: Path,
        *,
        gateway_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Register one agent's CronExecutionService and recover stale accepted runs."""
        if self._registry.resolve(agent_id) is not None:
            return
        service = CronExecutionService(
            agent_id=agent_id,
            workspace_root=workspace_root,
            runner=CronRunner(
                agent_id=agent_id,
                workspace_root=workspace_root,
                kernel_client=self._kernel_client,
                session_binder=self._session_binder,
                canonical_session_id_provider=lambda: self._canonical_session_store.get(
                    agent_id
                ),
            ),
            terminal_consumer=CronRunTerminalConsumer(
                kernel=self._kernel,
                owner_user_id=self._owner_user_id,
                run_context_store=self._run_context_store,
                observer=(
                    self._kernel_event_observer_provider()
                    if self._owner_user_id
                    else None
                ),
            ),
            gateway_loop=gateway_loop,
        )
        self._registry.register(agent_id, service)
        service.converge_stale_on_restart()

    def register_configured_agents(self) -> None:
        """Register each agent present in the initial Gateway configuration."""
        for snapshot in self._agent_catalog.values_snapshot():
            self.register_agent(
                snapshot.agent_id,
                Path(snapshot.config.workspace_root).expanduser().resolve(),
            )

    def on_agent_created(self, agent_id: str, workspace_root: Path) -> None:
        """Register a dynamically synchronized agent on the active Gateway loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        self.register_agent(agent_id, workspace_root, gateway_loop=loop)

    async def tick_agent(self, agent_id: str) -> None:
        """Evaluate due jobs and enqueue them through the registered service."""
        agent_snapshot = self._agent_catalog.get(agent_id)
        if agent_snapshot is None or not agent_snapshot.config.cron_enabled:
            return
        service = self._registry.resolve(agent_id)
        if service is None:
            _log.warning(
                "cron tick: no CronExecutionService for agent=%s; skipping", agent_id
            )
            return
        workspace_root = (
            Path(agent_snapshot.config.workspace_root).expanduser().resolve()
        )

        async def enqueue(*, agent_id: str, job: object) -> None:
            job_id = getattr(job, "id", None)
            if job_id:
                service.enqueue(job_id=job_id, trigger="scheduled")

        scheduler = CronScheduler(
            agent_id=agent_id,
            job_store=CronJobStore(workspace_root=workspace_root),
            state_store=CronSchedulerStateStore(
                state_path=workspace_root
                / WORKSPACE_CONFIG_DIRNAME
                / "cron"
                / "state.json"
            ),
            submit_fn=enqueue,
        )
        await scheduler.tick()
