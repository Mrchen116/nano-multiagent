"""Gateway-side HostCapabilityDispatcher that routes cron enqueue requests.

bugfix-402 Decision 2: The Gateway provides a HostCapabilityDispatcher so the cron tool's
manual run action reaches the CronExecutionService without any HTTP loopback or direct
import of personal_assistant internals from the kernel.

This module is personal_assistant-internal.  The cron tool in agent.products imports only
agent.sdk types (HostCapabilityDispatcher, HostCapabilityContext); the Gateway constructs
this dispatcher and injects it via build_kernel(host_capabilities=...).

A single GatewayCronDispatcher is wired for the whole kernel and routes each invocation to
the correct per-agent CronExecutionService by agent_id (bugfix-402 round-2: replaces
workspace_root routing which suffered dual-source path mismatch between the IM-synced
AgentWorkspaceConfig.workspace_root and the locally registered CronExecutionService key).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

from agent.sdk import HostCapabilityContext, HostCapabilityDispatcher

from personal_assistant.scheduler.cron_execution_service import CronExecutionService

_ENQUEUE_CAPABILITY = "personal_assistant.cron.enqueue"


class GatewayCronDispatcher(HostCapabilityDispatcher):
    """Dispatch host capability calls to per-agent CronExecutionService instances.

    Routes the "personal_assistant.cron.enqueue" capability to the CronExecutionService
    whose agent_id matches context.agent_id.  All other capability names raise ValueError.

    bugfix-402 round-2: routing key changed from workspace_root to agent_id because
    workspace_root has two data sources (IM-stored vs locally resolved path from YAML),
    which causes lookup misses when IM-synced config writes a different path than what was
    used at CronExecutionService registration time.

    Args:
        services: Mapping of agent_id (str) to CronExecutionService.
            Use register() or construct with a pre-built dict.
    """

    def __init__(
        self,
        *,
        services: Mapping[str, CronExecutionService] | None = None,
        # Convenience single-service constructor used in tests.
        service: CronExecutionService | None = None,
    ) -> None:
        if services is not None and service is not None:
            raise ValueError("Provide either 'services' or 'service', not both")
        if service is not None:
            # Single-service convenience: register under sentinel key and the
            # service's own agent_id so test code needs no workspace routing.
            self._services: dict[str, CronExecutionService] = {
                "_single": service,
                service._agent_id: service,  # noqa: SLF001
            }
            self._single_service = service
        else:
            self._services = dict(services or {})
            self._single_service = None

    def register(self, agent_id: str, service: CronExecutionService) -> None:
        """Register a CronExecutionService for the given agent_id.

        Called by Gateway assembly code once per agent during startup and
        dynamically from the on_agent_created callback.

        Args:
            agent_id: Stable agent identity (matches IM agent_id).
            service: CronExecutionService instance for this agent.
        """
        self._services[agent_id] = service

    def set_gateway_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Inject the Gateway asyncio loop into all registered services.

        Called from GatewayRuntime._run_until_shutdown() once the loop is
        running so enqueue() called from worker threads (asyncio.to_thread)
        can schedule execute_fn on the correct loop.
        """
        for service in self._services.values():
            service._gateway_loop = loop  # noqa: SLF001

    async def drain_all(self, timeout: float = 30.0) -> None:
        """Drain pending execute_fn tasks across all registered services in parallel.

        bugfix-402-M6 W-1: called from GatewayRuntime._run_until_shutdown() after
        kernel.aclose() and before im_connection_manager.close() so that in-flight
        cron executions (stream consume + IM delivery) complete before the IM
        transport is torn down (Decision 7).

        bugfix-402 code-review fix: services are drained with asyncio.gather so all
        agents share the same wall-clock timeout instead of accumulating N×timeout
        for N agents.

        Args:
            timeout: Maximum wall-clock seconds to wait for all services combined.
        """
        seen_ids: set[int] = set()
        drain_coros = []
        for service in self._services.values():
            svc_id = id(service)
            if svc_id in seen_ids:
                # Skip duplicate — single-service mode registers under two keys.
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

    def invoke(
        self,
        capability: str,
        payload: Mapping[str, Any],
        context: HostCapabilityContext,
    ) -> Mapping[str, Any]:
        """Dispatch a host capability call.

        Args:
            capability: Capability name; only "personal_assistant.cron.enqueue" is supported.
            payload: Must contain {"job_id": str} for the enqueue capability.
            context: HostCapabilityContext; agent_id is used to route to the correct
                per-agent CronExecutionService (workspace_root is no longer used for
                routing — it was structurally unreliable due to dual-source path mismatch).

        Returns:
            CronEnqueueAck mapping (accepted, job_id, request_id, error_code).

        Raises:
            ValueError: When capability is not "personal_assistant.cron.enqueue".
        """
        if capability != _ENQUEUE_CAPABILITY:
            raise ValueError(
                f"GatewayCronDispatcher: unsupported capability {capability!r}; "
                f"only {_ENQUEUE_CAPABILITY!r} is supported"
            )

        job_id = payload.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            return {
                "accepted": False,
                "job_id": str(job_id or ""),
                "request_id": None,
                "error_code": "invalid_payload",
            }

        service = self._resolve_service(context.agent_id)
        if service is None:
            return {
                "accepted": False,
                "job_id": job_id,
                "request_id": None,
                "error_code": "cron_unavailable",
            }

        return service.enqueue(job_id=job_id, trigger="manual")

    def _resolve_service(self, agent_id: str) -> CronExecutionService | None:
        """Resolve the CronExecutionService for the given agent_id."""
        if self._single_service is not None:
            # Single-service mode (tests): ignore routing.
            return self._single_service
        return self._services.get(agent_id)

    # ---------------------------------------------------------------------------
    # Legacy workspace_root-based accessor kept for cron tick path compatibility.
    # The tick path (main.py:_cron_tick_for_agent) resolves services by agent_id
    # directly; this method is retained only to avoid breaking any tests that
    # call it by keyword during migration.  Callers should prefer _resolve_service.
    # ---------------------------------------------------------------------------

    def _resolve_service_by_workspace(
        self, workspace_root: str
    ) -> CronExecutionService | None:
        """Resolve by workspace_root across all registered services (linear scan).

        Used as a fallback when agent_id is not available.  Normalises both the
        lookup path and the stored workspace_root values for comparison.
        """
        resolved = str(Path(workspace_root).expanduser().resolve())
        for service in self._services.values():
            if str(service._workspace_root) == resolved:  # noqa: SLF001
                return service
        return None
