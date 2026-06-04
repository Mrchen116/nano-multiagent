"""Canonical async hook dispatcher with timeout/error isolation semantics."""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping

from agent.core.observability.tracing import span

from .context import HookContext
from .registry import HookRegistry
from .types import HookEventMode, HookRegistration, HookStatus, ensure_known_hook_event

_log = logging.getLogger("agent.core.hooks.runner")


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
        """Run observe handlers and collect per-hook diagnostics.

        Observe handlers always receive a HookContext with fork_conversation=None.
        Only background handlers (via dispatch_background) get fork_conversation.
        """

        with span("HookRunner.dispatch_observe", event=event):
            normalized_event = ensure_known_hook_event(event)
            # Strip fork_conversation — it's only valid for background dispatches.
            observe_ctx = _strip_fork_conversation(ctx)
            diagnostics: list[HookExecution] = []
            for registration in self._registry.handlers_for(normalized_event):
                # Intercept-mode handlers run only in dispatch_intercept, where
                # their return value is honored against the populated payload/ctx.
                # Running them here would re-invoke them on an observe ctx (e.g.
                # the auto_mode_gate classifier on a ctx without message_history)
                # and discard the result — wasted work, and for the gate a wasted
                # model call producing a blind, empty-transcript classification.
                if registration.mode == HookEventMode.INTERCEPT:
                    continue
                _, record = await self._execute_handler(
                    registration=registration,
                    payload=payload,
                    ctx=observe_ctx,
                )
                diagnostics.append(record)
            return tuple(diagnostics)

    async def dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> InterceptDispatchResult:
        """Run intercept handlers that may rewrite payload or stop processing.

        Intercept handlers always receive a HookContext with fork_conversation=None.
        Only background handlers (via dispatch_background) get fork_conversation.
        """

        normalized_event = ensure_known_hook_event(event)
        # Strip fork_conversation — it's only valid for background dispatches.
        intercept_ctx = _strip_fork_conversation(ctx)
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
                ctx=intercept_ctx,
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

    def dispatch_background(
        self,
        event: str,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> None:
        """Start all BACKGROUND handlers for an event as fire-and-forget tasks.

        Does not await handlers, applies no timeout_ms, and swallows exceptions.
        Only BACKGROUND-mode registrations are dispatched here (observe/intercept
        handlers are skipped — they belong to dispatch_observe/dispatch_intercept).

        The ctx passed here should have fork_conversation set if the event warrants
        a side-chain fork (e.g. agent_end with self-improvement hook).
        """

        normalized_event = ensure_known_hook_event(event)
        for registration in self._registry.background_handlers_for(normalized_event):
            # Capture registration in closure to avoid late-binding issues.
            def _make_task(reg: HookRegistration) -> None:
                async def _run() -> None:
                    try:
                        await self._invoke_handler(reg, payload, ctx)
                    except Exception as exc:
                        # Background hook failures must never crash the caller.
                        _log.warning(
                            "background hook error isolated",
                            extra={
                                "hook_id": reg.hook_id,
                                "event": normalized_event,
                                "error": str(exc),
                            },
                        )

                asyncio.create_task(
                    _run(), name=f"bg-hook:{normalized_event}:{reg.hook_id}"
                )

            _make_task(registration)

    async def _execute_handler(
        self,
        *,
        registration: HookRegistration,
        payload: Mapping[str, Any],
        ctx: HookContext,
    ) -> tuple[Any, HookExecution]:
        started = time.perf_counter()
        try:
            if registration.timeout_ms is None:
                # Hook self-manages time boundaries — do not wrap in wait_for.
                # Used by security-critical hooks like auto_mode_gate that may
                # legitimately park for extended periods awaiting user input.
                result = await self._invoke_handler(registration, payload, ctx)
            else:
                timeout_seconds = registration.timeout_ms / 1000
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


def log_hook_diagnostics(
    hook_ctx: "HookContext",
    *,
    event: str,
    diagnostics: tuple["HookExecution", ...],
) -> None:
    """Log a warning for each hook execution that did not finish with status 'ok'.

    Previously duplicated as a private static method in AgentRuntime, AgentLoop,
    ToolRegistry, and RunsRegistry — consolidated here as refactor-395-M1.

    Args:
        hook_ctx: The hook context whose logger will receive the warning.
        event: The hook event name (e.g. 'tool.call.before').
        diagnostics: Execution records returned by the hook runner.
    """
    for item in diagnostics:
        if item.status == "ok":
            continue
        hook_ctx.logger.warning(
            "hook execution isolated",
            event=event,
            hook_id=item.hook_id,
            status=item.status,
            duration_ms=item.duration_ms,
            error=item.error,
        )


def _strip_fork_conversation(ctx: HookContext) -> HookContext:
    """Return a copy of ctx with fork_conversation=None.

    Observe and intercept handlers must never receive fork_conversation;
    it is reserved for background dispatches only.
    """
    if ctx.fork_conversation is None:
        return ctx  # already stripped, avoid allocation
    # Null ONLY fork_conversation; replace() preserves every other field so
    # later-added ones (message_history, permission_requester) cannot be
    # silently dropped — the manual rebuild had been dropping both, which left
    # the classifier transcript empty and fail-closed the permission ask path
    # on any fork_conversation-bearing dispatch.
    return replace(ctx, fork_conversation=None)
