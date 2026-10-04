"""Request-owned company admission, with explicit slow-wait suspension."""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")
_current: ContextVar["CompanyLease | None"] = ContextVar("company_lease", default=None)


class CompanyLease:
    """Keep a request's lock ownership through result, error and cancellation paths."""

    def __init__(self, gate: asyncio.Lock, revalidate: Callable[[], Awaitable[None]]):
        self.gate = gate
        self.revalidate = revalidate
        self.owner = asyncio.current_task()
        self.held = True

    def release(self) -> None:
        """Release this request's admission lock once."""
        if self.held:
            self.held = False
            self.gate.release()

    async def _resume(self) -> None:
        # Cancellation must not let exception handlers write through an unheld gate.
        acquisition = asyncio.create_task(self.gate.acquire())
        cancelled = False
        while True:
            try:
                await asyncio.shield(acquisition)
                break
            except asyncio.CancelledError:
                cancelled = True
        self.held = True
        await self.revalidate()
        if cancelled:
            raise asyncio.CancelledError

    async def wait(self, operation: Awaitable[T]) -> T:
        """Run one slow operation outside admission, then revalidate before returning."""
        self.release()
        try:
            result = await operation
        except BaseException:
            await self._resume()
            raise
        await self._resume()
        return result


@asynccontextmanager
async def company_lease(gate: asyncio.Lock, revalidate: Callable[[], Awaitable[None]]):
    """Own admission for this task; inherited background contexts cannot release it."""
    await gate.acquire()
    lease = CompanyLease(gate, revalidate)
    token = _current.set(lease)
    try:
        yield lease
    finally:
        lease.release()
        _current.reset(token)


async def await_outside_gate(operation: Awaitable[T]) -> T:
    """Suspend admission only when called by its owning request task."""
    lease = _current.get()
    if lease is None or lease.owner is not asyncio.current_task() or not lease.held:
        return await operation
    return await lease.wait(operation)


@asynccontextmanager
async def outside_gate_lock(lock: asyncio.Lock):
    """Wait for a resource lock without holding company admission in reverse order."""
    acquired = False

    async def acquire():
        nonlocal acquired
        await lock.acquire()
        acquired = True

    try:
        if lock.locked():
            await await_outside_gate(acquire())
        else:
            await acquire()
        yield
    finally:
        if acquired:
            lock.release()
