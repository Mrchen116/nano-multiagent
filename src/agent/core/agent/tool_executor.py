"""Tool batch partitioning and concurrent execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

from agent.core.types import ToolCall, ToolResult


@dataclass(frozen=True)
class ToolBatch:
    """One atomic unit of tool execution: either a single unsafe call or N concurrent safe calls."""

    calls: tuple[ToolCall, ...]
    concurrent: bool


def partition_into_batches(
    calls: Sequence[ToolCall],
    concurrency_map: Mapping[str, bool],
) -> list[ToolBatch]:
    """Partition tool calls into ordered batches preserving relative order.

    Consecutive concurrency-safe calls form one ConcurrentBatch; each unsafe
    call forms its own SerialBatch. Batches execute sequentially; calls within
    a ConcurrentBatch execute in parallel.

    Example: [safe, safe, unsafe, safe] →
        [Batch(safe safe, concurrent=True), Batch(unsafe, concurrent=False), Batch(safe, concurrent=True)]
    """
    if not calls:
        return []

    batches: list[ToolBatch] = []
    safe_buffer: list[ToolCall] = []

    for call in calls:
        if concurrency_map.get(call.name, False):
            safe_buffer.append(call)
        else:
            if safe_buffer:
                batches.append(ToolBatch(calls=tuple(safe_buffer), concurrent=True))
                safe_buffer = []
            batches.append(ToolBatch(calls=(call,), concurrent=False))

    if safe_buffer:
        batches.append(ToolBatch(calls=tuple(safe_buffer), concurrent=True))

    return batches


ExecuteFn = Callable[[ToolCall], Awaitable[ToolResult]]


class ToolExecutor:
    """Execute a ToolBatch, returning results in original call order."""

    async def execute(self, batch: ToolBatch, execute_fn: ExecuteFn) -> tuple[ToolResult, ...]:
        if batch.concurrent and len(batch.calls) > 1:
            return await self._execute_concurrent(batch.calls, execute_fn)
        return (await execute_fn(batch.calls[0]),)

    async def _execute_concurrent(
        self,
        calls: tuple[ToolCall, ...],
        execute_fn: ExecuteFn,
    ) -> tuple[ToolResult, ...]:
        raw = await asyncio.gather(
            *[execute_fn(call) for call in calls],
            return_exceptions=True,
        )
        return tuple(
            r
            if isinstance(r, ToolResult)
            else ToolResult(call_id=call.call_id, name=call.name, error=str(r))
            for call, r in zip(calls, raw)
        )
