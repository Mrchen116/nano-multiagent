"""Keep human approval cards flowing while the model-event consumer awaits delivery."""

from __future__ import annotations

import asyncio
import inspect

from agent.sdk import PermissionOutcome


class DeliveryPermission:
    """Observe only permission facts during one Gateway authorization operation."""

    def __init__(self, *, kernel, contexts, observe):
        self.kernel = kernel
        self.contexts = contexts
        self.observe = observe

    async def authorize(self, candidate, destination):
        """Await real SDK authorization, cancelling it when its product lease is revoked."""
        anchor = self.kernel.current_event_sequence()
        settled = asyncio.Event()
        settled.set()
        pending = set()

        async def permission_events():
            async for event in self.kernel.stream(
                candidate.session_id, after_sequence=anchor
            ):
                if event.get("run_id") != candidate.run_id:
                    continue
                name = event.get("event")
                if name not in {"permission_request", "permission_resolved"}:
                    continue
                request_id = event.get("request_id")
                if name == "permission_request":
                    pending.add(request_id)
                    settled.clear()
                result = self.observe(event)
                if inspect.isawaitable(result):
                    await result
                if name == "permission_resolved":
                    pending.discard(request_id)
                    if not pending:
                        settled.set()

        pump = asyncio.create_task(permission_events())
        authorization = asyncio.create_task(
            self.kernel.authorize_tool(
                candidate.session_id,
                "send_message",
                {"target": destination.target, "text": candidate.text},
                f"delivery:{candidate.run_id}:{candidate.candidate_id}",
                workspace_root=destination.workspace,
                run_id=candidate.run_id,
            )
        )
        revoked = asyncio.create_task(self.contexts.await_revoked(candidate.run_id))
        try:
            done, _ = await asyncio.wait(
                (authorization, revoked, pump), return_when=asyncio.FIRST_COMPLETED
            )
            if revoked in done:
                return PermissionOutcome(False, "delivery_revoked")
            if pump in done:
                await pump
                raise RuntimeError(
                    "Permission event stream closed before authorization"
                )
            result = await authorization
            await settled.wait()
            return result
        finally:
            for task in (authorization, pump, revoked):
                task.cancel()
            await asyncio.gather(authorization, pump, revoked, return_exceptions=True)
