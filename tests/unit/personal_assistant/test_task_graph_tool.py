"""Protect the native tool's authenticated loopback handoff and honest outcomes."""

from types import SimpleNamespace

import httpx
import pytest

from personal_assistant.tools.task_graph import TaskGraphTool


def test_native_tool_preserves_business_args_and_runtime_identity(monkeypatch):
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(200, json={"ok": True, "result": {"revision": 2}})

    monkeypatch.setattr(httpx, "post", post)
    ctx = SimpleNamespace(
        session_id="session", tool_call_id="call", session_metadata={"agent_id": "pa"}
    )
    tool = TaskGraphTool(
        gateway_dispatch_url_provider=lambda: "http://127.0.0.1:123/old"
    )
    args = {"action": "get", "graph_id": "tg_known"}
    assert tool.run(args, ctx) == {"revision": 2}
    assert seen[0][0] == "http://127.0.0.1:123/internal/task-graph"
    assert seen[0][1]["json"] == {
        "source_agent_id": "pa",
        "origin_kernel_session_id": "session",
        "tool_call_id": "call",
        "args": args,
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
        args.update(target="c_home", title="Plan", mode="dag", request_key="retry-same")
    ctx = SimpleNamespace(
        session_id="session", tool_call_id="call", session_metadata={"agent_id": "pa"}
    )
    tool = TaskGraphTool(
        gateway_dispatch_url_provider=lambda: "http://127.0.0.1:123/old"
    )
    with pytest.raises(RuntimeError, match=code) as error:
        tool.run(args, ctx)
    if action == "create":
        assert "retry-same" in str(error.value)
