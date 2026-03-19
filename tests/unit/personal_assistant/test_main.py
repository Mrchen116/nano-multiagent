from __future__ import annotations

import asyncio
import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
import os

import httpx
import pytest

import personal_assistant.main as main_module

from personal_assistant.config.local_store import (
    DEFAULT_LOCAL_KERNEL_TOKEN,
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
    load_local_config,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
from personal_assistant.gateway.session_keys import PersistentSessionBindingStore, SessionBindingStore
from personal_assistant.main import (
    BackgroundLaunchResult,
    GatewayProcessManager,
    GatewayStartupError,
    GatewayRuntime,
    RuntimeFactories,
    _IMBootstrapClient,
    _IMConfigSyncClient,
    _build_channel_registry,
    build_runtime,
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


def test_relay_lifecycle_callback_sends_receipts_and_reports_with_real_usage_to_im() -> None:
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
                usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            ),
        )

    asyncio.run(_exercise())

    assert [item[0] for item in manager.sent_frames] == [
        "node.delivery_receipt",
        "node.report",
        "node.report",
        "node.delivery_receipt",
    ]
    assert manager.sent_frames[0][1]["delivery_status"] == "sent"
    assert manager.sent_frames[1][1]["conversation_id"] == "conv-1"
    assert manager.sent_frames[1][1]["message_id"] == "msg-1"
    assert manager.sent_frames[2][1]["status"] == "completed"
    assert manager.sent_frames[2][1]["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert manager.sent_frames[3][1]["detail"] == "hello from agent"


def test_build_relay_lifecycle_callback_marks_no_reply_suppression_in_completed_receipt() -> None:
    sent_frames: list[tuple[str, dict[str, object]]] = []

    class _Reporter:
        def send_delivery_receipt(self, *, relay_task_id: str, delivery_status: str, detail: str | None = None):
            return {
                "relay_task_id": relay_task_id,
                "delivery_status": delivery_status,
                "detail": detail,
            }

    class _Manager:
        connected = True

        async def send_json(self, message_type: str, payload: dict[str, object]) -> None:
            sent_frames.append((message_type, payload))

    callback = _build_relay_lifecycle_callback(
        reporter=_Reporter(),
        im_connection_manager_factory=lambda: _Manager(),
    )
    message = type("_Message", (), {})()
    message.external_chat_id = "conv-1"
    message.metadata = {"relay_task_id": "relay-1", "message_id": "msg-1"}

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="NO_REPLY",
                detail={"suppressed_by": "no_reply_token"},
            ),
        )

    asyncio.run(_exercise())

    assert sent_frames == [
        (
            "node.delivery_receipt",
            {
                "relay_task_id": "relay-1",
                "delivery_status": "completed",
                "detail": "suppressed_by=no_reply_token",
            },
        )
    ]


