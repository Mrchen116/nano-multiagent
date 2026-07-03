"""Unit tests for GatewayProcessManager and GatewayRuntime startup/shutdown lifecycle."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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


class _SkillReviewKernel:
    def __init__(self) -> None:
        self.maintenance_roots: list[Path] = []
        self.drained = False
        self.created_sessions: list[dict[str, object]] = []
        self.submitted_parts: list[dict[str, object]] = []

    def run_skill_maintenance(self, *, workspace_root: Path) -> None:
        self.maintenance_roots.append(workspace_root)

    async def run_queued_skill_batch_reviews(self, *, run_background_analysis):
        self.drained = True
        await run_background_analysis(
            "review prompt",
            tool_allowlist=("skill_view", "skill_manage"),
            metadata={"background_task": "skill_batch_review"},
        )
        return (SimpleNamespace(completed=True),)

    async def create_session(self, **kwargs):
        self.created_sessions.append(dict(kwargs))
        return SimpleNamespace(session_id="skill-review-session")

    def submit(self, **kwargs):
        self.submitted_parts.append(dict(kwargs))
        return SimpleNamespace(run_id="run-1", status="queued")

    def get_run(self, run_id: str):
        return SimpleNamespace(run_id=run_id, status="completed")


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
    )
    outcome: dict[str, int] = {}
    thread = threading.Thread(
        target=lambda: outcome.setdefault("exit_code", runtime.run_forever()),
        daemon=True,
    )

    thread.start()

    try:
        assert runtime.wait_until_ready(timeout=1.0) is True
        assert thread.is_alive() is True
        # bugfix-446-M1: the eager connect_once + post_im_connect block is gone — the IM
        # connection is now owned by the supervised run_forever loop. Heartbeat startup
        # still waits for the first connect attempt to resolve before its first tick
        # (feat-393 guard), so heartbeat.start is the last startup event to land.
        deadline = time.time() + 1.0
        while "heartbeat.start" not in events and time.time() < deadline:
            time.sleep(0.01)
        assert events[:3] == [
            "kernel.start",
            "channel.start:web_relay",
            "heartbeat.start",
        ]
    finally:
        # Always request shutdown so run_forever returns and its asyncio.to_thread
        # wait()-worker (non-daemon) is released; otherwise a failed assertion above
        # would orphan that thread and hang the interpreter on exit.
        runtime.request_shutdown()
        thread.join(timeout=1.0)

    assert outcome == {"exit_code": 0}
    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "heartbeat.stop",
        "channel.stop:web_relay",
        "im.close",
        "kernel.stop",
    ]


def test_gateway_skill_maintenance_drains_queued_skill_batch_reviews(
    tmp_path: Path,
) -> None:
    config = build_config(tmp_path)
    kernel = _SkillReviewKernel()
    runtime = GatewayRuntime(config, None, kernel=kernel)

    asyncio.run(runtime._run_skill_maintenance())  # noqa: SLF001

    workspace_root = config.agents[0].workspace_root
    assert kernel.maintenance_roots == [workspace_root]
    assert kernel.drained is True
    assert kernel.created_sessions == [
        {
            "workspace_root": workspace_root,
            "enabled_tools": ["skill_view", "skill_manage"],
            "metadata": {"background_task": "skill_batch_review"},
        }
    ]
    assert kernel.submitted_parts == [
        {
            "session_id": "skill-review-session",
            "parts": [{"type": "text", "text": "review prompt"}],
            "workspace_root": workspace_root,
        }
    ]


# bugfix-446-M1: the old test_gateway_runtime_cleans_up_reverse_order_when_im_start_fails
# asserted that a failed initial IM connect crashes the gateway (fail-fast). That contract
# is intentionally inverted by decision 3 — startup is now order-insensitive — and the new
# behavior (gateway survives an unreachable IM at startup) is covered by
# test_gateway_runtime_watchdog.py::test_gateway_survives_unreachable_im_at_startup with a
# real IMConnectionManager.
