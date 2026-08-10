"""Isolated process runtime for one Feishu SDK WebSocket listener."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import multiprocessing
from multiprocessing.connection import Connection, wait
import os
import queue
import threading
import time
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)

_CARD_ACTION_FALLBACK = {
    "error": "temporarily_unavailable",
    "message": "Card action could not be processed; please retry.",
}


@dataclass(slots=True)
class FeishuWorkerProcessContext:
    """Pickle-safe child process access to the bounded IPC lanes."""

    app_id: str
    app_secret: str
    domain: str
    incarnation: str
    event_queue: Any
    status_mailbox: Any
    priority_send: Connection
    action_connection: Connection
    stop_event: Any
    ready_event: Any
    status_counter: Any


@dataclass(frozen=True, slots=True)
class FeishuWorkerStatus:
    """One incarnation/sequence ordered listener status frame."""

    runtime_incarnation: str
    status_sequence: int
    connection_state: str
    diagnostics_state: str = "unknown"
    status_code: str | None = None
    status_message: str | None = None
    checks: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class FeishuWorkerStopReport:
    """Observable child-process and queue cleanup result."""

    joined: bool
    terminated: bool
    dropped_events: int


def _next_status_sequence(context: FeishuWorkerProcessContext) -> int:
    with context.status_counter.get_lock():
        context.status_counter.value += 1
        return int(context.status_counter.value)


def _status_frame(
    context: FeishuWorkerProcessContext,
    *,
    connection_state: str,
    diagnostics_state: str = "unknown",
    status_code: str | None = None,
    status_message: str | None = None,
    status_sequence: int | None = None,
) -> dict[str, object]:
    return {
        "kind": "status",
        "runtime_incarnation": context.incarnation,
        "status_sequence": status_sequence
        if status_sequence is not None
        else _next_status_sequence(context),
        "connection_state": connection_state,
        "diagnostics_state": diagnostics_state,
        "status_code": status_code,
        "status_message": status_message,
    }


def publish_status(
    context: FeishuWorkerProcessContext,
    *,
    connection_state: str,
    diagnostics_state: str = "unknown",
    status_code: str | None = None,
    status_message: str | None = None,
) -> None:
    """Write a coalescible latest-value non-terminal status."""
    frame = _status_frame(
        context,
        connection_state=connection_state,
        diagnostics_state=diagnostics_state,
        status_code=status_code,
        status_message=status_message,
    )
    try:
        context.status_mailbox.put_nowait(frame)
    except queue.Full:
        try:
            context.status_mailbox.get_nowait()
        except queue.Empty:
            pass
        try:
            context.status_mailbox.put_nowait(frame)
        except queue.Full:
            pass


def publish_priority_status(
    context: FeishuWorkerProcessContext,
    *,
    connection_state: str,
    diagnostics_state: str = "unknown",
    status_code: str | None = None,
    status_message: str | None = None,
    status_sequence: int | None = None,
) -> None:
    """Send terminal/error status independently from bounded message traffic."""
    context.priority_send.send(
        _status_frame(
            context,
            connection_state=connection_state,
            diagnostics_state=diagnostics_state,
            status_code=status_code,
            status_message=status_message,
            status_sequence=status_sequence,
        )
    )


def publish_event(
    context: FeishuWorkerProcessContext, payload: object, *, timeout: float = 2.0
) -> bool:
    """Put one user event in FIFO order or fail the worker visibly on saturation."""
    try:
        context.event_queue.put(payload, timeout=timeout)
        return True
    except queue.Full:
        publish_priority_status(
            context,
            connection_state="failed",
            status_code="event_backpressure",
            status_message="Inbound event queue is full.",
        )
        context.stop_event.set()
        return False


def request_card_action(
    context: FeishuWorkerProcessContext,
    payload: object,
    *,
    timeout: float = 3.0,
) -> dict[str, object]:
    """Round-trip one synchronous SDK card callback over a correlated duplex pipe."""
    request_id = uuid4().hex
    deadline = time.monotonic() + timeout
    try:
        context.action_connection.send(
            {
                "kind": "card_action.request",
                "request_id": request_id,
                "deadline": deadline,
                "payload": payload,
            }
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not context.action_connection.poll(remaining):
                return dict(_CARD_ACTION_FALLBACK)
            frame = context.action_connection.recv()
            if (
                isinstance(frame, dict)
                and frame.get("kind") == "card_action.result"
                and frame.get("request_id") == request_id
                and isinstance(frame.get("payload"), dict)
            ):
                return dict(frame["payload"])
    except (EOFError, OSError):
        return dict(_CARD_ACTION_FALLBACK)


def _default_worker_target(context: FeishuWorkerProcessContext) -> None:
    from personal_assistant.channels.feishu.client import _run_feishu_sdk_worker

    _run_feishu_sdk_worker(context)


def _exit_when_parent_terminates(parent_sentinel: int) -> None:
    wait([parent_sentinel])
    os._exit(0)


def _worker_bootstrap(
    target: Callable[[FeishuWorkerProcessContext], None],
    context: FeishuWorkerProcessContext,
) -> None:
    try:
        parent = multiprocessing.parent_process()
        if parent is None:
            raise RuntimeError("feishu worker has no multiprocessing parent")
        threading.Thread(
            target=_exit_when_parent_terminates,
            args=(parent.sentinel,),
            name="feishu-parent-liveness",
            daemon=True,
        ).start()
        context.ready_event.set()
        target(context)
    except BaseException:
        try:
            publish_priority_status(
                context,
                connection_state="failed",
                status_code="worker_crashed",
                status_message="Feishu listener process exited unexpectedly.",
            )
        except (BrokenPipeError, EOFError, OSError):
            pass
        raise


class FeishuWorkerRuntime:
    """Parent-side owner of process, bounded queues, RPC, and ordered status."""

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        incarnation: str,
        on_event: Callable[[object], None],
        on_status: Callable[[FeishuWorkerStatus], None],
        on_card_action: Callable[[object], dict[str, object] | None] | None = None,
        domain: str = "https://open.feishu.cn",
        event_queue_capacity: int = 128,
        join_timeout: float = 2.0,
        startup_timeout: float = 30.0,
        drain_timeout: float = 5.0,
        worker_target: Callable[[FeishuWorkerProcessContext], None] | None = None,
        multiprocessing_context: Any | None = None,
    ) -> None:
        self._mp = multiprocessing_context or multiprocessing.get_context("spawn")
        self._event_queue = self._mp.Queue(maxsize=max(1, event_queue_capacity))
        self._status_mailbox = self._mp.Queue(maxsize=1)
        priority_recv, priority_send = self._mp.Pipe(duplex=False)
        parent_action, child_action = self._mp.Pipe(duplex=True)
        self._priority_recv = priority_recv
        self._parent_action = parent_action
        self._stop_event = self._mp.Event()
        self._ready_event = self._mp.Event()
        self._status_counter = self._mp.Value("Q", 1)
        context = FeishuWorkerProcessContext(
            app_id=app_id,
            app_secret=app_secret,
            domain=domain,
            incarnation=incarnation,
            event_queue=self._event_queue,
            status_mailbox=self._status_mailbox,
            priority_send=priority_send,
            action_connection=child_action,
            stop_event=self._stop_event,
            ready_event=self._ready_event,
            status_counter=self._status_counter,
        )
        self._process = self._mp.Process(
            target=_worker_bootstrap,
            args=(worker_target or _default_worker_target, context),
            name=f"feishu-worker-{app_id[:8]}",
            daemon=False,
        )
        self._incarnation = incarnation
        self._on_event = on_event
        self._on_status = on_status
        self._on_card_action = on_card_action
        self._join_timeout = join_timeout
        self._startup_timeout = startup_timeout
        self._drain_timeout = drain_timeout
        self._monitor_stop = threading.Event()
        self._accept_events = True
        self._stopping = False
        self._started = False
        self._last_status_sequence = 1
        self._dropped_events = 0
        self._event_inflight = 0
        self._event_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._threads: tuple[threading.Thread, ...] = ()

    @property
    def pid(self) -> int | None:
        """Return the child PID after start."""
        return self._process.pid

    @property
    def is_alive(self) -> bool:
        """Return whether the listener child still owns OS resources."""
        return self._process.is_alive() if self._started else False

    def start(self) -> None:
        """Start one listener process and independent event/control/RPC consumers."""
        with self._lifecycle_lock:
            if self._started:
                raise RuntimeError("feishu worker already started")
            self._process.start()
            self._started = True
            try:
                if not self._ready_event.wait(self._startup_timeout):
                    raise RuntimeError("feishu worker did not initialize")
                threads = (
                    threading.Thread(target=self._event_loop, daemon=True),
                    threading.Thread(target=self._status_loop, daemon=True),
                    threading.Thread(target=self._action_loop, daemon=True),
                )
                for thread in threads:
                    thread.start()
                    self._threads = (*self._threads, thread)
            except Exception:
                self._stop_started(drain=False)
                raise

    def stop(self, *, drain: bool) -> FeishuWorkerStopReport:
        """Drain shutdown traffic or drop an invalidated generation, then reap child."""
        with self._lifecycle_lock:
            return self._stop_started(drain=drain)

    def _stop_started(self, *, drain: bool) -> FeishuWorkerStopReport:
        if not self._started:
            return FeishuWorkerStopReport(True, False, 0)
        self._stopping = True
        self._accept_events = drain
        self._stop_event.set()
        self._process.join(self._join_timeout)
        terminated = False
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(self._join_timeout)
            terminated = True
        if self._process.is_alive():
            self._process.kill()
            self._process.join(self._join_timeout)
        if drain:
            deadline = time.monotonic() + self._drain_timeout
            quiet_since: float | None = None
            while time.monotonic() < deadline:
                with self._event_lock:
                    inflight = self._event_inflight
                if self._event_queue.empty() and inflight == 0:
                    quiet_since = quiet_since or time.monotonic()
                    if time.monotonic() - quiet_since >= 0.1:
                        break
                else:
                    quiet_since = None
                time.sleep(0.01)
        else:
            self._discard_queued_events()
        self._monitor_stop.set()
        for thread in self._threads:
            thread.join(timeout=0.1)
        self._priority_recv.close()
        self._parent_action.close()
        joined = not self._process.is_alive()
        if not joined:
            raise RuntimeError("feishu worker could not be reaped")
        self._process.close()
        self._started = False
        return FeishuWorkerStopReport(
            joined=joined,
            terminated=terminated,
            dropped_events=self._dropped_events,
        )

    def _event_loop(self) -> None:
        while not self._monitor_stop.is_set():
            try:
                payload = self._event_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if not self._accept_events:
                self._dropped_events += 1
                continue
            with self._event_lock:
                self._event_inflight += 1
            try:
                self._on_event(payload)
            except Exception:
                logger.exception("failed to consume Feishu worker event")
            finally:
                with self._event_lock:
                    self._event_inflight -= 1

    def _status_loop(self) -> None:
        crash_reported = False
        while not self._monitor_stop.is_set():
            if self._priority_recv.poll(0.02):
                try:
                    self._accept_status_frame(self._priority_recv.recv())
                except (EOFError, OSError):
                    pass
            try:
                self._accept_status_frame(self._status_mailbox.get_nowait())
            except queue.Empty:
                pass
            if (
                self._started
                and not self._stopping
                and not self._process.is_alive()
                and not self._stop_event.is_set()
                and not crash_reported
            ):
                crash_reported = True
                sequence = self._next_parent_sequence()
                self._accept_status_frame(
                    {
                        "kind": "status",
                        "runtime_incarnation": self._incarnation,
                        "status_sequence": sequence,
                        "connection_state": "failed",
                        "diagnostics_state": "unknown",
                        "status_code": "worker_crashed",
                        "status_message": "Feishu listener process exited unexpectedly.",
                    }
                )

    def _action_loop(self) -> None:
        while not self._monitor_stop.is_set():
            if not self._parent_action.poll(0.05):
                continue
            try:
                frame = self._parent_action.recv()
            except (EOFError, OSError):
                return
            if (
                not isinstance(frame, dict)
                or frame.get("kind") != "card_action.request"
            ):
                continue
            request_id = frame.get("request_id")
            deadline = frame.get("deadline")
            if not isinstance(request_id, str) or not isinstance(
                deadline, (int, float)
            ):
                continue
            if time.monotonic() >= deadline or self._on_card_action is None:
                response = dict(_CARD_ACTION_FALLBACK)
            else:
                try:
                    response = self._on_card_action(frame.get("payload"))
                    if not isinstance(response, dict):
                        response = dict(_CARD_ACTION_FALLBACK)
                except Exception:
                    logger.exception("Feishu card action handler failed")
                    response = dict(_CARD_ACTION_FALLBACK)
            if time.monotonic() >= deadline:
                continue
            try:
                self._parent_action.send(
                    {
                        "kind": "card_action.result",
                        "request_id": request_id,
                        "payload": response,
                    }
                )
            except (BrokenPipeError, EOFError, OSError):
                return

    def _accept_status_frame(self, frame: object) -> None:
        if not isinstance(frame, dict) or frame.get("kind") != "status":
            return
        if frame.get("runtime_incarnation") != self._incarnation:
            return
        sequence = frame.get("status_sequence")
        if not isinstance(sequence, int) or sequence <= self._last_status_sequence:
            return
        self._last_status_sequence = sequence
        self._on_status(
            FeishuWorkerStatus(
                runtime_incarnation=self._incarnation,
                status_sequence=sequence,
                connection_state=str(frame.get("connection_state") or "failed"),
                diagnostics_state=str(frame.get("diagnostics_state") or "unknown"),
                status_code=frame.get("status_code")
                if isinstance(frame.get("status_code"), str)
                else None,
                status_message=frame.get("status_message")
                if isinstance(frame.get("status_message"), str)
                else None,
            )
        )

    def _next_parent_sequence(self) -> int:
        with self._status_counter.get_lock():
            self._status_counter.value += 1
            return int(self._status_counter.value)

    def _discard_queued_events(self) -> None:
        while True:
            try:
                self._event_queue.get_nowait()
                self._dropped_events += 1
            except queue.Empty:
                return
