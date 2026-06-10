"""Gateway-side HostCapabilityDispatcher that routes cron enqueue requests.

bugfix-402 Decision 2: The Gateway provides a HostCapabilityDispatcher so the cron tool's
manual run action reaches the CronExecutionService without any HTTP loopback or direct
import of personal_assistant internals from the kernel.

This module is personal_assistant-internal.  The cron tool in agent.products imports only
agent.sdk types (HostCapabilityDispatcher, HostCapabilityContext); the Gateway constructs
this dispatcher and injects it via build_kernel(host_capabilities=...).

A single GatewayCronDispatcher is wired for the whole kernel and routes each invocation to
the correct per-agent CronExecutionService by workspace_root, since HostCapabilityContext
carries the agent's workspace_root at call time.
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
    whose workspace_root matches the context's workspace_root.  All other capability names
    raise ValueError.

    Args:
        services: Mapping of resolved workspace_root (str) to CronExecutionService.
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
            # Single-service convenience: register under a sentinel key so
            # test code can use GatewayCronDispatcher(service=svc) without workspace matching.
            self._services: dict[str, CronExecutionService] = {
                "_single": service,
                str(service._workspace_root): service,  # noqa: SLF001
            }
            self._single_service = service
        else:
            self._services = dict(services or {})
            self._single_service = None

    def register(self, workspace_root: Path, service: CronExecutionService) -> None:
        """Register a CronExecutionService for the given workspace_root.

        Called by Gateway assembly code once per agent during startup.
        """
        self._services[str(workspace_root.expanduser().resolve())] = service

    def set_gateway_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Inject the Gateway asyncio loop into all registered services.

        Called from GatewayRuntime._run_until_shutdown() once the loop is
        running so enqueue() called from worker threads (asyncio.to_thread)
        can schedule execute_fn on the correct loop.
        """
        for service in self._services.values():
            service._gateway_loop = loop  # noqa: SLF001

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
            context: HostCapabilityContext; workspace_root is used to route to the correct
                per-agent CronExecutionService.

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

        service = self._resolve_service(context.workspace_root)
        if service is None:
            return {
                "accepted": False,
                "job_id": job_id,
                "request_id": None,
                "error_code": "cron_unavailable",
            }

        return service.enqueue(job_id=job_id, trigger="manual")

    def _resolve_service(self, workspace_root: str) -> CronExecutionService | None:
        """Resolve the CronExecutionService for the given workspace_root."""
        if self._single_service is not None:
            # Single-service mode (tests): ignore workspace routing.
            return self._single_service
        resolved = str(Path(workspace_root).expanduser().resolve())
        return self._services.get(resolved)
