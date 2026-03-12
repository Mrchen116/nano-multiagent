from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import httpx
import pytest

from personal_assistant.config.local_store import HeartbeatConfig, KernelConfig, LocalConfig, NodeConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
from personal_assistant.main import (
    BackgroundLaunchResult,
    GatewayProcessManager,
    GatewayRuntime,
    RuntimeFactories,
    _IMBootstrapClient,
    _build_relay_lifecycle_callback,
    launch_gateway_in_background,
    main,
    run_gateway,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter


class _FakeKernelClient:
    def __init__(self, health_results: list[dict[str, object] | Exception]) -> None:
        self.health_results = list(health_results)
        self.calls = 0

    def health(self) -> dict[str, object]:
        self.calls += 1
        outcome = self.health_results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeProcess:
    def __init__(self, wait_result: int | TimeoutError, *, pid: int = 4321, poll_result: int | None = None) -> None:
        self.wait_result = wait_result
        self.pid = pid
        self.poll_result = poll_result
        self.terminate_called = 0
        self.kill_called = 0
        self.wait_calls: list[float] = []

    def poll(self) -> int | None:
        return self.poll_result

    def terminate(self) -> None:
        self.terminate_called += 1

    def kill(self) -> None:
        self.kill_called += 1

    def wait(self, timeout: float) -> int:
        self.wait_calls.append(timeout)
        if isinstance(self.wait_result, TimeoutError):
            raise self.wait_result
        return self.wait_result


class _FakeProcessManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def start_kernel_process(self) -> None:
        self._events.append("kernel.start")

    def stop_kernel_process(self) -> None:
        self._events.append("kernel.stop")


class _FakeChannel:
    def __init__(self, events: list[str], *, name: str = "web_relay") -> None:
        self.name = name
        self._events = events

    def start(self, on_inbound) -> None:  # noqa: ANN001
        self._events.append(f"channel.start:{self.name}")

    def send(self, outbound) -> None:  # noqa: ANN001
        return None

    def stop(self) -> None:
        self._events.append(f"channel.stop:{self.name}")


class _FakeHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.stop")


class _FakeIMManager:
    def __init__(self, events: list[str], *, fail_connect: bool = False) -> None:
        self._events = events
        self._fail_connect = fail_connect
        self._closed = asyncio.Event()
        self.connected = True
        self.sent_frames: list[tuple[str, dict[str, object]]] = []

    async def connect_once(self) -> None:
        self._events.append("im.connect")
        if self._fail_connect:
            raise RuntimeError("im offline")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
        self._closed.set()

    async def send_json(self, message_type: str, payload: dict[str, object]) -> None:
        self.sent_frames.append((message_type, payload))


def _build_config(tmp_path: Path) -> LocalConfig:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    return LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(),
        channels=(),
        kernel=KernelConfig(
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )


def test_gateway_process_manager_waits_for_kernel_health(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
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


def test_gateway_process_manager_raises_when_health_never_becomes_ready(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0)
    client = _FakeKernelClient([RuntimeError("down"), RuntimeError("down"), RuntimeError("down")])
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


def test_gateway_process_manager_shutdown_uses_kill_after_terminate_timeout(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
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
    config = _build_config(tmp_path)
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
    thread = threading.Thread(target=lambda: outcome.setdefault("exit_code", runtime.run_forever()), daemon=True)

    thread.start()

    assert runtime.wait_until_ready(timeout=1.0) is True
    assert thread.is_alive() is True
    assert events[:5] == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "im.connect",
        "im.bootstrap",
    ]

    runtime.request_shutdown()
    thread.join(timeout=1.0)

    assert outcome == {"exit_code": 0}
    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "im.connect",
        "im.bootstrap",
        "heartbeat.stop",
        "channel.stop:web_relay",
        "im.close",
        "kernel.stop",
    ]


def test_gateway_runtime_cleans_up_reverse_order_when_im_start_fails(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
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

    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "im.connect",
        "heartbeat.stop",
        "channel.stop:web_relay",
        "kernel.stop",
    ]


def test_relay_lifecycle_callback_sends_receipts_and_report_to_im() -> None:
    reporter = UpstreamReporter(node=NodeConfig(node_id="node-local"), agents=(), send_frame=lambda _t, _p: None)
    manager = _FakeIMManager([])
    callback = _build_relay_lifecycle_callback(
        reporter=reporter,
        im_connection_manager_factory=lambda: manager,
    )
    message = type("_Message", (), {})()
    message.external_chat_id = "conv-1"
    message.metadata = {"relay_task_id": "relay-1", "message_id": "msg-1"}

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(phase="accepted", agent_id="agent-a", session_key="web:user:agent-a", run_id="run-1"),
        )
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="running",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
            ),
        )
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
            ),
        )

    asyncio.run(_exercise())

    assert [item[0] for item in manager.sent_frames] == [
        "node.delivery_receipt",
        "node.report",
        "node.delivery_receipt",
    ]
    assert manager.sent_frames[0][1]["delivery_status"] == "sent"
    assert manager.sent_frames[1][1]["conversation_id"] == "conv-1"
    assert manager.sent_frames[1][1]["message_id"] == "msg-1"
    assert manager.sent_frames[2][1]["detail"] == "hello from agent"


