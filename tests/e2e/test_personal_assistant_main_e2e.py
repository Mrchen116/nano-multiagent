from __future__ import annotations

import asyncio
import threading
from pathlib import Path

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


def test_run_gateway_e2e_starts_runtime_with_loaded_config(tmp_path: Path) -> None:
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

        def run_forever(self) -> int:
            seen["started"] = True
            return 0

    exit_code = run_gateway(
        config_path=config_path,
        factories={"build_runtime": _Runtime},
    )

    assert exit_code == 0
    assert seen == {"node_id": "node-e2e", "health_path": "/v1/health", "started": True}


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