def test_build_relay_lifecycle_callback_keeps_completed_updates_when_im_is_reconnecting() -> None:
    sent_frames: list[tuple[str, dict[str, object]]] = []

    class _Reporter:
        def send_report(
            self,
            *,
            run_id: str,
            status: str,
            agent_id: str | None = None,
            session_key: str | None = None,
            conversation_id: str | None = None,
            message_id: str | None = None,
            summary: str | None = None,
            detail: dict[str, object] | None = None,
            usage: dict[str, object] | None = None,
        ) -> dict[str, object]:
            payload = {
                "run_id": run_id,
                "status": status,
                "agent_id": agent_id,
                "session_key": session_key,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "summary": summary,
            }
            if detail is not None:
                payload["detail"] = detail
            if usage is not None:
                payload["usage"] = usage
            return payload

        def send_delivery_receipt(self, *, relay_task_id: str, delivery_status: str, detail: str | None = None):
            return {
                "relay_task_id": relay_task_id,
                "delivery_status": delivery_status,
                "detail": detail,
            }

    class _Manager:
        connected = False

        async def send_json(self, message_type: str, payload: dict[str, object]) -> None:
            sent_frames.append((message_type, payload))

    callback = _build_relay_lifecycle_callback(
        reporter=_Reporter(),
        im_connection_manager_factory=lambda: _Manager(),
    )
    message = type("_Message", (), {})()
    message.external_chat_id = "conv-1"
    message.metadata = {"relay_task_id": "relay-1", "message_id": "msg-1"}

    async def _exercise() -> None:
        await callback(
            message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id="agent-a",
                session_key="web:user:agent-a",
                run_id="run-1",
                reply_text="hello from agent",
                usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            ),
        )

    asyncio.run(_exercise())

    assert sent_frames == [
        (
            "node.report",
            {
                "run_id": "run-1",
                "status": "completed",
                "agent_id": "agent-a",
                "session_key": "web:user:agent-a",
                "conversation_id": "conv-1",
                "message_id": "msg-1",
                "summary": "hello from agent",
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
        ),
        (
            "node.delivery_receipt",
            {
                "relay_task_id": "relay-1",
                "delivery_status": "completed",
                "detail": "hello from agent",
            },
        ),
    ]


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


def test_build_runtime_defaults_local_kernel_token_when_config_omits_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(),
        kernel=KernelConfig(
            token=None,
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )
    seen: dict[str, object] = {}

    class _RecordingKernelClient:
        def __init__(self, *, config, transport=None) -> None:  # noqa: ANN001
            del transport
            seen["kernel_config"] = config

        def close(self) -> None:
            seen["closed"] = True

    monkeypatch.setattr("personal_assistant.main.KernelApiClient", _RecordingKernelClient)

    runtime = build_runtime(config)

    assert isinstance(runtime, GatewayRuntime)
    kernel_config = seen["kernel_config"]
    assert kernel_config.token == DEFAULT_LOCAL_KERNEL_TOKEN



def test_build_channel_registry_passes_dedup_db_path(tmp_path: Path) -> None:
    registry = _build_channel_registry(
        (ChannelConfig(name="web_relay", enabled=True),),
        dedup_db_path=tmp_path / "relay-dedup.sqlite3",
    )

    relay_adapter = registry.get("web_relay")

    assert relay_adapter is not None
    assert relay_adapter._dedup_store is not None  # noqa: SLF001
    assert relay_adapter._dedup_store._db_path == tmp_path / "relay-dedup.sqlite3"  # noqa: SLF001



def test_build_runtime_wires_web_relay_dedup_db_under_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        kernel=KernelConfig(
            token=None,
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        source_path=tmp_path / "node-config.yaml",
    )

    class _RecordingKernelClient:
        def __init__(self, *, config, transport=None) -> None:  # noqa: ANN001
            del config, transport

        def close(self) -> None:
            return None

    monkeypatch.setattr("personal_assistant.main.KernelApiClient", _RecordingKernelClient)
    monkeypatch.setattr(
        "personal_assistant.main._build_im_connection_manager",
        lambda **kwargs: type("_Manager", (), {"connected": True, "close": lambda self: None})(),
    )

    runtime = build_runtime(config)
    relay_adapter = runtime._channel_registry.get("web_relay")  # noqa: SLF001

    assert relay_adapter is not None
    assert relay_adapter._dedup_store is not None  # noqa: SLF001
    assert relay_adapter._dedup_store._db_path == tmp_path / "relay_dedup.sqlite3"  # noqa: SLF001


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


def test_im_bootstrap_client_falls_back_to_local_im_api_port_when_primary_bootstrap_host_has_no_node() -> None:
    opened: list[str] = []

    def _client_factory(base_url: str) -> httpx.Client:
        def _handler(request: httpx.Request) -> httpx.Response:
            if base_url == "http://127.0.0.1:8021" and request.method == "GET" and request.url.path == "/im/v1/nodes":
                return httpx.Response(200, json=[])
            if base_url == "http://127.0.0.1:8011" and request.method == "GET" and request.url.path == "/im/v1/nodes":
                return httpx.Response(200, json=[{"node_id": "node-local", "owner_id": ""}])
            if base_url == "http://127.0.0.1:8011" and request.method == "POST" and request.url.path == "/im/v1/bind":
                return httpx.Response(201, json={"bind_url": "http://127.0.0.1:4173/bind/confirm?token=fallback"})
            raise AssertionError(f"unexpected request: {base_url} {request.method} {request.url}")

        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(_handler), trust_env=False)

    bootstrap = _IMBootstrapClient(
        base_url="http://127.0.0.1:8021",
        token=None,
        client_factory=_client_factory,
        browser_opener=lambda url, new=0, autoraise=True: opened.append(url) or True,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    bind_url = bootstrap.ensure_node_binding(node_id="node-local")

    assert bind_url == "http://127.0.0.1:4173/bind/confirm?token=fallback"
    assert opened == ["http://127.0.0.1:4173/bind/confirm?token=fallback"]



def test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace-from-im"
    seen: list[tuple[str, str | None]] = []
    sleeps: list[float] = []
    responses = iter(
        [
            httpx.Response(404, json={"detail": "agent_id not found"}),
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-live",
                    "display_name": "Agent Live",
                    "profile_version": 1,
                    "workspace_root": str(workspace_root),
                },
            ),
            httpx.Response(
                200,
                json={
                    "agent_id": "agent-live",
                    "display_name": "Agent Live v2",
                    "profile_version": 2,
                    "workspace_root": str(workspace_root),
                },
            ),
        ]
    )

    class _Pipeline:
        def __init__(self) -> None:
            self.dropped: list[str] = []

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            seen.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped.append(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        assert request.url.params["source"] == "mirror"
        return next(responses)

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: sleeps.append(seconds),
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert seen == [("agent-live", str(workspace_root))]
    assert pipeline.dropped == ["agent-live"]
    assert sleeps == [0.1, 0.1]
    assert workspace_root.is_dir()
    assert (workspace_root / "MEMORY.md").is_file() is True
    assert (workspace_root / "HEARTBEAT.md").is_file() is True
    assert (workspace_root / "MEMORY.md").read_text(encoding="utf-8").strip()
    assert (workspace_root / "HEARTBEAT.md").read_text(encoding="utf-8").strip()



def test_im_config_sync_client_drops_existing_agent_session_bindings_after_profile_refresh(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    class _Pipeline:
        def __init__(self) -> None:
            self.registered: list[tuple[str, str]] = []
            self._session_store = SessionBindingStore()
            self._session_store.bind(
                session_key="web:conv-1:agent-live",
                kernel_session_id="sess-old",
                reply_context=type("_ReplyContext", (), {"channel_name": "web_relay", "target_chat_id": "conv-1", "thread_id": None, "metadata": {}})(),
            )
            self._session_store.bind(
                session_key="web:conv-2:agent-other",
                kernel_session_id="sess-other",
                reply_context=type("_ReplyContext", (), {"channel_name": "web_relay", "target_chat_id": "conv-2", "thread_id": None, "metadata": {}})(),
            )

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            self.registered.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self._session_store.drop_agent(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        return httpx.Response(
            200,
            json={"agent_id": "agent-live", "display_name": "Agent Live", "profile_version": 2},
        )

    pipeline = _Pipeline()
    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert pipeline.registered == [("agent-live", str(workspace_root))]
    assert pipeline._session_store.get("web:conv-1:agent-live") is None
    assert pipeline._session_store.get("web:conv-2:agent-other") is not None


def test_im_config_sync_client_does_not_overwrite_existing_workspace_files(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    memory_path = workspace_root / "MEMORY.md"
    heartbeat_path = workspace_root / "HEARTBEAT.md"
    memory_path.write_text("existing memory\n", encoding="utf-8")
    heartbeat_path.write_text("interval: 1h\n\n- Existing heartbeat\n", encoding="utf-8")
    seen: list[tuple[str, str | None]] = []

    class _Pipeline:
        def __init__(self) -> None:
            self.dropped: list[str] = []

        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            seen.append((agent.agent_id, str(agent.workspace_root)))

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped.append(agent_id)

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/im/v1/agents/agent-live/config"
        return httpx.Response(
            200,
            json={"agent_id": "agent-live", "display_name": "Agent Live", "profile_version": 2},
        )

    client = httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False)
    pipeline = _Pipeline()
    config_path = tmp_path / "config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=(tmp_path / "seed-workspace")),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=pipeline,
        local_config=local_config,
        workspace_root_factory=lambda _agent_id: workspace_root,
        client=client,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    assert seen == [("agent-live", str(workspace_root))]
    assert pipeline.dropped == ["agent-live"]
    assert memory_path.read_text(encoding="utf-8") == "existing memory\n"
    assert heartbeat_path.read_text(encoding="utf-8") == "interval: 1h\n\n- Existing heartbeat\n"


def test_im_config_sync_client_persists_agent_config_to_source_path(tmp_path: Path) -> None:
    """Config sync must write back to the path the config was loaded from, not a hardcoded default."""
    workspace_root = tmp_path / "workspace"

    class _Pipeline:
        def register_agent(self, agent: AgentWorkspaceConfig) -> None:
            self.agent = agent

        def drop_agent_sessions(self, agent_id: str) -> None:
            self.dropped = agent_id

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-live",
                "display_name": "Agent Live",
                "profile_version": 2,
                "workspace_root": str(workspace_root),
                "skills": ["skill-a", "skill-b"],
                "tool_allowlist": ["Read", "Bash"],
                "system_prompt": "You are synced.",
                "group_reply_policy": "mention_only",
                "default_model": "claude-sonnet-4-6",
            },
        )

    seed_workspace = tmp_path / "seed-workspace"
    seed_workspace.mkdir(parents=True)
    config_path = tmp_path / "my-config.yaml"
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed-agent", workspace_root=seed_workspace),
        ),
        channels=(),
        kernel=KernelConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=config_path,
    )
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        pipeline=_Pipeline(),
        local_config=local_config,
        client=httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://im.local", trust_env=False),
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    sync.sync_agent(agent_id="agent-live", profile_version=2)

    # Must write to source_path (where the config was loaded from), not a hardcoded default.
    assert config_path.exists() is True
    persisted = load_local_config(config_path)
    assert persisted.source_path == config_path
    assert len(persisted.agents) == 2
    agent = next(item for item in persisted.agents if item.agent_id == "agent-live")
    assert agent.title == "Agent Live"
    assert agent.workspace_root == workspace_root.resolve()
    assert agent.skills == ("skill-a", "skill-b")
    assert agent.tool_allowlist == ("Read", "Bash")
    assert agent.system_prompt == "You are synced."
    assert agent.group_reply_policy == "mention_only"
    assert agent.default_model == "claude-sonnet-4-6"


