"""bugfix-446-M1: GatewayRuntime-level connection resilience.

Covers the watchdog that rebuilds the IM maintenance loop when it exits abnormally
without shutdown (decision 1), startup-order-insensitivity now that the eager
connect_once is gone (decision 3), and the heartbeat first-connect gate that keeps
the feat-393 delivery invariant after the eager connect is removed.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import GatewayRuntime
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

from ._im_connection_helpers import _connect_fake, _minimal_reporter

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(LLMModelPayload(name="kimiCoding:K2.6"),),
        ),
    ),
)


def _make_config(tmp_path: Path) -> LocalConfig:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir(exist_ok=True)
    return LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )


def _run_in_thread(runtime: GatewayRuntime) -> tuple[threading.Thread, dict]:
    outcome: dict = {}

    def _target() -> None:
        try:
            outcome["exit_code"] = runtime.run_forever()
        except BaseException as exc:  # noqa: BLE001 — capture for assertion
            outcome["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return thread, outcome


class _CrashingIMManager:
    """run_forever raises a transient error N times before settling, so the watchdog
    has to rebuild it; records every entry so the test can count rebuilds."""

    def __init__(self, events: list[str], *, crash_times: int) -> None:
        self._events = events
        self._crash_times = crash_times
        self._calls = 0
        self._closed = asyncio.Event()
        self.connected = False

    async def connect_once(self) -> None:  # old-code compat (eager connect path)
        self._events.append("im.connect.eager")

    async def run_forever(self) -> None:
        self._calls += 1
        n = self._calls
        self._events.append(f"run_forever:{n}")
        if n <= self._crash_times:
            raise RuntimeError(f"transient crash {n}")
        self.connected = True
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        return

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
        self._closed.set()


def test_watchdog_rebuilds_im_loop_after_abnormal_exit(tmp_path: Path) -> None:
    """When run_forever exits abnormally (crash or silent return) without shutdown, the
    watchdog must rebuild it — and the crash must never propagate out of the gateway
    (issue path 3 / 'silent death'). Verified by run_forever being entered 3 times
    (2 crashes + 1 stable) and a clean exit 0."""
    events: list[str] = []
    config = _make_config(tmp_path)
    manager = _CrashingIMManager(events, crash_times=2)
    runtime = GatewayRuntime(
        config,
        None,
        im_connection_manager=manager,
        im_watchdog_initial_seconds=0.01,
        im_watchdog_max_seconds=0.02,
    )

    thread, outcome = _run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
        # Wait for the stable (3rd) entry: 2 crashes rebuilt + 1 that blocks.
        deadline = time.time() + 5.0
        while "run_forever:3" not in events and time.time() < deadline:
            time.sleep(0.02)
        assert "run_forever:3" in events, (
            f"watchdog did not rebuild the loop after abnormal exit; events={events}"
        )
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert "error" not in outcome, f"crash leaked out of gateway: {outcome.get('error')}"
    assert outcome.get("exit_code") == 0
    assert events.count("run_forever:1") == 1
    assert events.count("run_forever:2") == 1


def test_gateway_survives_unreachable_im_at_startup(tmp_path: Path) -> None:
    """Startup-order-insensitive (decision 3): with the eager connect_once gone, a real
    IMConnectionManager whose connect always fails must NOT crash the gateway. The
    gateway reaches ready and shuts down cleanly with exit 0 (it keeps retrying in the
    background). This inverts the old fail-fast contract."""
    events: list[str] = []
    config = _make_config(tmp_path)
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        raise RuntimeError("offline")

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=0.01,
            reconnect_max_seconds=0.02,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=_connect,
    )
    runtime = GatewayRuntime(config, None, im_connection_manager=manager)

    thread, outcome = _run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
        # Give the background loop time to fail several connects without crashing.
        time.sleep(0.2)
        assert thread.is_alive() is True
        assert "error" not in outcome
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0, (
        f"gateway must survive unreachable IM at startup; outcome={outcome}, events={events}"
    )


class _GateFakeIM:
    """run_forever resolves the first-connect signal only after a delay; the heartbeat
    startup must wait for that resolution before its first tick (feat-393 guard)."""

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()
        self._resolved = asyncio.Event()
        self.connected = False

    async def connect_once(self) -> None:  # old-code compat (eager connect path)
        self._events.append("im.connect.eager")

    async def run_forever(self) -> None:
        await asyncio.sleep(0.05)
        self.connected = True
        self._events.append("im.connect.resolved")
        self._resolved.set()
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        try:
            await asyncio.wait_for(self._resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    async def close(self) -> None:
        self._events.append("im.close")
        self._closed.set()


class _RecordingHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.close")


def test_heartbeat_start_waits_for_first_connect_attempt(tmp_path: Path) -> None:
    """feat-393 guard: heartbeat startup must wait until the first connect attempt has
    resolved, so the first tick never fires before the handshake. Verified by ordering:
    im.connect.resolved precedes heartbeat.start."""
    events: list[str] = []
    config = _make_config(tmp_path)
    manager = _GateFakeIM(events)
    heartbeat = _RecordingHeartbeatRunner(events)
    runtime = GatewayRuntime(
        config,
        None,
        im_connection_manager=manager,
        heartbeat_runner=heartbeat,
    )

    thread, outcome = _run_in_thread(runtime)
    try:
        deadline = time.time() + 3.0
        while "heartbeat.start" not in events and time.time() < deadline:
            time.sleep(0.01)
        assert "heartbeat.start" in events, f"heartbeat never started; events={events}"
        assert "im.connect.resolved" in events
        assert events.index("im.connect.resolved") < events.index("heartbeat.start"), (
            f"heartbeat must start only after the first connect attempt resolved; "
            f"events={events}"
        )
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0
