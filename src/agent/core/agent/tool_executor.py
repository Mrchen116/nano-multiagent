"""Streaming tool executor with FIFO queue and dynamic concurrency safety."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Protocol

from agent.core.agent.reject_messages import build_reject_message
from agent.core.types import ToolCall, ToolResult


class _ToolRegistryLike(Protocol):
    """Minimal registry surface needed by StreamingToolExecutor."""

    def get(self, name: str) -> Any | None: ...

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: Any | None = None,
        session_file_state: Any | None = None,
        out_meta: dict[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


@dataclass
class _QueuedTool:
    tool_call: ToolCall
    status: str = "queued"  # queued | executing | completed | yielded
    is_safe: bool = False
    result: ToolResult | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    _cancelled: bool = False
    hook_context: Any | None = None
    duration_ms: int = 0
    _started_at_ns: int = 0


class StreamingToolExecutor:
    """FIFO queue that executes tools with dynamic concurrency safety.

    Safe tools run in parallel. Non-safe tools block all subsequent
    queued items until they complete, matching Claude Code behaviour.
    """

    def __init__(
        self,
        tool_registry: _ToolRegistryLike,
        *,
        hook_context: Any | None = None,
        session_file_state: Any | None = None,
        tool_execution_allowlist: tuple[str, ...] | None = None,
    ) -> None:
        self._queue: list[_QueuedTool] = []
        self._registry = tool_registry
        self._hook_context = hook_context
        self._session_file_state = session_file_state
        # Execution-layer allowlist. When set (fork side-chain only), tool calls
        # whose name is not in this set are denied with a synthetic error result
        # and never reach registry.execute(). None means "no restriction" — the
        # main agent path always passes None so its tool execution is unaffected.
        self._tool_execution_allowlist = (
            frozenset(tool_execution_allowlist)
            if tool_execution_allowlist is not None
            else None
        )
        self._lock = asyncio.Lock()
        self._has_errored = False
        self._errored_tool_name = ""
        self._sibling_event = asyncio.Event()

    def _is_execution_denied(self, tool_name: str) -> bool:
        """Return True when the allowlist is active and excludes this tool name."""
        if self._tool_execution_allowlist is None:
            return False
        return tool_name not in self._tool_execution_allowlist

    def add_tool(self, tool_call: ToolCall, *, hook_context: Any | None = None) -> None:
        """Enqueue a tool call when its content_block completes in the stream."""
        tool = self._registry.get(tool_call.name)
        safe_method = getattr(tool, "is_concurrency_safe", None)
        is_safe = (
            tool.is_concurrency_safe(tool_call.arguments)
            if tool is not None and callable(safe_method)
            else bool(safe_method)
        )
        item = _QueuedTool(
            tool_call=tool_call, is_safe=is_safe, hook_context=hook_context
        )
        self._queue.append(item)
        asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Start queued tools when concurrency rules allow."""
        async with self._lock:
            for item in self._queue:
                if item.status != "queued":
                    continue
                if self._can_execute(item.is_safe):
                    item.status = "executing"
                    item.task = asyncio.create_task(self._execute_one(item))
                elif not item.is_safe:
                    # A non-safe tool blocks everything after it.
                    break

    def _can_execute(self, is_safe: bool) -> bool:
        executing = [t for t in self._queue if t.status == "executing"]
        if not executing:
            return True
        return is_safe and all(t.is_safe for t in executing)

    def _should_cancel(self, item: _QueuedTool) -> bool:
        if not self._has_errored:
            return False
        if item.tool_call.name != "bash":
            return False
        return True

    def _synthetic_error(
        self, item: _QueuedTool, reason: str, *, approval: str | None = None
    ) -> ToolResult:
        # feat-434-M1 (F2): a tool cancelled AFTER registry.execute already stamped a
        # user approval (sibling-abort race) must keep it — otherwise the front-end
        # gate region silently drops 「已授权」 for a genuinely user-approved tool.
        return ToolResult(
            call_id=item.tool_call.call_id,
            name=item.tool_call.name,
            output=None,
            error=f"aborted: {reason}",
            approval=approval,
        )

    async def _execute_one(self, item: _QueuedTool) -> None:
        """Run a single tool call and record its result."""
        item._started_at_ns = time.perf_counter_ns()
        # feat-434-M1 (C2): hoist the approval sink ABOVE the try so the
        # ``except asyncio.CancelledError`` branch can read it — a gate-approved tool
        # interrupted mid-run must keep approval=user_allow, same invariant as the
        # sibling-abort branch. Empty dict when cancelled before execute() ran → None.
        exec_meta: dict[str, Any] = {}
        try:
            if self._should_cancel(item):
                item.result = self._synthetic_error(
                    item, "cancelled by sibling bash error"
                )
                item.status = "completed"
                item._event.set()
                await self._process_queue()
                return

            # Execution-layer allowlist enforcement (fork side-chain only).
            # Deny non-allowlisted tools with a synthetic error result — the call
            # never reaches registry.execute(), so the tool has no side effects.
            if self._is_execution_denied(item.tool_call.name):
                # feat-440-M1: a subagent (allowlist active) block — its model-facing
                # text is the SUBAGENT_REJECT variant ("换做法/上报"), identical to a
                # gate-denied tool inside the fork, so the LLM gets one consistent
                # signal regardless of which path denied it.
                item.result = ToolResult(
                    call_id=item.tool_call.call_id,
                    name=item.tool_call.name,
                    output=None,
                    error=build_reject_message(
                        approval=None, reason=None, is_subagent=True
                    ),
                    arguments=dict(item.tool_call.arguments),
                )
                item.status = "completed"
                item._event.set()
                await self._process_queue()
                return

            # feat-434-M1: per-call sink for execution metadata that must not leak
            # into the model-facing output. The gate writes approval=user_allow here
            # on the success path (the deny path rides ToolError.details instead).
            # (exec_meta is declared above the try for the CancelledError branch.)
            output = await self._registry.execute(
                item.tool_call.name,
                item.tool_call.arguments,
                hook_context=item.hook_context or self._hook_context,
                session_file_state=self._session_file_state,
                out_meta=exec_meta,
            )
            approval = exec_meta.get("approval")
            approval = approval if isinstance(approval, str) and approval else None
            if self._should_cancel(item):
                item.result = self._synthetic_error(
                    item, "cancelled by sibling bash error", approval=approval
                )
            else:
                item.result = ToolResult(
                    call_id=item.tool_call.call_id,
                    name=item.tool_call.name,
                    output=output,
                    duration_ms=item.duration_ms,
                    arguments=dict(item.tool_call.arguments),
                    approval=approval,
                )
            item.status = "completed"
        except asyncio.CancelledError:
            # feat-434-M1 (C2): a gate-approved tool interrupted mid-run must keep its
            # approval — mirror the sibling-abort branch. exec_meta is empty (→ None)
            # when cancelled before execute() stamped it.
            cancelled_approval = exec_meta.get("approval")
            cancelled_approval = (
                cancelled_approval
                if isinstance(cancelled_approval, str) and cancelled_approval
                else None
            )
            item.result = self._synthetic_error(
                item, "tool execution discarded", approval=cancelled_approval
            )
            item.status = "completed"
            raise
        except Exception as exc:
            # bugfix-410-M2 (#97): lift the dedicated reason_code (e.g. "denied" for a
            # hook block) out of a ToolError so it survives into the ToolResult; the
            # registry only kept str(exc) before, dropping the classification.
            reason_code = None
            approval = None
            blocked_by_hook = False
            block_reason = None
            details = getattr(exc, "details", None)
            if isinstance(details, Mapping):
                rc = details.get("reason_code")
                if isinstance(rc, str) and rc:
                    reason_code = rc
                # feat-434-M1: lift the gate's user_deny verdict the same way as
                # reason_code — both ride the blocked tool's ToolError.details.
                ap = details.get("approval")
                if isinstance(ap, str) and ap:
                    approval = ap
                blocked_by_hook = bool(details.get("blocked_by_hook"))
                # feat-440-M1: the gate's free-text reason was dropped before — lift
                # it so it can be woven into the semantic rejection text below.
                br = details.get("reason")
                if isinstance(br, str) and br:
                    block_reason = br
            # feat-440-M1: a hook block (user Deny / policy auto-block) gets a
            # semantic, scenario-specific message instead of the generic
            # "tool blocked by hook" — so the LLM can tell a user's deliberate Deny
            # (停下等指示) from an automatic policy block (换做法/上报). Genuine tool
            # failures (no block) keep their raw error string.
            if blocked_by_hook:
                error_text = build_reject_message(
                    approval=approval,
                    reason=block_reason,
                    is_subagent=self._tool_execution_allowlist is not None,
                )
            else:
                error_text = str(exc)
            item.result = ToolResult(
                call_id=item.tool_call.call_id,
                name=item.tool_call.name,
                output=None,
                error=error_text,
                duration_ms=item.duration_ms,
                arguments=dict(item.tool_call.arguments),
                reason_code=reason_code,
                approval=approval,
            )
            item.status = "completed"
            # Bash error triggers sibling abort.
            if item.tool_call.name == "bash":
                self._has_errored = True
                self._errored_tool_name = item.tool_call.name
                self._sibling_event.set()
        finally:
            item.duration_ms = (
                time.perf_counter_ns() - item._started_at_ns
            ) // 1_000_000
            if item.result is not None:
                # update result with final duration
                item.result = ToolResult(
                    call_id=item.result.call_id,
                    name=item.result.name,
                    output=item.result.output,
                    error=item.result.error,
                    content=item.result.content,
                    duration_ms=item.duration_ms,
                    arguments=item.result.arguments,
                    reason_code=item.result.reason_code,
                    approval=item.result.approval,
                )
        item._event.set()
        await self._process_queue()

    def get_completed_results(self) -> list[ToolResult]:
        """Non-blocking: return tool_results for completed tools in order."""
        results: list[ToolResult] = []
        for item in self._queue:
            if item.status == "completed":
                item.status = "yielded"
                results.append(item.result)
            elif item.status == "executing":
                # Any executing tool (safe or not) blocks later results: the
                # caller must see results in enqueue order so that tool_results
                # sent to the LLM line up with the assistant's tool_use order.
                break
        return results

    async def get_remaining_results(self) -> AsyncIterator[ToolResult]:
        """Blocking: wait for all unfinished tools, yield results in order."""
        for item in self._queue:
            if item.status in ("queued", "executing"):
                await item._event.wait()
            if item.status == "completed":
                item.status = "yielded"
                yield item.result

    def has_unfinished(self) -> bool:
        """Return True while any tool is still queued or executing."""
        return any(t.status in ("queued", "executing") for t in self._queue)

    def discard(self) -> None:
        """Abort all queued/executing tools (fallback scenario)."""
        for item in self._queue:
            if item.status in ("queued", "executing"):
                if item.task is not None:
                    item.task.cancel()
                item._cancelled = True
                item.status = "completed"
                item.result = ToolResult(
                    call_id=item.tool_call.call_id,
                    name=item.tool_call.name,
                    output=None,
                    error="aborted: tool execution discarded",
                    arguments=dict(item.tool_call.arguments),
                )
                item._event.set()