def test_build_heartbeat_product_reports_maps_runs_to_main_agent_im_payloads() -> None:
    from personal_assistant.scheduler.heartbeat_scheduler import HeartbeatRunRecord, HeartbeatTickSummary
    from personal_assistant.main import _build_heartbeat_product_reports

    payloads = _build_heartbeat_product_reports(
        HeartbeatTickSummary(
            triggered_runs=(
                HeartbeatRunRecord(
                    agent_id="agent-a",
                    due_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
                    run_id="heartbeat-run-1",
                    session_id="session-heartbeat-1",
                ),
            ),
            skipped_agents=(),
        )
    )

    assert payloads == [
        {
            "run_id": "heartbeat-run-1",
            "status": "completed",
            "agent_id": "agent-a",
            "session_key": "agent-a::heartbeat",
            "conversation_id": "heartbeat:agent-a",
            "message_id": "heartbeat-run-1",
            "summary": "Heartbeat complete for main agent agent-a at 2026-03-13T09:00:00+00:00.",
            "guidance": "Open your main agent thread in Web IM to review the latest heartbeat result.",
        }
    ]



def test_gateway_runtime_publishes_heartbeat_product_reports_to_im(tmp_path: Path) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),),
        channels=(),
        kernel=KernelConfig(command="python -m agent.platform.http_api.app"),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )
    events: list[str] = []
    manager = _FakeIMManager(events)
    heartbeat_runner = _FakeHeartbeatRunner(
        events,
        report_payloads=[
            {
                "run_id": "heartbeat-run-1",
                "status": "completed",
                "agent_id": "agent-a",
                "summary": "Heartbeat complete: synced 3 tasks back to your main agent.",
                "conversation_id": "conv-main-agent",
                "message_id": "msg-heartbeat-1",
                "session_key": "agent-a::heartbeat",
            }
        ],
    )
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=manager,
    )

    thread = threading.Thread(target=runtime.run_forever)
    thread.start()
    assert runtime.wait_until_ready(timeout=1.0) is True
    runtime.request_shutdown()
    thread.join(timeout=2.0)

    assert ("node.report", {
        "run_id": "heartbeat-run-1",
        "status": "completed",
        "agent_id": "agent-a",
        "summary": "Heartbeat complete: synced 3 tasks back to your main agent.",
        "conversation_id": "conv-main-agent",
        "message_id": "msg-heartbeat-1",
        "session_key": "agent-a::heartbeat",
    }) in manager.sent_frames