def test_run_gateway_loads_config_and_starts_runtime(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    seen: dict[str, object] = {}

    class _Runtime:
        def __init__(self, loaded_config: LocalConfig) -> None:
            seen["config"] = loaded_config

        def run_forever(self) -> int:
            seen["ran"] = True
            return 0

    exit_code = run_gateway(
        config_path=tmp_path / "node-config.yaml",
        factories=RuntimeFactories(
            load_config=lambda path: config if path == tmp_path / "node-config.yaml" else None,
            build_runtime=lambda loaded_config: _Runtime(loaded_config),
        ),
    )

    assert exit_code == 0
    assert seen == {"config": config, "ran": True}


def test_im_bootstrap_client_opens_browser_for_unbound_node() -> None:
    opened: list[tuple[str, int, bool]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/im/v1/nodes":
            return httpx.Response(200, json=[{"node_id": "node-local", "owner_id": ""}])
        if request.method == "POST" and request.url.path == "/im/v1/bind":
            return httpx.Response(201, json={"bind_url": "http://127.0.0.1:4173/bind/confirm?token=t-1"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    bootstrap = _IMBootstrapClient(
        base_url="http://im.local",
        token=None,
        client=client,
        browser_opener=lambda url, new=0, autoraise=True: opened.append((url, new, autoraise)) or True,
    )

    bind_url = bootstrap.ensure_node_binding(node_id="node-local")

    assert bind_url == "http://127.0.0.1:4173/bind/confirm?token=t-1"
    assert opened == [("http://127.0.0.1:4173/bind/confirm?token=t-1", 2, True)]


def test_im_bootstrap_client_skips_browser_for_bound_node() -> None:
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path == "/im/v1/nodes":
            return httpx.Response(200, json=[{"node_id": "node-local", "owner_id": "owner-1"}])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    bootstrap = _IMBootstrapClient(
        base_url="http://im.local",
        token=None,
        client=client,
        browser_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("browser should not open")),
    )

    bind_url = bootstrap.ensure_node_binding(node_id="node-local")

    assert bind_url is None
    assert calls == ["GET /im/v1/nodes"]


def test_launch_gateway_in_background_spawns_foreground_child_and_waits_for_ready(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)
    seen: dict[str, object] = {}

    def _spawn_process(argv: list[str], log_path: Path) -> _FakeProcess:
        seen["spawn"] = (argv, log_path)
        return process

    def _wait_for_ready(child: _FakeProcess, loaded_config: LocalConfig, timeout_seconds: float) -> None:
        seen["wait"] = (child, loaded_config, timeout_seconds)

    result = launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda path: config if path == config.source_path else None,
        spawn_process=_spawn_process,
        wait_for_ready=_wait_for_ready,
    )

    assert result == BackgroundLaunchResult(
        pid=2468,
        health_url=f"{config.kernel.base_url}{config.kernel.health_path}",
        log_path=config.source_path.parent / "gateway.log",
    )
    assert seen["spawn"] == (
        [
            sys.executable,
            "-m",
            "personal_assistant.main",
            "--config",
            str(config.source_path),
            "--foreground",
        ],
        config.source_path.parent / "gateway.log",
    )
    assert seen["wait"] == (process, config, config.kernel.startup_timeout_seconds)


def test_launch_gateway_in_background_stops_child_when_ready_wait_fails(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0)

    with pytest.raises(RuntimeError, match="not ready"):
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
            spawn_process=lambda _argv, _log_path: process,
            wait_for_ready=lambda _child, _config, _timeout: (_ for _ in ()).throw(RuntimeError("not ready")),
        )

    assert process.terminate_called == 1


def test_main_defaults_to_background_launch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seen: dict[str, object] = {}
    result = BackgroundLaunchResult(
        pid=999,
        health_url="http://127.0.0.1:8100/v1/health",
        log_path=tmp_path / "gateway.log",
    )

    def _launch_background(*, config_path: str) -> BackgroundLaunchResult:
        seen["background"] = config_path
        return result

    monkeypatch.setattr("personal_assistant.main.launch_gateway_in_background", _launch_background)
    monkeypatch.setattr(
        "personal_assistant.main.run_gateway",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("foreground path should not run")),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert seen == {"background": str(tmp_path / "node-config.yaml")}
    assert capsys.readouterr().out == (
        "STARTED pid=999 health_url=http://127.0.0.1:8100/v1/health log="
        f"{tmp_path / 'gateway.log'}\n"
    )


def test_main_runs_gateway_in_foreground_when_requested(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def _run_gateway(*, config_path: str, factories=None) -> int:  # noqa: ANN001
        seen["foreground"] = (config_path, factories)
        return 0

    monkeypatch.setattr("personal_assistant.main.run_gateway", _run_gateway)
    monkeypatch.setattr(
        "personal_assistant.main.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("background path should not run")),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml"), "--foreground"])

    assert exit_code == 0
    assert seen == {"foreground": (str(tmp_path / "node-config.yaml"), None)}


def test_main_returns_non_zero_when_background_launch_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "personal_assistant.main.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("gateway failed")),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 1
    assert capsys.readouterr().err == "ERROR gateway failed\n"
