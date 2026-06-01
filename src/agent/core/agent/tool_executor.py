"""Streaming tool executor with FIFO queue and dynamic concurrency safety."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Protocol

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

    def _synthetic_error(self, item: _QueuedTool, reason: str) -> ToolResult:
        return ToolResult(
            call_id=item.tool_call.call_id,
            name=item.tool_call.name,
            output=None,
            error=f"aborted: {reason}",
        )

    async def _execute_one(self, item: _QueuedTool) -> None:
        """Run a single tool call and record its result."""
        item._started_at_ns = time.perf_counter_ns()
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
                item.result = ToolResult(
                    call_id=item.tool_call.call_id,
                    name=item.tool_call.name,
                    output=None,
                    error=(
                        f"tool '{item.tool_call.name}' is not allowed in this "
                        "background review context"
                    ),
                    arguments=dict(item.tool_call.arguments),
                )
                item.status = "completed"
                item._event.set()
                await self._process_queue()
                return

            output = await self._registry.execute(
                item.tool_call.name,
                item.tool_call.arguments,
                hook_context=item.hook_context or self._hook_context,
                session_file_state=self._session_file_state,
            )
            if self._should_cancel(item):
                item.result = self._synthetic_error(
                    item, "cancelled by sibling bash error"
                )
            else:
                item.result = ToolResult(
                    call_id=item.tool_call.call_id,
                    name=item.tool_call.name,
                    output=output,
                    duration_ms=item.duration_ms,
                    arguments=dict(item.tool_call.arguments),
                )
            item.status = "completed"
        except asyncio.CancelledError:
            item.result = self._synthetic_error(item, "tool execution discarded")
            item.status = "completed"
            raise
        except Exception as exc:
            item.result = ToolResult(
                call_id=item.tool_call.call_id,
                name=item.tool_call.name,
                output=None,
                error=str(exc),
                duration_ms=item.duration_ms,
                arguments=dict(item.tool_call.arguments),
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