def test_gateway_runtime_reports_actionable_bootstrap_failure_to_im(tmp_path: Path) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),),
        channels=(),
        kernel=KernelConfig(command="python -m agent.platform.http_api.app"),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )
    events: list[str] = []
    manager = _FakeIMManager(events)
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        heartbeat_runner=_FakeHeartbeatRunner(events),
        im_connection_manager=manager,
        post_im_connect=lambda: (_ for _ in ()).throw(
            GatewayStartupError(
                summary="node-local did not appear in IM bootstrap",
                next_step="Verify /im/v1/nodes on the configured IM API and rerun gateway.",
            )
        ),
    )

    with pytest.raises(GatewayStartupError, match="node-local did not appear in IM bootstrap"):
        runtime.run_forever()

    assert manager.sent_frames == [
        (
            "node.heartbeat",
            {
                "node_id": "node-local",
                "status": "degraded",
                "agent_count": 1,
                "last_error": (
                    "node-local did not appear in IM bootstrap Next: Verify /im/v1/nodes on the configured IM API "
                    "and rerun gateway."
                ),
            },
        )
    ]


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


def test_main_defaults_to_canonical_config_path_when_flag_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    seen: dict[str, object] = {}

    def _launch_background(**kwargs):  # noqa: ANN001
        seen["background"] = kwargs["config_path"]
        return BackgroundLaunchResult(
            pid=1,
            health_url="http://127.0.0.1:8000/v1/health",
            log_path=tmp_path / "gateway.log",
        )

    monkeypatch.setattr("personal_assistant.main.launch_gateway_in_background", _launch_background)
    monkeypatch.setattr(
        "personal_assistant.main.run_gateway",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("foreground path should not run")),
    )

    exit_code = main([])

    assert exit_code == 0
    assert seen == {"background": str((home_dir / ".nano-assistant" / "config.yaml").resolve())}


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


