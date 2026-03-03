"""Async hook dispatcher with timeout/error isolation semantics."""

import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any, Mapping

from .context import HookContext
from .registry import HookRegistry
from .types import HookRegistration, HookStatus, ensure_known_hook_event


@dataclass(frozen=True, slots=True)
class HookExecution:
    """Record one hook execution outcome for diagnostics and observability."""

    hook_id: str
    event: str
    status: HookStatus
    duration_ms: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class InterceptDispatchResult:
    """Return rewritten intercept payload with stop flag and diagnostics."""

    payload: dict[str, Any]
    stopped: bool
    diagnostics: tuple[HookExecution, ...]


class HookRunner:
    """Dispatch hook events while isolating handler failures and timeouts."""

    def __init__(self, *, registry: HookRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> HookRegistry:
        """Expose backing registry for read-only inspection."""

        return self._registry

    async def dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> tuple[HookExecution, ...]:
        """Run observe handlers and collect per-hook diagnostics."""

        normalized_event = ensure_known_hook_event(event)
        diagnostics: list[HookExecution] = []
        for registration in self._registry.handlers_for(normalized_event):
            _, record = await self._execute_handler(
                registration=registration,
                payload=payload,
                ctx=ctx,
            )
            diagnostics.append(record)
        return tuple(diagnostics)

    async def dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> InterceptDispatchResult:
        """Run intercept handlers that may rewrite payload or stop processing."""

        normalized_event = ensure_known_hook_event(event)
        mutable_payload = dict(payload)
        diagnostics: list[HookExecution] = []
        stopped = False

        for registration in self._registry.handlers_for(normalized_event):
            handler_payload = dict(mutable_payload)
            # DISPATCH ISOLATION: each handler receives a copy so failed/mutating
            # handlers cannot corrupt shared payload state for later handlers.
            result, record = await self._execute_handler(
                registration=registration,
                payload=handler_payload,
                ctx=ctx,
            )
            diagnostics.append(record)

            if record.status != "ok":
                # Timeout/error diagnostics are preserved, but dispatch keeps going.
                continue
            if not isinstance(result, Mapping):
                continue

            if normalized_event == "input":
                action = str(result.get("action", "continue"))
                if action == "transform":
                    if "text" in result:
                        mutable_payload["text"] = result["text"]
                    if "images" in result:
                        mutable_payload["images"] = result["images"]
                elif action == "handled":
                    stopped = True
                    break
                continue

            if normalized_event == "before_agent_start":
                if "message" in result and result["message"] is not None:
                    mutable_payload["message"] = result["message"]
                if "system_prompt" in result and result["system_prompt"] is not None:
                    mutable_payload["system_prompt"] = result["system_prompt"]
                continue

            if normalized_event == "tool_call":
                if "args" in result and isinstance(result["args"], Mapping):
                    mutable_payload["args"] = dict(result["args"])
                if "allow_unlisted" in result:
                    mutable_payload["allow_unlisted"] = bool(result["allow_unlisted"])
                if bool(result.get("block")):
                    mutable_payload["block"] = True
                    mutable_payload["reason"] = result.get("reason")
                    stopped = True
                    break
                continue

            if normalized_event == "tool_result":
                for field in ("output", "content", "details", "is_error", "error"):
                    if field in result:
                        mutable_payload[field] = result[field]
                continue

            mutable_payload.update(result)

        return InterceptDispatchResult(
            payload=mutable_payload,
            stopped=stopped,
            diagnostics=tuple(diagnostics),
        )

    async def _execute_handler(
        self,
        *,
        registration: HookRegistration,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> tuple[Any, HookExecution]:
        started = time.perf_counter()
        timeout_seconds = registration.timeout_ms / 1000
        try:
            result = await asyncio.wait_for(
                self._invoke_handler(registration, payload, ctx),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return None, HookExecution(
                hook_id=registration.hook_id,
                event=registration.event,
                status="timeout",
                duration_ms=duration_ms,
                error="hook timeout",
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return None, HookExecution(
                hook_id=registration.hook_id,
                event=registration.event,
                status="error",
                duration_ms=duration_ms,
                error=f"{type(exc).__name__}: {exc}",
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        return result, HookExecution(
            hook_id=registration.hook_id,
            event=registration.event,
            status="ok",
            duration_ms=duration_ms,
        )

    async def _invoke_handler(
        self,
        registration: HookRegistration,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> Any:
        if inspect.iscoroutinefunction(registration.handler):
            return await registration.handler(payload, ctx)

        result = await asyncio.to_thread(registration.handler, payload, ctx)
        if inspect.isawaitable(result):
            return await result
        return result
