from __future__ import annotations

import asyncio
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SMOKE_MODULE = "personal_assistant.smoke_runtime"


def _pick_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pythonpath_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    return env


def _write_smoke_config(config_path: Path, workspace_root: Path | None = None, *, port: int) -> None:
    command = f"{sys.executable} -m uvicorn agent.platform.http_api.app:app --host 127.0.0.1 --port {port}"
    lines = [
        "node:",
        "  node_id: node-smoke",
        "agents:",
        "  - agent_id: assistant-a",
    ]
    if workspace_root is not None:
        lines.append(f"    workspace_root: {workspace_root}")
    lines.extend(
        [
            "channels:",
            "  - name: web_relay",
            "heartbeat:",
            "  tick_interval_seconds: 0.05",
            "kernel:",
            f"  command: {command}",
            "  startup_timeout_seconds: 10",
            "  health_poll_interval_seconds: 0.05",
            "  shutdown_grace_seconds: 3",
        ]
    )
    config_path.write_text("\n".join(lines), encoding="utf-8")


def _smoke_command(config_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        SMOKE_MODULE,
        "--config",
        str(config_path),
        "--ready-timeout",
        "20",
        "--steady-seconds",
        "0.2",
        "--shutdown-timeout",
        "10",
    ]


def _run_smoke(config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _smoke_command(config_path),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def _main_command(config_path: Path, *extra_args: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "personal_assistant.main",
        "--config",
        str(config_path),
        *extra_args,
    ]


def _parse_started_pid(stdout: str) -> int:
    match = re.search(r"STARTED pid=(\d+)", stdout)
    if match is None:
        raise AssertionError(f"missing background startup line: {stdout}")
    return int(match.group(1))


def _wait_for_health(url: str, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() <= deadline:
        try:
            response = httpx.get(url, timeout=1.0, trust_env=False)
            payload = response.json()
            if response.status_code == 200 and isinstance(payload, dict) and bool(payload.get("healthy")):
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for {url}")


def _terminate_background_pid(pid: int, *, timeout: float = 10.0) -> None:
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() <= deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)


def test_smoke_runtime_script_reports_ready_running_and_shutdown(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    _write_smoke_config(config_path, port=_pick_free_port())

    completed = _run_smoke(config_path)

    assert completed.returncode == 0, completed.stderr
    assert "READY pid=" in completed.stdout
    assert "RUNNING steady_seconds=0.2" in completed.stdout
    assert "SHUTDOWN exit_code=0" in completed.stdout
    assert (home_dir / "nano-assistant" / "workspace" / "assistant-a").is_dir() is True


def test_smoke_runtime_script_keeps_gateway_alive_after_ready(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    _write_smoke_config(config_path, port=_pick_free_port())

    completed = _run_smoke(config_path)

    assert completed.returncode == 0, completed.stderr
    assert "RUNNING steady_seconds=0.2 alive=true" in completed.stdout
    assert "READY pid=" in completed.stdout
    assert "SHUTDOWN exit_code=0" in completed.stdout
    assert (home_dir / "nano-assistant" / "workspace" / "assistant-a").is_dir() is True


def test_main_default_command_returns_after_background_start(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    port = _pick_free_port()
    _write_smoke_config(config_path, port=port)

    completed = subprocess.run(
        _main_command(config_path),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    pid = _parse_started_pid(completed.stdout)
    health_url = f"http://127.0.0.1:{port}/v1/health"
    try:
        _wait_for_health(health_url)
    finally:
        _terminate_background_pid(pid)


def test_main_foreground_flag_keeps_process_attached_until_sigterm(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    port = _pick_free_port()
    _write_smoke_config(config_path, port=port)

    process = subprocess.Popen(
        _main_command(config_path, "--foreground"),
        env=_pythonpath_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    health_url = f"http://127.0.0.1:{port}/v1/health"
    try:
        _wait_for_health(health_url)
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)

    assert process.returncode == 0


class _FakeProcessManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def start_kernel_process(self) -> None:
        self._events.append("kernel.start")

    def stop_kernel_process(self) -> None:
        self._events.append("kernel.stop")


class _FakeChannel:
    name = "web_relay"

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def start(self, on_inbound) -> None:  # noqa: ANN001
        self._events.append("channel.start:web_relay")

    def send(self, outbound) -> None:  # noqa: ANN001
        return None

    def stop(self) -> None:
        self._events.append("channel.stop:web_relay")


class _FakeHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.stop")


class _FakeIMManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()

    async def connect_once(self) -> None:
        self._events.append("im.connect")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self._closed.set()



from personal_assistant.config.local_store import load_local_config
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.main import GatewayRuntime, run_gateway


class _FakeProcessManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def start_kernel_process(self) -> None:
        self._events.append("kernel.start")

    def stop_kernel_process(self) -> None:
        self._events.append("kernel.stop")


class _FakeChannel:
    name = "web_relay"

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def start(self, on_inbound) -> None:  # noqa: ANN001
        self._events.append("channel.start:web_relay")

    def send(self, outbound) -> None:  # noqa: ANN001
        return None

    def stop(self) -> None:
        self._events.append("channel.stop:web_relay")


class _FakeHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.stop")


class _FakeIMManager:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()

    async def connect_once(self) -> None:
        self._events.append("im.connect")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self._closed.set()


def test_run_gateway_e2e_starts_runtime_with_loaded_config(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    config_path = tmp_path / "node-config.yaml"
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-e2e",
                "agents:",
                "  - agent_id: assistant-a",
                "kernel:",
                "  command: python -m agent.platform.http_api.app",
            ]
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    class _Runtime:
        def __init__(self, config) -> None:  # noqa: ANN001
            seen["node_id"] = config.node.node_id
            seen["health_path"] = config.kernel.health_path
            seen["workspace_root"] = str(config.agents[0].workspace_root)

        def run_forever(self) -> int:
            seen["started"] = True
            return 0

    exit_code = run_gateway(
        config_path=config_path,
        factories={"build_runtime": _Runtime},
    )

    assert exit_code == 0
    assert seen == {
        "node_id": "node-e2e",
        "health_path": "/v1/health",
        "workspace_root": str((home_dir / "nano-assistant" / "workspace" / "assistant-a").resolve()),
        "started": True,
    }
    assert (home_dir / "nano-assistant" / "workspace" / "assistant-a").is_dir() is True


def test_gateway_runtime_e2e_waits_for_shutdown_after_reaching_ready(tmp_path: Path) -> None:
    config_path = tmp_path / "node-config.yaml"
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-e2e",
                "agents:",
                "  - agent_id: assistant-a",
                f"    workspace_root: {workspace_root}",
                "channels:",
                "  - name: web_relay",
                "heartbeat:",
                "  tick_interval_seconds: 0.01",
                "im_service:",
                "  url: http://im.local:9000",
                "kernel:",
                "  command: python -m agent.platform.http_api.app",
            ]
        ),
        encoding="utf-8",
    )
    config = load_local_config(config_path)
    events: list[str] = []
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        channel_registry=ChannelRegistry([_FakeChannel(events)]),
        heartbeat_runner=_FakeHeartbeatRunner(events),
        im_connection_manager=_FakeIMManager(events),
    )
    outcome: dict[str, int] = {}
    thread = threading.Thread(target=lambda: outcome.setdefault("exit_code", runtime.run_forever()), daemon=True)

    thread.start()

    assert runtime.wait_until_ready(timeout=1.0) is True
    assert thread.is_alive() is True
    assert events[:4] == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "im.connect",
    ]

    runtime.request_shutdown()
    thread.join(timeout=1.0)

    assert outcome == {"exit_code": 0}
    assert events == [
        "kernel.start",
        "channel.start:web_relay",
        "heartbeat.start",
        "im.connect",
        "heartbeat.stop",
        "channel.stop:web_relay",
        "im.close",
        "kernel.stop",
    ]
