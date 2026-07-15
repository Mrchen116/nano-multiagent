"""Process and IPC behavior tests for the Feishu listener worker."""

from __future__ import annotations

import multiprocessing
import os
import threading
import time

from personal_assistant.channels.feishu.worker import (
    FeishuWorkerProcessContext,
    FeishuWorkerRuntime,
    publish_event,
    publish_priority_status,
    publish_status,
    request_card_action,
)


def _wait_until(predicate, *, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def _listener_worker(context: FeishuWorkerProcessContext) -> None:
    publish_status(context, connection_state="connecting")
    publish_event(context, {"app_id": context.app_id, "index": 0})
    while not context.stop_event.wait(0.01):
        pass


def _pressure_worker(context: FeishuWorkerProcessContext) -> None:
    publish_status(context, connection_state="connecting")
    publish_status(context, connection_state="reconnecting")
    publish_priority_status(
        context,
        connection_state="connected",
        status_sequence=2,
    )
    for index in range(4):
        if not publish_event(context, {"index": index}, timeout=0.05):
            return
    while not context.stop_event.wait(0.01):
        pass


def _drain_worker(context: FeishuWorkerProcessContext) -> None:
    for index in range(3):
        publish_event(context, {"index": index}, timeout=1)
    while not context.stop_event.wait(0.01):
        pass


def _card_worker(context: FeishuWorkerProcessContext) -> None:
    result = request_card_action(
        context,
        {"approval_id": "approval-1", "decision": "allow_once"},
        timeout=0.5,
    )
    publish_event(context, {"card_result": result}, timeout=1)
    while not context.stop_event.wait(0.01):
        pass


def _crash_worker(_context: FeishuWorkerProcessContext) -> None:
    os._exit(17)


def _runtime(*, target, events, statuses, **kwargs) -> FeishuWorkerRuntime:
    return FeishuWorkerRuntime(
        app_id=kwargs.pop("app_id", "cli_a"),
        app_secret="secret",
        incarnation=kwargs.pop("incarnation", "inc-a"),
        on_event=events.append,
        on_status=statuses.append,
        worker_target=target,
        multiprocessing_context=multiprocessing.get_context("spawn"),
        join_timeout=1,
        **kwargs,
    )


def test_two_listener_processes_are_isolated_and_true_stop_join() -> None:
    """Each app owns one live process and both are fully reaped on stop."""
    events_a, events_b, statuses = [], [], []
    runtime_a = _runtime(
        target=_listener_worker,
        events=events_a,
        statuses=statuses,
        app_id="cli_a",
        incarnation="inc-a",
    )
    runtime_b = _runtime(
        target=_listener_worker,
        events=events_b,
        statuses=statuses,
        app_id="cli_b",
        incarnation="inc-b",
    )
    runtime_a.start()
    runtime_b.start()
    _wait_until(lambda: events_a and events_b)

    assert runtime_a.pid != runtime_b.pid
    assert events_a == [{"app_id": "cli_a", "index": 0}]
    assert events_b == [{"app_id": "cli_b", "index": 0}]
    report_a = runtime_a.stop(drain=True)
    report_b = runtime_b.stop(drain=True)
    assert report_a.joined and report_b.joined
    assert not report_a.terminated and not report_b.terminated
    assert runtime_a.is_alive is False and runtime_b.is_alive is False


def test_backpressure_status_coalescing_and_priority_error_are_visible() -> None:
    """A full FIFO fails visibly while the independent status lane remains ordered."""
    entered = threading.Event()
    release = threading.Event()
    events, statuses = [], []

    def slow_event(payload) -> None:
        events.append(payload)
        if payload["index"] == 0:
            entered.set()
            release.wait(2)

    runtime = FeishuWorkerRuntime(
        app_id="cli_pressure",
        app_secret="secret",
        incarnation="inc-pressure",
        on_event=slow_event,
        on_status=statuses.append,
        worker_target=_pressure_worker,
        multiprocessing_context=multiprocessing.get_context("spawn"),
        event_queue_capacity=1,
        join_timeout=1,
    )
    runtime.start()
    assert entered.wait(2)
    _wait_until(lambda: any(item.status_code == "event_backpressure" for item in statuses))
    release.set()
    report = runtime.stop(drain=True)

    assert report.joined
    assert [item["index"] for item in events] == sorted(
        item["index"] for item in events
    )
    sequences = [item.status_sequence for item in statuses]
    assert sequences == sorted(set(sequences))
    assert statuses[-1].connection_state == "failed"
    assert statuses[-1].status_code == "event_backpressure"


def test_stop_can_drain_or_drop_invalidated_generation() -> None:
    """Gateway shutdown drains, while replacement drops old-generation queued input."""
    drained, statuses = [], []
    graceful = _runtime(target=_drain_worker, events=drained, statuses=statuses)
    graceful.start()
    graceful_report = graceful.stop(drain=True)
    assert graceful_report.joined
    assert [item["index"] for item in drained] == [0, 1, 2]
    assert graceful_report.dropped_events == 0

    entered = threading.Event()
    release = threading.Event()
    delivered = []

    def blocked(payload) -> None:
        delivered.append(payload)
        entered.set()
        release.wait(2)

    invalidated = FeishuWorkerRuntime(
        app_id="cli_drop",
        app_secret="secret",
        incarnation="inc-drop",
        on_event=blocked,
        on_status=lambda _status: None,
        worker_target=_drain_worker,
        multiprocessing_context=multiprocessing.get_context("spawn"),
        event_queue_capacity=3,
        join_timeout=1,
    )
    invalidated.start()
    assert entered.wait(2)
    drop_report = invalidated.stop(drain=False)
    release.set()
    assert drop_report.joined
    assert drop_report.dropped_events >= 1
    assert len(delivered) == 1


def test_card_action_rpc_correlates_result_and_has_timeout_fallback() -> None:
    """Synchronous SDK callbacks receive a correlated card or deterministic retry."""
    events, statuses, requests = [], [], []

    def answer(request):
        requests.append(request)
        return {"header": {"template": "green"}, "request": request["approval_id"]}

    runtime = _runtime(
        target=_card_worker,
        events=events,
        statuses=statuses,
        on_card_action=answer,
    )
    runtime.start()
    _wait_until(lambda: events)
    runtime.stop(drain=True)
    assert requests == [{"approval_id": "approval-1", "decision": "allow_once"}]
    assert events[0]["card_result"]["request"] == "approval-1"

    timed_out = []

    def too_slow(_request):
        time.sleep(0.7)
        return {"late": True}

    timeout_runtime = _runtime(
        target=_card_worker,
        events=timed_out,
        statuses=[],
        on_card_action=too_slow,
    )
    timeout_runtime.start()
    _wait_until(lambda: timed_out, timeout=2)
    timeout_runtime.stop(drain=True)
    assert timed_out[0]["card_result"] == {
        "error": "temporarily_unavailable",
        "message": "Card action could not be processed; please retry.",
    }


def test_worker_crash_is_a_terminal_priority_status() -> None:
    """An abnormal listener exit is observable and leaves no live child."""
    statuses = []
    runtime = _runtime(target=_crash_worker, events=[], statuses=statuses)
    runtime.start()
    _wait_until(lambda: any(item.status_code == "worker_crashed" for item in statuses))
    report = runtime.stop(drain=False)
    assert report.joined
    assert runtime.is_alive is False
