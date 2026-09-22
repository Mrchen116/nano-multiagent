"""Protect PA provenance, explicit graph targets and the real loopback listener."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.internal_dispatch import (
    InternalDispatchEndpoint,
    InternalDispatchHandler,
)
from personal_assistant.gateway.runtime import GatewayRuntime
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.gateway.task_graphs import TaskGraphBridge
from personal_assistant.product import DEFAULT_TOOL_IDS, resolve_enabled_tools
from personal_assistant.reporter.capability_projection import PA_DEFAULT_TOOL_IDS
from personal_assistant.tools.task_graph import TaskGraphTool

from ._gateway_runtime_test_utils import make_config, run_in_thread


def stack(tmp_path, mode="single_thread", allowlist=("task_graph",)):
    config = AgentWorkspaceConfig(
        agent_id="pa", workspace_root=tmp_path, work_mode=mode, tool_allowlist=allowlist
    )
    catalog = LiveAgentCatalog((config,))
    binder = GatewaySessionBinder(
        catalog=catalog, repository=SessionBindingStore(), kernel=None
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
    config, catalog, binder, manager, inbox = stack(tmp_path, mode)
    endpoint = InternalDispatchEndpoint()
    handler = InternalDispatchHandler(
        im_connection_manager=manager,
        session_binder=binder,
        global_inbox=inbox,
        message_delivery=None,
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
        ctx.session_metadata["agent_id"] = "ephemeral-child"
        with pytest.raises(RuntimeError, match="unsupported_context"):
            tool.run({"action": "get", "graph_id": "tg_known"}, ctx)
        assert manager.send_json_await_ack.call_count == 3
    finally:
        runtime.request_shutdown()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert "error" not in outcome


@pytest.mark.asyncio
async def test_stale_or_disabled_provenance_never_enters_transport(tmp_path):
    config, catalog, binder, manager, inbox = stack(tmp_path)
    bridge = TaskGraphBridge(manager=manager, binder=binder, inbox=inbox)
    payload = {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "tool_call_id": "call",
        "args": {"action": "get", "graph_id": "tg_one"},
    }
    catalog.publish(replace(config, tool_allowlist=()))
    assert (await bridge.execute(payload))["error"]["code"] == "unsupported_context"
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
