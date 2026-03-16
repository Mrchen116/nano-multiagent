from __future__ import annotations

import asyncio
import json
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
    if extra_args and extra_args[0] == "stop":
        return [
            sys.executable,
            "-m",
            "personal_assistant.main",
            "stop",
            "--config",
            str(config_path),
            *extra_args[1:],
        ]
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


class _PwdToolLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request):  # noqa: ANN001, ANN201
        from agent.core.llm.interfaces import LLMGenerateResponse, LLMMessage, LLMToolCall

        self.calls += 1
        if self.calls == 1:
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(call_id="call_pwd", name="bash", arguments={"command": "pwd"}),
                    ),
                ),
                finish_reason="tool_calls",
            )
        tool_payload = json.loads(request.messages[-1].content)
        output = tool_payload.get("output", {}) if isinstance(tool_payload, dict) else {}
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=str(output.get("content", "")).strip()),
            finish_reason="stop",
        )


def _runtime_pwd_for_workspace(*, tmp_path: Path, workspace_root: Path) -> str:
    from fastapi.testclient import TestClient

    from agent.core.agent.runtime import AgentRuntime
    from agent.core.session.manager import SessionManager
    from agent.platform.http_api.app import create_app
    from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
    from agent.platform.tools.loader import build_tool_registry

    workspace_root.mkdir(parents=True, exist_ok=True)
    llm = _PwdToolLLM()
    store = SQLiteSessionStore(db_path=tmp_path / "pwd-runtime.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=REPO_ROOT,
    )
    tool_registry = build_tool_registry(repo_root=REPO_ROOT, runtime=runtime)
    app = create_app(session_store=store, runtime=runtime, tool_registry=tool_registry, auth_token="test-token")
    client = TestClient(app)
    created = client.post(
        "/v1/sessions",
        json={"workspace_root": str(workspace_root)},
        headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-workspace-create"},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "show pwd"}], "stream": False},
        headers={"Authorization": "Bearer test-token", "X-Request-Id": "req-workspace-message"},
    )
    assert response.status_code == 200
    return str(response.json()["message"]["content"]).strip()


def test_kernel_session_workspace_root_controls_runtime_pwd(tmp_path: Path) -> None:
    workspace_root = tmp_path / "fuck"

    assert _runtime_pwd_for_workspace(tmp_path=tmp_path, workspace_root=workspace_root) == str(workspace_root.resolve())


def test_new_kernel_session_uses_its_own_workspace_root_after_workspace_change(tmp_path: Path) -> None:
    first_workspace = tmp_path / "workspace-a"
    second_workspace = tmp_path / "workspace-b"

    assert _runtime_pwd_for_workspace(tmp_path=tmp_path / "run-a", workspace_root=first_workspace) == str(first_workspace.resolve())
    assert _runtime_pwd_for_workspace(tmp_path=tmp_path / "run-b", workspace_root=second_workspace) == str(second_workspace.resolve())


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


def test_main_background_start_uses_repo_root_node_config_multiple_agents(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = REPO_ROOT / "node-config.yaml"
    original = config_path.read_text(encoding="utf-8")
    port = _pick_free_port()
    command = f"{sys.executable} -m uvicorn agent.platform.http_api.app:app --host 127.0.0.1 --port {port}"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: canonical-node",
                "agents:",
                "  - agent_id: Alpha",
                "    title: Alpha",
                "  - agent_id: Beta",
                "    title: Beta",
                "channels:",
                "  - name: web_relay",
                "    enabled: true",
                "kernel:",
                f"  command: {command}",
            ]
        ),
        encoding="utf-8",
    )

    try:
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
            loaded = load_local_config(config_path)
            assert [agent.agent_id for agent in loaded.agents] == ["Alpha", "Beta"]
            assert (home_dir / "nano-assistant" / "workspace" / "Alpha").is_dir() is True
            assert (home_dir / "nano-assistant" / "workspace" / "Beta").is_dir() is True
        finally:
            _terminate_background_pid(pid)
    finally:
        config_path.write_text(original, encoding="utf-8")


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


