"""Realtime tool events preserve machine-only correlation metadata."""

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.platform.hooks.builtins.realtime_stream import setup


async def test_tool_end_carries_event_metadata_verbatim() -> None:
    hooks = HookRegistry()
    setup(hooks)
    published: list[dict[str, object]] = []
    ctx = HookContext(
        session_id="sess_parent",
        turn_id="turn_parent",
        metadata={"run_id": "run_parent"},
        session_event_publisher=lambda event, data: published.append(data),
    )
    metadata = {
        "parent_session_id": "sess_parent",
        "parent_run_id": "run_parent",
        "parent_tool_call_id": "call_workflow",
        "workflow_run_id": "wf_123456",
    }

    await HookRunner(registry=hooks).dispatch_observe(
        "tool_result",
        {
            "run_id": "run_parent",
            "call_id": "call_workflow",
            "name": "Workflow",
            "arguments": {},
            "output": {"status": "async_launched"},
            "event_metadata": metadata,
        },
        ctx,
    )

    assert published[0]["event"] == "tool_end"
    assert published[0]["event_metadata"] == metadata
