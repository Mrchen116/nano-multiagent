"""Protect the native tool's authenticated loopback handoff and honest outcomes."""

from types import SimpleNamespace

import httpx
import pytest

from personal_assistant.tools.task_graph import TaskGraphTool


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
