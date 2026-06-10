"""Host capability dispatcher protocol for product-neutral capability invocation.

Products inject side effects (e.g. personal assistant cron enqueue) through
a HostCapabilityDispatcher at composition root (build_kernel); the generic
dispatcher is forwarded to ToolContext so cron tool can invoke capabilities
without importing personal_assistant directly.

Provenance: bugfix-402 design.md Decision 1 — 通用 SDK 只提供宿主能力 dispatcher.
Types defined here (agent.core.tools) rather than agent.sdk to avoid the
sdk→core import inversion; agent.sdk re-exports them as the public surface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class HostCapabilityContext:
    """Kernel-trusted context passed to every capability invocation.

    The dispatcher receives only information the kernel can guarantee: session
    identity, workspace location, and product scope.  Products must not add
    caller-supplied fields here; payload carries the request arguments instead.

    Args:
        session_id: The kernel session ID that triggered this capability request.
        workspace_root: Agent workspace root resolved by the kernel.
        product_id: Product identity string (e.g. "personal_assistant").
    """

    session_id: str
    workspace_root: str
    product_id: str


class HostCapabilityDispatcher(ABC):
    """Abstract base for product-owned capability dispatch.

    Products subclass this and inject an instance at build_kernel() time.
    The kernel passes the dispatcher to ToolContext; tools call
    ``ctx.host_capabilities.invoke(capability, payload, context)`` without
    knowing the concrete product or import path.

    The invoke contract is synchronous by design: tools run on RunsRegistry's
    background thread; the dispatcher must bridge to the Gateway's asyncio loop
    via call_soon_threadsafe / thread-safe future internally, but the tool-facing
    surface stays sync.  The short blocking window is only the "accepted" ack
    check — the dispatcher must NOT block for full job completion.
    """

    @abstractmethod
    def invoke(
        self,
        capability: str,
        payload: Mapping[str, Any],
        context: HostCapabilityContext,
    ) -> Mapping[str, Any]:
        """Invoke a named capability and return a structured ack.

        Args:
            capability: Namespaced capability name, e.g.
                ``"personal_assistant.cron.enqueue"``.
            payload: Capability-specific request parameters.  The dispatcher
                validates and acts on them; the kernel does not interpret this.
            context: Kernel-trusted execution context.

        Returns:
            A Mapping with at least an ``accepted`` bool key.  Concrete shape
            is defined by the capability contract (product-private).

        Raises:
            KeyError: When the capability name is not registered.
            ValueError: When payload validation fails.
        """
