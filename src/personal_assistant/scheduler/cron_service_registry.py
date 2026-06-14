"""Per-agent CronExecutionService registry + lifecycle (refactor-406 决策 9).

Replaces ``GatewayCronDispatcher``: after the cron tool became a closure that
holds the per-agent service map directly (build_pa_kernel → make_cron_tool), the
Gateway no longer needs a ``HostCapabilityDispatcher`` to route cron enqueue back
into the kernel. This registry keeps only the parts the Gateway still needs:

- the mutable agent_id → CronExecutionService map (shared by reference with the
  cron tool closure so services registered after kernel-build are visible);
- registration (startup + dynamic on_agent_created);
- gateway-loop injection so worker-thread enqueues schedule on the right loop;
- drain-all on shutdown so in-flight cron executions complete before teardown.

It is **not** a HostCapabilityDispatcher and has no ``invoke`` — cron routing now
lives entirely in the cron tool closure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.scheduler.cron_execution_service import CronExecutionService


class CronServiceRegistry:
    """Hold and manage the Gateway's per-agent CronExecutionService instances.

    Args:
        services: Optional initial agent_id → CronExecutionService map. The
            registry shares this dict by reference with the cron tool closure
            (``make_cron_tool(registry.services)``) so late registrations are
            visible to the already-built tool.
    """

    def __init__(
        self,
        *,
        services: dict[str, CronExecutionService] | None = None,
    ) -> None:
        self._services: dict[str, CronExecutionService] = (
            services if services is not None else {}
        )

    @property
    def services(self) -> dict[str, CronExecutionService]:
        """The live agent_id → CronExecutionService map (shared by reference)."""
        return self._services

    def register(self, agent_id: str, service: CronExecutionService) -> None:
        """Register a CronExecutionService for ``agent_id`` (startup + dynamic)."""
        self._services[agent_id] = service

    def resolve(self, agent_id: str) -> CronExecutionService | None:
        """Return the CronExecutionService for ``agent_id``, or None."""
        return self._services.get(agent_id)

    def resolve_by_workspace(self, workspace_root: str) -> CronExecutionService | None:
        """Resolve by workspace_root via linear scan (path-normalised compare)."""
        resolved = str(Path(workspace_root).expanduser().resolve())
        for service in self._services.values():
            if str(service._workspace_root) == resolved:  # noqa: SLF001
                return service
        return None

    def set_gateway_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Inject the Gateway asyncio loop into all registered services.

        Called once the loop is running so enqueue() from worker threads
        (asyncio.to_thread) can schedule execute_fn on the correct loop.
        """
        for service in self._services.values():
            service._gateway_loop = loop  # noqa: SLF001

    async def drain_all(self, timeout: float = 30.0) -> None:
        """Drain pending execute_fn tasks across all services in parallel.

        Called on shutdown (after kernel.aclose(), before IM teardown) so
        in-flight cron executions (stream consume + IM delivery) complete. All
        services share one wall-clock timeout via asyncio.gather.
        """
        seen_ids: set[int] = set()
        drain_coros = []
        for service in self._services.values():
            svc_id = id(service)
            if svc_id in seen_ids:
                continue
            seen_ids.add(svc_id)
            drain_coros.append(service.drain(timeout=timeout))
        if drain_coros:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*drain_coros, return_exceptions=True),
                    timeout=timeout,
                )
            except (asyncio.TimeoutError, TimeoutError):
                pass
