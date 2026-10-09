"""Protect the native tool's authenticated loopback handoff and honest outcomes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from personal_assistant.tools.task_graph import TaskGraphTool
from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMMessage
from agent.core.tools.registry import ToolRegistry
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


@pytest.mark.parametrize(
    "args,expected_target",
    [
        ({"action": "get", "graph_id": "tg_known"}, None),
        (
            {
                "action": "apply",
                "graph_id": "tg_known",
                "base_revision": 1,
                "request_key": "update",
                "operations": [
                    {"op": "update_task", "node_id": "n1", "patch": {"status": "doing"}}
                ],
                "change_note": "Started",
            },
            None,
        ),
        (
            {
                "action": "create",
                "title": "Plan",
                "mode": "dag",
                "request_key": "create",
            },
            None,
        ),
        (
            {
                "action": "create",
                "target": "c_explicit",
                "title": "Plan",
                "mode": "dag",
                "request_key": "explicit",
            },
            "c_explicit",
        ),
    ],
)
def test_native_tool_preserves_business_args_and_runtime_identity(
    monkeypatch, args, expected_target
):
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(200, json={"ok": True, "result": {"revision": 2}})

    monkeypatch.setattr(httpx, "post", post)
    ctx = SimpleNamespace(
        session_id="session",
        run_id="run",
        tool_call_id="call",
        session_metadata={"agent_id": "pa", "conversation_id": "c_current"},
    )
    tool = TaskGraphTool(
        gateway_dispatch_url_provider=lambda: "http://127.0.0.1:123/old"
    )
    assert tool.run(args, ctx) == {"revision": 2}
    assert seen[0][0] == "http://127.0.0.1:123/internal/task-graph"
    assert seen[0][1]["json"] == {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "origin_run_id": "run",
        "tool_call_id": "call",
        "args": {**args, **({"target": expected_target} if expected_target else {})},
    }
    with pytest.raises(ValueError, match="invalid_arguments"):
        tool.run({**args, "actor": "owner"}, ctx)
    assert len(seen) == 1


@pytest.mark.parametrize(
    "action,code", [("create", "write_outcome_unknown"), ("list", "source_unavailable")]
)
def test_native_tool_timeout_retains_write_identity(monkeypatch, action, code):
    def post(*args, **kwargs):
        raise httpx.ReadTimeout("lost response")

    monkeypatch.setattr(httpx, "post", post)
    args = {"action": action}
    if action == "create":
        args.update(title="Plan", mode="dag", request_key="retry-same")
    ctx = SimpleNamespace(
        session_id="session",
        run_id="run",
        tool_call_id="call",
        session_metadata={"agent_id": "pa"},
    )
    tool = TaskGraphTool(
        gateway_dispatch_url_provider=lambda: "http://127.0.0.1:123/old"
    )
    with pytest.raises(RuntimeError, match=code) as error:
        tool.run(args, ctx)
    if action == "create":
        assert "retry-same" in str(error.value)


@pytest.mark.parametrize("blocked", [False, True])
async def test_delete_obeys_ordinary_tool_approval(tmp_path, monkeypatch, blocked):
    post = Mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"deleted": True}})
    )
    monkeypatch.setattr(httpx, "post", post)
    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext(
            repo_root=tmp_path,
            cwd=tmp_path,
            safety=ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig()),
        ),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(
        TaskGraphTool(gateway_dispatch_url_provider=lambda: "http://127.0.0.1:123")
    )
    classifier = AsyncMock(
        return_value=SimpleNamespace(
            content=f"<block>{'yes' if blocked else 'no'}</block>"
        )
    )
    context = HookContext(
        session_id="session",
        repo_root=tmp_path,
        metadata={
            "agent_id": "pa",
            "run_id": "run",
            "tool_call_id": "delete",
            "_auto_mode_config_loader": lambda: AutoModeConfig(),
        },
        message_history=(
            LLMMessage(role="assistant", content="删除番茄炒蛋及其 5 个子任务？"),
            LLMMessage(role="user", content="对"),
        ),
        model_caller=classifier,
    )
    args = {
        "action": "delete",
        "graph_id": "tg_known",
        "base_revision": 2,
        "request_key": "delete",
    }
    if blocked:
        with pytest.raises(ToolError) as denied:
            await registry.execute("task_graph", args, hook_context=context)
        assert denied.value.details["reason_code"] == "denied"
        post.assert_not_called()
    else:
        result = await registry.execute("task_graph", args, hook_context=context)
        assert result["deleted"]
        assert post.call_args.kwargs["json"]["args"] == args
    classifier.assert_awaited()
    assert "tg_known" in classifier.call_args.args[0].user_prompt
