"""Shared test helpers for personal_assistant.main unit tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(name="kimiCoding:K2.6", extra_request_body={"thinking": {"type": "adaptive"}}),
            ),
        ),
    ),
)


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
    def __init__(self, events: list[str], *, report_payloads: list[dict[str, object]] | None = None) -> None:
        self._events = events
        self.report_payloads = list(report_payloads or [])

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.stop")

    def request_tick(self) -> None:
        self._events.append("heartbeat.tick")

    def build_product_reports(self) -> list[dict[str, object]]:
        payloads = list(self.report_payloads)
        self.report_payloads.clear()
        return payloads


class _FakeHeartbeatRunnerMissingProductHook:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.stop")

    def request_tick(self) -> None:
        self._events.append("heartbeat.tick")


class _FakeHeartbeatRunnerMinimal:
    def __init__(self, events: list[str], *, report_payloads: list[dict[str, object]] | None = None) -> None:
        self._delegate = _FakeHeartbeatRunner(events, report_payloads=report_payloads)

    async def start(self) -> None:
        await self._delegate.start()

    async def close(self) -> None:
        await self._delegate.close()

    def request_tick(self) -> None:
        self._delegate.request_tick()

    def build_product_reports(self) -> list[dict[str, object]]:
        return self._delegate.build_product_reports()


class _FakeHeartbeatRunnerMain(_FakeHeartbeatRunner):
    pass


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


def build_config(tmp_path: Path) -> LocalConfig:
    """Construct a LocalConfig with a kernel process manager for process/runtime tests."""
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
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )


def make_minimal_config(tmp_path: Path) -> LocalConfig:
    """Construct a minimal LocalConfig suitable for build_runtime tests."""
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    return LocalConfig(
        node=NodeConfig(node_id="node-m248"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(),
        kernel=KernelConfig(
            token=None,
            command="python -m dummy",
            startup_timeout_seconds=0.1,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )
