"""Unit tests for relay lifecycle callbacks and gateway runtime build functions."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    DEFAULT_LOCAL_KERNEL_TOKEN,
    AgentWorkspaceConfig,
    ChannelConfig,
    HeartbeatConfig,
    IMServiceConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
from personal_assistant.main import (
    GatewayRuntime,
    GatewayStartupError,
    RuntimeFactories,
    _IMBootstrapClient,
    _build_channel_registry,
    _build_relay_lifecycle_callback,
    build_runtime,
    run_gateway,
)
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

from agent.core.llm.model_registry import _reset_for_tests
from ._main_helpers import _FakeIMManager, build_config

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

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
    _reset_for_tests()  # run_gateway calls init_model_registry; must start from clean state
    config = build_config(tmp_path)
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


def test_build_runtime_returns_gateway_runtime_with_no_process_manager(tmp_path: Path) -> None:
    """refactor-387 M3: build_runtime no longer spawns a kernel subprocess.

    GatewayRuntime.process_manager must be None — the kernel runs in-process.
    """
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(),
        kernel=KernelConfig(
            token=None,
            # command removed: kernel now in-process (refactor-387-M4)
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    runtime = build_runtime(config)

    assert isinstance(runtime, GatewayRuntime)
    # M3: process manager must be None — kernel is in-process, no subprocess spawned.
    assert runtime._process_manager is None  # noqa: SLF001


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
            # command removed: kernel now in-process (refactor-387-M4)
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

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
    import httpx

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
    import httpx

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


def test_im_bootstrap_client_only_uses_configured_im_base_url() -> None:
    import httpx

    requests: list[tuple[str, str]] = []

    def _client_factory(base_url: str) -> httpx.Client:
        def _handler(request: httpx.Request) -> httpx.Response:
            requests.append((base_url, request.url.path))
            return httpx.Response(200, json=[])

        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(_handler), trust_env=False)

    bootstrap = _IMBootstrapClient(
        base_url="http://127.0.0.1:8021",
        token=None,
        client_factory=_client_factory,
        browser_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("browser should not open")),
        monotonic=iter([0.0, 0.0, 5.1]).__next__,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(GatewayStartupError, match="node node-local did not appear in IM bootstrap"):
        bootstrap.ensure_node_binding(node_id="node-local")

    assert requests == [("http://127.0.0.1:8021", "/im/v1/nodes")]


# ---------------------------------------------------------------------------
# Prompt preview provider wiring (C1 fix: refactor-387 regression)
# ---------------------------------------------------------------------------


def test_build_runtime_wires_prompt_preview_provider_when_im_service_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_runtime must wire a non-None prompt_preview_provider when im_service is set.

    refactor-387 M3 regression: prompt_preview_provider was set to None because
    the kernel HTTP endpoint was deleted without an SDK replacement.  The fix adds
    Kernel.assemble_prompt_preview() and wires it here.

    This test verifies that:
    1. The im_connection_manager receives a non-None provider.
    2. Calling the provider returns {"prompt": <non-empty str>, "section_count": <int>}.
    """
    import asyncio

    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace_root),),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        kernel=KernelConfig(
            token=None,
            startup_timeout_seconds=0.2,
            health_poll_interval_seconds=0.0,
            shutdown_grace_seconds=0.1,
        ),
        heartbeat=HeartbeatConfig(),
        im_service=IMServiceConfig(url="http://im.local"),
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )

    captured_kwargs: dict = {}

    def _fake_build_im_connection_manager(**kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return type("_Manager", (), {"connected": True, "close": lambda self: None})()

    monkeypatch.setattr(
        "personal_assistant.main._build_im_connection_manager",
        _fake_build_im_connection_manager,
    )

    build_runtime(config)

    provider = captured_kwargs.get("prompt_preview_provider")
    assert provider is not None, (
        "build_runtime must wire a non-None prompt_preview_provider when im_service is set; "
        "None means agent settings page Preview shows empty (M3 regression)"
    )
    assert callable(provider), "prompt_preview_provider must be callable"

    # Call the provider and verify it returns the expected schema.
    result = asyncio.run(
        provider(
            "agent-a",
            str(workspace_root),
            {},    # features
            None,  # custom_prompt
            [],    # tool_ids
            "direct",  # scenario
            [],    # skill_ids
        )
    ) if asyncio.iscoroutinefunction(provider) else provider(
        "agent-a",
        str(workspace_root),
        {},
        None,
        [],
        "direct",
        [],
    )
    assert isinstance(result, dict), f"provider must return dict, got {type(result)}"
    assert "prompt" in result, f"provider result must contain 'prompt', got {list(result)}"
    assert "section_count" in result, f"provider result must contain 'section_count', got {list(result)}"
    assert result["prompt"], "prompt_preview_provider must return non-empty prompt"
    assert isinstance(result["section_count"], int) and result["section_count"] > 0, (
        f"section_count must be positive int, got {result['section_count']!r}"
    )