def test_main_stop_command_stops_background_gateway(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    port = _pick_free_port()
    _write_smoke_config(config_path, port=port)

    started = subprocess.run(
        _main_command(config_path),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert started.returncode == 0, started.stderr
    health_url = f"http://127.0.0.1:{port}/v1/health"
    _wait_for_health(health_url)

    stopped = subprocess.run(
        _main_command(config_path, "stop"),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert stopped.returncode == 0, stopped.stderr
    assert "STOPPED pid=" in stopped.stdout
    deadline = time.monotonic() + 10.0
    while time.monotonic() <= deadline:
        try:
            httpx.get(health_url, timeout=0.5, trust_env=False)
        except Exception:  # noqa: BLE001
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f"gateway still healthy after stop: {health_url}")


def test_main_stop_command_reports_stale_runtime_state_after_process_is_gone(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    port = _pick_free_port()
    _write_smoke_config(config_path, port=port)

    started = subprocess.run(
        _main_command(config_path),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert started.returncode == 0, started.stderr
    pid = _parse_started_pid(started.stdout)
    _wait_for_health(f"http://127.0.0.1:{port}/v1/health")
    _terminate_background_pid(pid)

    stopped = subprocess.run(
        _main_command(config_path, "stop"),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert stopped.returncode == 0, stopped.stderr
    assert "STALE pid=" in stopped.stdout
    assert (config_path.parent / ".gateway-state.json").exists() is False


def test_main_stop_command_reports_still_healthy_when_another_listener_remains(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    port = _pick_free_port()
    _write_smoke_config(config_path, port=port)

    started = subprocess.run(
        _main_command(config_path),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert started.returncode == 0, started.stderr
    pid = _parse_started_pid(started.stdout)
    health_url = f"http://127.0.0.1:{port}/v1/health"
    _wait_for_health(health_url)

    blocker: subprocess.Popen[bytes] | None = None
    try:
        _terminate_background_pid(pid)
        blocker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import json; import signal; import threading; from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer; "
                    f"server = ThreadingHTTPServer(('127.0.0.1', {port}), type('Handler', (BaseHTTPRequestHandler,), {{"
                    "'do_GET': lambda self: (self.send_response(200), self.send_header('Content-Type', 'application/json'), self.end_headers(), self.wfile.write(json.dumps({'healthy': True}).encode('utf-8'))), "
                    "'log_message': lambda *args: None"
                    "})); "
                    "done = threading.Event(); "
                    "signal.signal(signal.SIGTERM, lambda *_args: (done.set(), server.shutdown())); "
                    "threading.Thread(target=server.serve_forever, daemon=True).start(); "
                    "done.wait()"
                ),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_health(health_url)

        stopped = subprocess.run(
            _main_command(config_path, "stop"),
            env=_pythonpath_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

        assert stopped.returncode == 0, stopped.stderr
        assert "health_url=" in stopped.stdout
        assert "still_healthy=true" in stopped.stdout
        assert (config_path.parent / ".gateway-state.json").exists() is False
    finally:
        if blocker is not None:
            blocker.terminate()
            blocker.wait(timeout=10)


def test_main_stop_command_reports_not_running_without_state_file(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    config_path = tmp_path / "node-config.yaml"
    _write_smoke_config(config_path, port=_pick_free_port())

    stopped = subprocess.run(
        _main_command(config_path, "stop"),
        env=_pythonpath_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert stopped.returncode == 0, stopped.stderr
    assert "NOT RUNNING" in stopped.stdout
    assert str(config_path.parent / ".gateway-state.json") in stopped.stdout
    assert "kill" not in stopped.stdout.lower()
    assert "pid=" not in stopped.stdout


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
        self.connected = True

    async def connect_once(self) -> None:
        self._events.append("im.connect")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
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
        self.connected = True

    async def connect_once(self) -> None:
        self._events.append("im.connect")

    async def run_forever(self) -> None:
        await self._closed.wait()

    async def close(self) -> None:
        self._events.append("im.close")
        self.connected = False
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
