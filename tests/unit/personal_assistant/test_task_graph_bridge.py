"""Protect PA provenance, explicit graph targets and the real loopback listener."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.composition import _make_prompt_preview_provider
from personal_assistant.gateway.global_inbox import GlobalInboxStore
from personal_assistant.gateway.kernel_client import InProcessKernelClient
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.runtime import GatewayRuntime
from personal_assistant.gateway.inbound_models import ShadowConversationRef
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
    IMRelayTarget,
    ExternalShadowTarget,
)
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.gateway.session_composition import project_agent_runtime
from personal_assistant.gateway.task_graphs import TaskGraphBridge
from personal_assistant.product import DEFAULT_TOOL_IDS, resolve_enabled_tools
from personal_assistant.reporter.capability_projection import PA_DEFAULT_TOOL_IDS
from personal_assistant.tools.task_graph import TaskGraphTool

from ._gateway_runtime_test_utils import make_config, run_in_thread


def stack(tmp_path, mode="single_thread", allowlist=("task_graph",), repository=None):
    config = AgentWorkspaceConfig(
        agent_id="pa", workspace_root=tmp_path, work_mode=mode, tool_allowlist=allowlist
    )
    catalog = LiveAgentCatalog((config,))
    binder = GatewaySessionBinder(
        catalog=catalog, repository=repository or SessionBindingStore(), kernel=None
    )
    binder.register_session_provenance(
        catalog.require("pa"), kernel_session_id="session"
    )
    manager = SimpleNamespace(
        connected=True,
        im_user_url="https://im.example/chat",
        send_json_await_ack=AsyncMock(
            return_value={
                "ok": True,
                "result": {
                    "graph_id": "tg_one",
                    "revision": 1,
                    "relative_url": "/tasks/tg_one",
                },
            }
        ),
    )
    inbox = SimpleNamespace(
        get_target=lambda agent, target: (
            {"conversation_id": "c_shadow"} if target == "local:external" else None
        )
    )
    return config, catalog, binder, manager, inbox


@pytest.mark.parametrize("mode", ["global", "single_thread"])
@pytest.mark.parametrize("channel", ["web_relay", "feishu"])
def test_native_tool_uses_real_listener_with_same_agent_rules(tmp_path, mode, channel):
    repository = SessionBindingStore()
    source_field = (
        "shadow_conversation_id" if channel == "feishu" else "conversation_id"
    )

    def bind(chat):
        repository.bind(
            session_key=f"{channel}:home:pa",
            kernel_session_id="session",
            reply_context=ReplyContext(
                channel_name=channel,
                target_chat_id="external-home",
                metadata={source_field: chat},
            ),
        )

    bind("c_first")
    contexts = RunDeliveryContextStore()
    config, catalog, binder, manager, inbox = stack(
        tmp_path, mode, repository=repository
    )
    endpoint = InternalDispatchEndpoint()
    handler = InternalDispatchHandler(
        im_connection_manager=manager,
        session_binder=binder,
        global_inbox=inbox,
        message_delivery=None,
        run_context_store=contexts,
    )
    runtime = GatewayRuntime(
        make_config(tmp_path),
        internal_dispatch_handler=handler,
        internal_dispatch_endpoint=endpoint,
        gateway_internal_port=0,
    )
    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(2)
        tool = TaskGraphTool(gateway_dispatch_url_provider=endpoint.current_url)
        ctx = SimpleNamespace(
            session_id="session",
            run_id="run",
            tool_call_id="call",
            session_metadata={"agent_id": "pa", "channel": channel},
        )
        result = tool.run(
            {
                "action": "create",
                "target": "local:external",
                "title": "Plan",
                "mode": "dag",
                "request_key": "create",
            },
            ctx,
        )
        assert result["web_url"] == "https://im.example/tasks/tg_one"
        sent = manager.send_json_await_ack.call_args
        assert sent.args[0] == "task_graph.command"
        assert sent.args[1]["args"]["conversation_id"] == "c_shadow"
        assert sent.args[1]["agent_id"] == "pa"
        assert "target" not in sent.args[1]["args"]
        tool.run({"action": "list"}, ctx)
        assert manager.send_json_await_ack.call_args.args[1]["args"] == {}
        tool.run({"action": "get", "graph_id": "tg_known"}, ctx)
        assert manager.send_json_await_ack.call_args.args[1]["args"] == {
            "graph_id": "tg_known"
        }
        for chat in ("c_first", "c_updated"):
            # An alias can bind another chat to the same Kernel session; source
            # must follow this run, not the repository's first reverse match.
            repository.bind(
                session_key=f"{channel}:{chat}:pa",
                kernel_session_id="session",
                reply_context=ReplyContext(
                    channel_name=channel,
                    target_chat_id=chat,
                    metadata={source_field: chat},
                ),
            )
            ctx.run_id = f"run-{chat}"
            target = (
                RunDeliveryTarget.for_external_shadow(
                    ExternalShadowTarget(ShadowConversationRef(chat, "message"))
                )
                if channel == "feishu"
                else RunDeliveryTarget.for_im_relay(IMRelayTarget(chat, "relay"))
            )
            contexts.seed(
                RunDeliveryContext(
                    run_id=ctx.run_id,
                    agent_id="pa",
                    kernel_session_id="session",
                    delivery_target=target,
                )
            )
            tool.run(
                {
                    "action": "create",
                    "title": "Bound source",
                    "mode": "dag",
                    "request_key": chat,
                },
                ctx,
            )
            sent_args = manager.send_json_await_ack.call_args.args[1]["args"]
            assert sent_args.get("conversation_id") == (
                chat if mode == "single_thread" else None
            )
        ctx.session_metadata["agent_id"] = "ephemeral-child"
        with pytest.raises(RuntimeError, match="unsupported_context"):
            tool.run({"action": "get", "graph_id": "tg_known"}, ctx)
        assert manager.send_json_await_ack.call_count == 5
    finally:
        runtime.request_shutdown()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert "error" not in outcome


@pytest.mark.asyncio
async def test_config_save_applies_to_task_tools_on_next_session_runtime(tmp_path):
    config, catalog, binder, manager, inbox = stack(tmp_path)
    bridge = TaskGraphBridge(manager=manager, binder=binder, inbox=inbox)
    payload = {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "tool_call_id": "call",
        "args": {"action": "get", "graph_id": "tg_one"},
    }
    catalog.publish(replace(config, tool_allowlist=()))
    assert (await bridge.execute(payload))["ok"] is True
    manager.send_json_await_ack.reset_mock()
    binder.register_session_provenance(
        catalog.require("pa"), kernel_session_id="session"
    )
    assert (await bridge.execute(payload))["error"]["code"] == "tool_not_allowed"
    manager.send_json_await_ack.assert_not_called()
    assert "task_graph" in DEFAULT_TOOL_IDS
    assert "task_graph" in PA_DEFAULT_TOOL_IDS
    assert "task_graph" not in resolve_enabled_tools(
        replace(config, tool_allowlist=(), work_mode="global")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["global", "single_thread"])
@pytest.mark.parametrize(
    "features,allowlist,enabled",
    [
        ({}, ("task_graph",), True),
        ({"task_graph": True}, ("task_graph",), True),
        ({"task_graph": False}, ("task_graph",), False),
        ({"task_graph": True}, (), False),
    ],
)
async def test_task_feature_controls_runtime_preview_and_dispatch_without_granting_tools(
    tmp_path, mode, features, allowlist, enabled
):
    config, catalog, binder, manager, inbox = stack(tmp_path, mode, allowlist)
    catalog.publish(replace(config, features=features))
    agent = catalog.require("pa")
    binder.register_session_provenance(agent, kernel_session_id="session")
    runtime = project_agent_runtime(
        agent, scenario={"conversation_id": "c_home"}, resolved_model="test-model"
    ).runtime
    assert ("task_graph" in runtime.enabled_tools) is enabled
    if not enabled:
        assert all("c_home" not in piece.text for piece in runtime.prompt.tail)
    preview = _make_prompt_preview_provider(
        SimpleNamespace(assemble_prompt_preview=lambda **kwargs: kwargs)
    )(
        "pa",
        str(tmp_path),
        features,
        None,
        list(allowlist),
        "direct",
        [],
        work_mode=mode,
    )
    assert preview["enabled_tools"] == runtime.enabled_tools
    result = await TaskGraphBridge(manager=manager, binder=binder, inbox=inbox).execute(
        {
            "source_agent_id": "pa",
            "origin_kernel_session_id": "session",
            "tool_call_id": "call",
            "args": {"action": "get", "graph_id": "tg_one"},
        }
    )
    assert result["ok"] is enabled
    if not enabled:
        assert result["error"]["code"] == "tool_not_allowed"
        manager.send_json_await_ack.assert_not_called()


@pytest.mark.asyncio
async def test_global_notifications_keep_task_tools_until_runtime_is_applied(tmp_path):
    config, catalog, _, manager, inbox = stack(tmp_path, mode="global")
    store = GlobalInboxStore(tmp_path / "global.sqlite3")
    store.save_global_session("pa", "session", str(tmp_path.resolve()))
    kernel = SimpleNamespace(
        get_session=lambda *args, **kwargs: None,
        identify_runtime=lambda **kwargs: SimpleNamespace(
            fingerprint_schema="v1", runtime_fingerprint="feature-off"
        ),
        get_session_runtime=AsyncMock(return_value=None),
        reconfigure_session=AsyncMock(return_value=None),
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
        global_store=store,
    )
    client = InProcessKernelClient(
        kernel,
        agent_catalog=catalog,
        session_binder=binder,
        product_default_model="test-model",
    )
    bridge = TaskGraphBridge(manager=manager, binder=binder, inbox=inbox)
    payload = {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "tool_call_id": "call",
        "args": {"action": "get", "graph_id": "tg_one"},
    }
    try:
        await binder.resolve_global(catalog.require("pa"))
        catalog.publish(replace(config, features={"task_graph": False}))
        next_agent = catalog.require("pa")
        # Inbox/heartbeat/cron may resolve the address while the old turn is busy.
        await binder.resolve_global(next_agent)
        assert not await client.ensure_agent_runtime(
            session_id="session",
            agent_snapshot=next_agent,
            workspace_root=str(tmp_path),
            metadata={"pa_work_scope": "global_main"},
            only_if_idle=True,
        )
        assert (await bridge.execute(payload))["ok"] is True
        kernel.reconfigure_session.return_value = object()
        assert await client.ensure_agent_runtime(
            session_id="session",
            agent_snapshot=next_agent,
            workspace_root=str(tmp_path),
            metadata={"pa_work_scope": "global_main"},
            only_if_idle=True,
        )
        assert (await bridge.execute(payload))["error"]["code"] == "tool_not_allowed"
        assert manager.send_json_await_ack.call_count == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_mapping_and_transport_failures_do_not_invent_success(tmp_path):
    config, catalog, binder, manager, inbox = stack(tmp_path)
    bridge = TaskGraphBridge(manager=manager, binder=binder, inbox=inbox)
    payload = {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "tool_call_id": "call",
        "args": {
            "action": "create",
            "target": "local:missing",
            "title": "Plan",
            "mode": "dag",
            "request_key": "same-key",
        },
    }
    assert (await bridge.execute(payload))["error"]["code"] == "source_unavailable"
    manager.send_json_await_ack.assert_not_called()
    payload["args"]["target"] = "c_home"
    manager.send_json_await_ack.side_effect = TimeoutError()
    result = await bridge.execute(payload)
    assert result["error"]["code"] == "write_outcome_unknown"
    assert result["error"]["request_key"] == "same-key"
    manager.connected = False
    assert (await bridge.execute(payload))["error"]["code"] == "source_unavailable"
    assert manager.send_json_await_ack.call_count == 1