def test_main_surfaces_next_step_for_gateway_startup_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "personal_assistant.main.launch_gateway_in_background",
        lambda **_kwargs: (_ for _ in ()).throw(
            GatewayStartupError(
                summary="node-local did not appear in IM bootstrap",
                next_step="Verify /im/v1/nodes on the configured IM API and rerun gateway.",
            )
        ),
    )

    exit_code = main(["--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 1
    assert capsys.readouterr().err == (
        "ERROR node-local did not appear in IM bootstrap\n"
        "NEXT Verify /im/v1/nodes on the configured IM API and rerun gateway.\n"
    )


def test_launch_gateway_in_background_writes_runtime_state_file(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    process = _FakeProcess(wait_result=0, pid=2468)

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=lambda _argv, _log_path: process,
        wait_for_ready=lambda _child, _config, _timeout: None,
    )

    state_path = tmp_path / ".gateway-state.json"
    assert state_path.exists() is True
    assert "2468" in state_path.read_text(encoding="utf-8")
    assert str(config.source_path) in state_path.read_text(encoding="utf-8")


def test_main_stop_command_stops_background_gateway(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def _stop_background(*, config_path: str) -> str:
        seen["config_path"] = config_path
        return "STOPPED pid=999"

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop_background)

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert seen == {"config_path": str(tmp_path / "node-config.yaml")}
    assert capsys.readouterr().out == "STOPPED pid=999\n"


def test_main_stop_command_defaults_to_canonical_config_path_when_flag_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    seen: dict[str, object] = {}

    def _stop_background(*, config_path: str) -> str:
        seen["config_path"] = config_path
        return "STOPPED pid=999"

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop_background)

    exit_code = main(["stop"])

    assert exit_code == 0
    assert seen == {"config_path": str((home_dir / ".nano-assistant" / "config.yaml").resolve())}
    assert capsys.readouterr().out == "STOPPED pid=999\n"


def test_main_stop_command_reports_not_running(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr("personal_assistant.main.stop_gateway", lambda **_kwargs: "NOT RUNNING config=node-config.yaml")

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert capsys.readouterr().out == "NOT RUNNING config=node-config.yaml\n"


def test_main_stop_command_reports_stale_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("personal_assistant.main.stop_gateway", lambda **_kwargs: "STALE pid=999 state=.gateway-state.json")

    exit_code = main(["stop", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert capsys.readouterr().out == "STALE pid=999 state=.gateway-state.json\n"


def test_stop_gateway_reports_still_healthy_when_pid_is_stale_but_health_url_is_alive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _build_config(tmp_path)
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: False)
    monkeypatch.setattr("personal_assistant.main._healthcheck_reports_healthy", lambda _url: True)

    result = main_module.stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert result == (
        "STALE pid=2468 state="
        f"{state_path} health_url=http://127.0.0.1:8100/v1/health still_healthy=true"
    )
    assert state_path.exists() is False


def test_stop_gateway_only_reports_stopped_after_health_url_goes_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(),
        channels=(),
        kernel=KernelConfig(
            command="python -m agent.platform.http_api.app",
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.01,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        source_path=tmp_path / "node-config.yaml",
    )
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    pid_checks = iter([True, False])
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr("personal_assistant.main.os.kill", lambda _pid, _sig: None)
    monkeypatch.setattr("personal_assistant.main.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("personal_assistant.main.time.monotonic", iter([0.0, 0.01]).__next__)
    verify_calls: list[tuple[str, float, float]] = []

    def _verify(health_url: str, *, timeout_seconds: float, sleep_seconds: float) -> bool:
        verify_calls.append((health_url, timeout_seconds, sleep_seconds))
        return False

    monkeypatch.setattr("personal_assistant.main._verify_stopped_health_url", _verify)

    result = main_module.stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert result == (
        "STOPPED pid=2468 state="
        f"{state_path} health_url=http://127.0.0.1:8100/v1/health still_healthy=true"
    )
    assert verify_calls == [("http://127.0.0.1:8100/v1/health", 0.1, 0.01)]
    assert state_path.exists() is False


# ---------------------------------------------------------------------------
# M245: PID file lifecycle, single-instance protection, restart subcommand
# ---------------------------------------------------------------------------


def test_run_gateway_writes_pid_file_before_start_and_removes_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must write gateway.pid before the runtime starts and remove it on clean exit."""
    from personal_assistant.main import run_gateway, _gateway_pid_path

    config = _build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_observed_during_run: list[bool] = []

    class _Runtime:
        def run_forever(self) -> int:
            pid_observed_during_run.append(pid_path.exists())
            return 0

    run_gateway(
        config_path=config.source_path,
        factories=RuntimeFactories(
            load_config=lambda _path: config,
            build_runtime=lambda _config: _Runtime(),
        ),
    )

    assert pid_observed_during_run == [True], "gateway.pid must exist while runtime is running"
    assert not pid_path.exists(), "gateway.pid must be removed after clean exit"


def test_run_gateway_removes_pid_file_even_when_runtime_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gateway must remove gateway.pid even when the runtime raises an exception."""
    from personal_assistant.main import run_gateway, _gateway_pid_path

    config = _build_config(tmp_path)
    pid_path = _gateway_pid_path(config)

    class _BrokenRuntime:
        def run_forever(self) -> int:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_gateway(
            config_path=config.source_path,
            factories=RuntimeFactories(
                load_config=lambda _path: config,
                build_runtime=lambda _config: _BrokenRuntime(),
            ),
        )

    assert not pid_path.exists(), "gateway.pid must be cleaned up even on error"


def test_launch_background_refuses_to_start_when_pid_file_shows_live_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """launch_gateway_in_background must raise GatewayStartupError with PID when already running."""
    from personal_assistant.main import launch_gateway_in_background, _gateway_pid_path

    config = _build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("12345", encoding="utf-8")

    # Simulate that PID 12345 is alive
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: True)

    with pytest.raises(GatewayStartupError) as exc_info:
        launch_gateway_in_background(
            config_path=config.source_path,
            load_config=lambda _path: config,
        )

    assert "12345" in str(exc_info.value), "error must mention the existing PID"
    assert pid_path.exists(), "stale pid file must be left intact when process is alive"


def test_launch_background_clears_stale_pid_file_when_process_dead(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """launch_gateway_in_background must remove a stale gateway.pid if process is no longer running."""
    from personal_assistant.main import launch_gateway_in_background, _gateway_pid_path

    config = _build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("99999", encoding="utf-8")

    spawned: list[list[str]] = []

    def _spawn(argv: list[str], log_path: Path) -> _FakeProcess:
        spawned.append(argv)
        return _FakeProcess(wait_result=0, pid=1111)

    # Simulate that PID 99999 is dead
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: False)

    launch_gateway_in_background(
        config_path=config.source_path,
        load_config=lambda _path: config,
        spawn_process=_spawn,
        wait_for_ready=lambda _child, _config, _timeout: None,
    )

    assert spawned, "gateway must have been spawned after stale PID cleanup"
    assert not pid_path.exists() or pid_path.read_text(encoding="utf-8") != "99999", (
        "stale PID content must have been replaced"
    )


def test_main_restart_command_stops_then_starts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """main restart must call stop then start (background launch), returning exit code 0."""
    calls: list[str] = []

    def _stop(*, config_path: str) -> str:
        calls.append(f"stop:{config_path}")
        return "STOPPED pid=999"

    def _start(*, config_path: str) -> BackgroundLaunchResult:
        calls.append(f"start:{config_path}")
        return BackgroundLaunchResult(
            pid=1234,
            health_url="http://127.0.0.1:8100/v1/health",
            log_path=tmp_path / "gateway.log",
        )

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop)
    monkeypatch.setattr("personal_assistant.main.launch_gateway_in_background", _start)

    config_path = str(tmp_path / "node-config.yaml")
    exit_code = main(["restart", "--config", config_path])

    assert exit_code == 0
    assert calls == [f"stop:{config_path}", f"start:{config_path}"]
    out = capsys.readouterr().out
    assert "STARTED pid=1234" in out


def test_main_restart_command_continues_when_gateway_not_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """main restart must ignore NOT RUNNING from stop and proceed to start."""
    calls: list[str] = []

    def _stop(*, config_path: str) -> str:
        calls.append("stop")
        return "NOT RUNNING config=node-config.yaml"

    def _start(*, config_path: str) -> BackgroundLaunchResult:
        calls.append("start")
        return BackgroundLaunchResult(
            pid=5678,
            health_url="http://127.0.0.1:8100/v1/health",
            log_path=tmp_path / "gateway.log",
        )

    monkeypatch.setattr("personal_assistant.main.stop_gateway", _stop)
    monkeypatch.setattr("personal_assistant.main.launch_gateway_in_background", _start)

    exit_code = main(["restart", "--config", str(tmp_path / "node-config.yaml")])

    assert exit_code == 0
    assert calls == ["stop", "start"]


def test_stop_gateway_removes_pid_file_on_successful_stop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stop_gateway must delete gateway.pid after successfully stopping the process."""
    from personal_assistant.main import stop_gateway, _gateway_pid_path

    config = _build_config(tmp_path)
    pid_path = _gateway_pid_path(config)
    pid_path.write_text("2468", encoding="utf-8")

    # Also write state file so stop_gateway can find the PID
    state_path = tmp_path / ".gateway-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": 2468,
                "config_path": str(config.source_path),
                "health_url": "http://127.0.0.1:8100/v1/health",
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )

    pid_checks = iter([True, False])
    monkeypatch.setattr("personal_assistant.main._pid_is_running", lambda _pid: next(pid_checks))
    monkeypatch.setattr("personal_assistant.main.os.kill", lambda _pid, _sig: None)
    monkeypatch.setattr("personal_assistant.main.time.sleep", lambda _s: None)
    monkeypatch.setattr("personal_assistant.main.time.monotonic", iter([0.0, 0.01]).__next__)
    monkeypatch.setattr("personal_assistant.main._verify_stopped_health_url", lambda *a, **kw: True)

    result = stop_gateway(config_path=config.source_path, load_config=lambda _path: config)

    assert "STOPPED" in result
    assert not pid_path.exists(), "gateway.pid must be removed after stop"


# ---------------------------------------------------------------------------
# M248: build_runtime 使用 PersistentSessionBindingStore
# ---------------------------------------------------------------------------


def _make_minimal_config(tmp_path: Path) -> "LocalConfig":
    """构造一个最小可用的 LocalConfig，source_path 在 tmp_path 下。"""
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
        source_path=tmp_path / "node-config.yaml",
    )


def test_build_runtime_uses_persistent_session_binding_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_runtime 构造的 pipeline 使用 PersistentSessionBindingStore。"""
    config = _make_minimal_config(tmp_path)

    class _DummyKernelClient:
        def __init__(self, *, config, transport=None) -> None:  # noqa: ANN001
            del config, transport

        def close(self) -> None:
            return None

    monkeypatch.setattr("personal_assistant.main.KernelApiClient", _DummyKernelClient)

    runtime = build_runtime(config)

    pipeline = runtime._on_inbound._pipeline  # noqa: SLF001
    assert isinstance(pipeline._session_store, PersistentSessionBindingStore)  # noqa: SLF001


def test_build_runtime_session_store_db_path_is_under_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """session_bindings.sqlite3 与 relay_dedup.sqlite3 同目录（config_path 的父目录）。"""
    config = _make_minimal_config(tmp_path)

    class _DummyKernelClient:
        def __init__(self, *, config, transport=None) -> None:  # noqa: ANN001
            del config, transport

        def close(self) -> None:
            return None

    monkeypatch.setattr("personal_assistant.main.KernelApiClient", _DummyKernelClient)

    runtime = build_runtime(config)

    pipeline = runtime._on_inbound._pipeline  # noqa: SLF001
    store: PersistentSessionBindingStore = pipeline._session_store  # noqa: SLF001
    expected_db_path = tmp_path / "session_bindings.sqlite3"
    assert store._db_path == expected_db_path  # noqa: SLF001


def test_build_runtime_injects_kernel_client_into_session_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_runtime 在构造后将 kernel_client 注入 PersistentSessionBindingStore。"""
    config = _make_minimal_config(tmp_path)
    injected_clients: list[object] = []

    original_init = PersistentSessionBindingStore.__init__

    class _TrackingStore(PersistentSessionBindingStore):
        def set_kernel_client(self, client: object) -> None:
            injected_clients.append(client)
            super().set_kernel_client(client)  # type: ignore[arg-type]

    monkeypatch.setattr("personal_assistant.main.PersistentSessionBindingStore", _TrackingStore)

    class _DummyKernelClient:
        def __init__(self, *, config, transport=None) -> None:  # noqa: ANN001
            del config, transport

        def close(self) -> None:
            return None

    monkeypatch.setattr("personal_assistant.main.KernelApiClient", _DummyKernelClient)

    build_runtime(config)

    assert len(injected_clients) == 1, "kernel_client должен быть инъецирован один раз"
    assert isinstance(injected_clients[0], _DummyKernelClient)
