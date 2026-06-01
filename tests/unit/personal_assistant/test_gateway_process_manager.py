"""Unit tests for GatewayProcessManager and GatewayRuntime startup/shutdown lifecycle."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.main import (
    GatewayProcessManager,
    GatewayRuntime,
)

from ._main_helpers import (
    _FakeChannel,
    _FakeHeartbeatRunner,
    _FakeIMManager,
    _FakeKernelClient,
    _FakeProcess,
    _FakeProcessManager,
    build_config,
)


def test_gateway_process_manager_waits_for_kernel_health(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    client = _FakeKernelClient([RuntimeError("not ready"), {"healthy": True}])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: 0.0 if client.calls == 0 else 0.05 * client.calls,
        sleep=lambda _: None,
    )

    manager.start_kernel_process()

    assert client.calls == 2
    assert manager.process is process


def test_gateway_process_manager_raises_when_health_never_becomes_ready(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    client = _FakeKernelClient(
        [RuntimeError("down"), RuntimeError("down"), RuntimeError("down")]
    )
    times = iter([0.0, 0.05, 0.15, 0.25])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: next(times),
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="kernel health check timed out"):
        manager.start_kernel_process()


def test_gateway_process_manager_shutdown_uses_kill_after_terminate_timeout(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    process = _FakeProcess(wait_result=TimeoutError())
    client = _FakeKernelClient([{"healthy": True}])
    manager = GatewayProcessManager(
        config=config.kernel,
        kernel_client=client,
        process_factory=lambda command: process,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    manager.start_kernel_process()

    manager.stop_kernel_process()

    assert process.terminate_called == 1
    assert process.kill_called == 1
    assert process.wait_calls == [0.1]


def test_gateway_runtime_keeps_running_until_shutdown_requested(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    events: list[str] = []
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        channel_registry=ChannelRegistry([_FakeChannel(events)]),
        heartbeat_runner=_FakeHeartbeatRunner(events),
        im_connection_manager=_FakeIMManager(events),
        post_im_connect=lambda: events.append("im.bootstrap"),
    )
    outcome: dict[str, int] = {}
    thread = threading.Thread(
        target=lambda: outcome.setdefault("exit_code", runtime.run_forever()),
        daemon=True,
    )

    thread.start()

    assert runtime.wait_until_ready(timeout=1.0) is True
    assert thread.is_alive() is True
    deadline = time.time() + 1.0
    while "im.bootstrap" not in events and time.time() < deadline:
        time.sleep(0.01)
    # feat-393 fix-r1: heartbeat must start AFTER im.connect so the kernel_event_observer
    # sees manager.connected=True on the very first heartbeat tick.  Starting before
    # connect_once means any heartbeat run that completes before the WS is established
    # finds connected=False and silently skips IM delivery (verified by debug log).
    assert events[:5] == [
        "kernel.start",
        "channel.start:web_relay",
        "im.connect",
        "im.bootstrap",
        "heartbeat.start",
    ]

    runtime.request_shutdown()
    thread.join(timeout=1.0)

    assert outcome == {"exit_code": 0}
    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "im.connect",
        "im.bootstrap",
        "heartbeat.start",
        "heartbeat.stop",
        "channel.stop:web_relay",
        "im.close",
        "kernel.stop",
    ]


def test_gateway_runtime_cleans_up_reverse_order_when_im_start_fails(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    events: list[str] = []
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        channel_registry=ChannelRegistry([_FakeChannel(events)]),
        heartbeat_runner=_FakeHeartbeatRunner(events),
        im_connection_manager=_FakeIMManager(events, fail_connect=True),
    )

    with pytest.raises(RuntimeError, match="im offline"):
        runtime.run_forever()

    # feat-393 fix-r1: heartbeat starts after im.connect attempt; if im.connect fails,
    # heartbeat was never started so only cleanup for channels/kernel is needed.
    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "im.connect",
        "channel.stop:web_relay",
        "kernel.stop",
    ]
