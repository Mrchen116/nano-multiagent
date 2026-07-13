"""Typed owner-loop executor for kernel conversation targets."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import threading
from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from agent.core import ids
from agent.core.session.types import TurnRequest
from agent.core.types import TurnResult


class ExecutorClosedError(RuntimeError):
    """Signal that target admission closed before a target was bound."""


class _ExecutorState(StrEnum):
    OPEN = "open"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class TargetToken:
    """Identify one admitted carrier target without exposing its Task."""

    token_id: str
    kind: str
    owner_id: str


@dataclass(frozen=True, slots=True)
class TargetCompletion:
    """Report carrier outcome only after conversation cleanup has unwound."""

    token: TargetToken
    result: TurnResult | None = None
    error: BaseException | None = None
    cancelled: bool = False
    cleanup_ack: bool = True


@dataclass(frozen=True, slots=True)
class AcceptedTargetSnapshot:
    """Snapshot all targets admitted before shutdown closed the gate."""

    top_level: tuple[TargetToken, ...]
    auxiliary: tuple[TargetToken, ...]
    lifecycle: tuple[TargetToken, ...]


class TopLevelCompletionSink(Protocol):
    """Bind semantic run state to a token and consume cleanup completion."""

    def bind_target(self, token: TargetToken) -> None:
        """Publish a prepared run only after target admission succeeds."""

    def complete(self, completion: TargetCompletion) -> None:
        """Consume one terminal carrier outcome and cleanup acknowledgement."""

    def started(self, token: TargetToken) -> None:
        """Mark semantic execution start immediately before the carrier awaits."""


class ConversationTarget(Protocol):
    """Conversation operation executable on the kernel owner loop."""

    async def submit_turn(self, request: TurnRequest) -> TurnResult:
        """Run one fully-owned conversation turn."""

    async def compact(self) -> Any:
        """Run one manual compaction transaction."""

    async def fork(self, *, up_to: str | None = None) -> Any:
        """Create an independent fork through the owning directory."""


class AuxiliaryHandle:
    """Expose typed auxiliary cancellation/result without a raw coroutine seam."""

    def __init__(
        self,
        *,
        executor: KernelExecutor,
        token: TargetToken,
        result_future: concurrent.futures.Future[TurnResult],
        cleanup_ack: threading.Event,
    ) -> None:
        self._executor = executor
        self.token = token
        self._result_future = result_future
        self.cleanup_ack = cleanup_ack

    def cancel(self, *, force: bool = False) -> bool:
        """Request cancellation, optionally bypassing cooperative grace."""

        return self._executor.request_cancel(self.token, force=force)

    def result(self, timeout: float | None = None) -> TurnResult:
        """Wait for and return the auxiliary turn result."""

        return self._result_future.result(timeout=timeout)

    @property
    def cancelled(self) -> bool:
        """Return whether the auxiliary result future reached cancellation."""

        return self._result_future.cancelled()


@dataclass(slots=True)
class _Target:
    token: TargetToken
    session: ConversationTarget
    request: TurnRequest
    sink: TopLevelCompletionSink | None
    result_future: concurrent.futures.Future[TurnResult] | None
    cleanup_ack: threading.Event
    task: asyncio.Task[None] | None = None
    cancel_requested: bool = False


@dataclass(slots=True)
class _LifecycleTarget:
    token: TargetToken
    operation: Callable[[], Awaitable[Any]]
    result_future: concurrent.futures.Future[Any]
    cleanup_ack: threading.Event
    task: asyncio.Task[None] | None = None
    cancel_requested: bool = False


class KernelExecutor:
    """Own one event loop and every top-level, auxiliary, and lifecycle Task."""

    def __init__(
        self,
        *,
        cancel_grace_seconds: float = 0.1,
        drain_timeout_seconds: float = 30.0,
    ) -> None:
        self._cancel_grace_seconds = max(0.0, cancel_grace_seconds)
        self._drain_timeout_seconds = max(0.1, drain_timeout_seconds)
        self._guard = threading.Condition()
        self._state = _ExecutorState.OPEN
        self._targets: dict[str, _Target | _LifecycleTarget] = {}
        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="nano-kernel-executor",
            daemon=True,
        )
        self._thread.start()
        if not self._loop_ready.wait(timeout=2):  # pragma: no cover - OS failure.
            raise RuntimeError("kernel executor loop failed to start")

    def start_top_level(
        self,
        run_id: str,
        session: ConversationTarget,
        request: TurnRequest,
        completion_sink: TopLevelCompletionSink,
    ) -> TargetToken:
        """Bind a prepared run token before scheduling its carrier Task."""

        return self._admit(
            kind="top_level",
            owner_id=run_id,
            session=session,
            request=request,
            sink=completion_sink,
        ).token

    def start_auxiliary(
        self,
        aux_id: str,
        session: ConversationTarget,
        request: TurnRequest,
    ) -> AuxiliaryHandle:
        """Admit an auxiliary turn tracked through cleanup and shutdown."""

        result_future: concurrent.futures.Future[TurnResult] = (
            concurrent.futures.Future()
        )
        target = self._admit(
            kind="auxiliary",
            owner_id=aux_id,
            session=session,
            request=request,
            result_future=result_future,
        )
        return AuxiliaryHandle(
            executor=self,
            token=target.token,
            result_future=result_future,
            cleanup_ack=target.cleanup_ack,
        )

    async def compact(self, session: ConversationTarget) -> Any:
        """Run manual compaction as a tracked lifecycle target on the owner loop."""

        return await asyncio.wrap_future(
            self._admit_lifecycle("compact", session.compact)
        )

    async def fork(
        self,
        session: ConversationTarget,
        *,
        up_to: str | None = None,
    ) -> Any:
        """Run fork capture/persist as a tracked lifecycle target on the owner loop."""

        return await asyncio.wrap_future(
            self._admit_lifecycle("fork", lambda: session.fork(up_to=up_to))
        )

    def request_cancel(self, token: TargetToken, *, force: bool = False) -> bool:
        """Request carrier cancellation, optionally bypassing cooperative grace."""

        with self._guard:
            target = self._targets.get(token.token_id)
            if target is None:
                return False
            target.cancel_requested = True
            task = target.task
        if task is not None:
            self._loop.call_soon_threadsafe(
                self._schedule_cancel,
                target,
                force,
            )
        return True

    def begin_shutdown(self) -> AcceptedTargetSnapshot:
        """Atomically close admission and snapshot every accepted target."""

        with self._guard:
            if self._state is _ExecutorState.OPEN:
                self._state = _ExecutorState.DRAINING
            targets = tuple(target.token for target in self._targets.values())
        return AcceptedTargetSnapshot(
            top_level=tuple(token for token in targets if token.kind == "top_level"),
            auxiliary=tuple(token for token in targets if token.kind == "auxiliary"),
            lifecycle=tuple(token for token in targets if token.kind == "lifecycle"),
        )

    def shutdown(
        self,
        *,
        timeout: float | None = None,
        finalize: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Cancel targets, run the final owner-loop cleanup, then stop the loop."""

        snapshot = self.begin_shutdown()
        for token in (*snapshot.top_level, *snapshot.auxiliary, *snapshot.lifecycle):
            self.request_cancel(token)
        wait_timeout = timeout if timeout is not None else self._drain_timeout_seconds
        with self._guard:
            self._guard.wait_for(lambda: not self._targets, timeout=wait_timeout)
            remaining = tuple(self._targets.values())
        for target in remaining:
            task = target.task
            if task is not None:
                self._loop.call_soon_threadsafe(task.cancel)
        if remaining:
            with self._guard:
                self._guard.wait_for(lambda: not self._targets, timeout=2)
        finalize_error: BaseException | None = None
        if finalize is not None and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(finalize(), self._loop)
                future.result(timeout=wait_timeout)
            except BaseException as exc:
                finalize_error = exc
        with self._guard:
            if self._state is _ExecutorState.CLOSED:
                already_closed = True
            else:
                self._state = _ExecutorState.CLOSED
                already_closed = False
        if not already_closed:
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2)
        if finalize_error is not None:
            raise finalize_error

    @property
    def active_target_count(self) -> int:
        """Return the number of carriers without cleanup acknowledgement."""

        with self._guard:
            return len(self._targets)

    def _admit(
        self,
        *,
        kind: str,
        owner_id: str,
        session: ConversationTarget,
        request: TurnRequest,
        sink: TopLevelCompletionSink | None = None,
        result_future: concurrent.futures.Future[TurnResult] | None = None,
    ) -> _Target:
        context = contextvars.copy_context()
        token = TargetToken(
            token_id=ids.make_event_id(),
            kind=kind,
            owner_id=owner_id,
        )
        target = _Target(
            token=token,
            session=session,
            request=request,
            sink=sink,
            result_future=result_future,
            cleanup_ack=threading.Event(),
        )
        with self._guard:
            if self._state is not _ExecutorState.OPEN:
                raise ExecutorClosedError(
                    "executor is shutting down; no new targets are accepted"
                )
            if sink is not None:
                sink.bind_target(token)
            self._targets[token.token_id] = target
            self._loop.call_soon_threadsafe(self._schedule_target, target, context)
        return target

    def _admit_lifecycle(
        self,
        owner_id: str,
        operation: Callable[[], Awaitable[Any]],
    ) -> concurrent.futures.Future[Any]:
        context = contextvars.copy_context()
        token = TargetToken(
            token_id=ids.make_event_id(),
            kind="lifecycle",
            owner_id=owner_id,
        )
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        target = _LifecycleTarget(
            token=token,
            operation=operation,
            result_future=future,
            cleanup_ack=threading.Event(),
        )
        with self._guard:
            if self._state is not _ExecutorState.OPEN:
                raise ExecutorClosedError(
                    "executor is shutting down; no new targets are accepted"
                )
            self._targets[token.token_id] = target
            self._loop.call_soon_threadsafe(self._schedule_lifecycle, target, context)
        return future

    def _schedule_target(self, target: _Target, context: contextvars.Context) -> None:
        task = self._loop.create_task(
            self._run_target(target),
            context=context,
            name=f"{target.token.kind}-{target.token.owner_id}",
        )
        with self._guard:
            target.task = task
            cancel_requested = target.cancel_requested
        if cancel_requested:
            self._schedule_cancel(target)

    def _schedule_lifecycle(
        self,
        target: _LifecycleTarget,
        context: contextvars.Context,
    ) -> None:
        task = self._loop.create_task(
            self._run_lifecycle(target),
            context=context,
            name=f"lifecycle-{target.token.owner_id}",
        )
        with self._guard:
            target.task = task
            cancel_requested = target.cancel_requested
        if cancel_requested:
            self._schedule_cancel(target)

    def _schedule_cancel(
        self,
        target: _Target | _LifecycleTarget,
        force: bool = False,
    ) -> None:
        task = target.task
        if task is None or task.done():
            return
        if force or self._cancel_grace_seconds == 0:
            task.cancel()
            return
        self._loop.create_task(self._cancel_after_grace(target))

    async def _cancel_after_grace(self, target: _Target | _LifecycleTarget) -> None:
        await asyncio.sleep(self._cancel_grace_seconds)
        task = target.task
        if task is not None and not task.done():
            task.cancel()

    async def _run_target(self, target: _Target) -> None:
        result: TurnResult | None = None
        error: BaseException | None = None
        cancelled = False
        try:
            started = getattr(target.sink, "started", None)
            if callable(started):
                started(target.token)
            result = await target.session.submit_turn(target.request)
            future = target.result_future
            if future is not None and not future.done():
                future.set_result(result)
        except asyncio.CancelledError as exc:
            error = exc
            cancelled = True
            future = target.result_future
            if future is not None and not future.done():
                future.cancel()
        except BaseException as exc:  # noqa: BLE001
            error = exc
            future = target.result_future
            if future is not None and not future.done():
                future.set_exception(exc)
        finally:
            completion = TargetCompletion(
                token=target.token,
                result=result,
                error=error,
                cancelled=cancelled,
            )
            with self._guard:
                self._targets.pop(target.token.token_id, None)
                target.cleanup_ack.set()
                self._guard.notify_all()
            if target.sink is not None:
                try:
                    target.sink.complete(completion)
                except Exception:
                    pass

    async def _run_lifecycle(self, target: _LifecycleTarget) -> None:
        try:
            result = await target.operation()
            if not target.result_future.done():
                target.result_future.set_result(result)
        except asyncio.CancelledError:
            if not target.result_future.done():
                target.result_future.cancel()
        except BaseException as exc:  # noqa: BLE001
            if not target.result_future.done():
                target.result_future.set_exception(exc)
        finally:
            with self._guard:
                self._targets.pop(target.token.token_id, None)
                target.cleanup_ack.set()
                self._guard.notify_all()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self._loop.close()
