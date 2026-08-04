"""Process and IPC behavior tests for the Feishu listener worker."""

from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import threading
import time
from types import SimpleNamespace

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


def _process_birth(pid: int) -> str | None:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    birth = " ".join(result.stdout.split())
    return birth or None


def _abrupt_listener_owner(worker_info, exit_owner) -> None:
    runtime = _runtime(target=_listener_worker, events=[], statuses=[])
    runtime.start()
    worker_info.send((runtime.pid, _process_birth(runtime.pid)))
    exit_owner.wait()
    os._exit(23)


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


def test_listener_exits_when_its_owner_dies_without_cleanup() -> None:
    """A listener cannot survive the Gateway process that created it."""
    mp = multiprocessing.get_context("spawn")
    worker_info_recv, worker_info_send = mp.Pipe(duplex=False)
    exit_owner = mp.Event()
    owner = mp.Process(
        target=_abrupt_listener_owner,
        args=(worker_info_send, exit_owner),
    )
    worker_pid: int | None = None
    worker_birth: str | None = None

    try:
        owner.start()
        assert worker_info_recv.poll(10), "owner did not report its listener"
        worker_pid, worker_birth = worker_info_recv.recv()
        assert worker_birth is not None

        exit_owner.set()
        owner.join(3)
        assert owner.exitcode == 23
        _wait_until(lambda: _process_birth(worker_pid) != worker_birth)
    finally:
        if owner.is_alive():
            owner.terminate()
            owner.join(1)
        if (
            worker_pid is not None
            and worker_birth is not None
            and _process_birth(worker_pid) == worker_birth
        ):
            os.kill(worker_pid, signal.SIGKILL)
            _wait_until(lambda: _process_birth(worker_pid) != worker_birth)
        worker_info_recv.close()
        worker_info_send.close()


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
    _wait_until(
        lambda: any(item.status_code == "event_backpressure" for item in statuses)
    )
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


def test_sdk_worker_suppresses_sensitive_websocket_url_info_log(monkeypatch) -> None:
    """The SDK must not log access_key/ticket query values at INFO."""
    from lark_oapi.core.enum import LogLevel
    from personal_assistant.channels.feishu.client import _run_feishu_sdk_worker

    captured: dict[str, object] = {}

    class FakeWSClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.on_reconnecting = lambda: None
            self.on_reconnected = lambda: None

        async def _connect(self) -> None:
            return None

        def start(self) -> None:
            return None

    monkeypatch.setattr(
        "personal_assistant.channels.feishu.client.WSClient", FakeWSClient
    )
    monkeypatch.setattr(
        "personal_assistant.channels.feishu.client.publish_status",
        lambda *_args, **_kwargs: None,
    )
    _run_feishu_sdk_worker(
        SimpleNamespace(
            app_id="cli_sensitive",
            app_secret="secret",
            domain="https://open.feishu.cn",
        )
    )

    assert captured["log_level"] is LogLevel.WARNING
