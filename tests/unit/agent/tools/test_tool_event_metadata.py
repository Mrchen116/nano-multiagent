"""Machine correlation travels beside, never inside, tool output."""

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from agent.core.agent.tool_executor import StreamingToolExecutor
from agent.core.types import ToolCall


class _Tool:
    name = "Workflow"
    is_concurrency_safe = False


class _Registry:
    def get(self, name: str) -> _Tool | None:
        return _Tool() if name == "Workflow" else None

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: Any | None = None,
        session_file_state: Any | None = None,
        out_meta: dict[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        del name, args, hook_context, session_file_state
        assert out_meta is not None
        out_meta["event_metadata"] = {
            "parent_session_id": "sess_parent",
            "parent_run_id": "run_parent",
            "parent_tool_call_id": "call_workflow",
            "workflow_run_id": "wf_123456",
        }
        return {"status": "async_launched", "runId": "wf_123456"}


@pytest.mark.asyncio
async def test_tool_result_keeps_event_metadata_out_of_model_output() -> None:
    executor = StreamingToolExecutor(_Registry())  # type: ignore[arg-type]
    executor.add_tool(ToolCall(call_id="call_workflow", name="Workflow", arguments={}))
    await asyncio.sleep(0)

    result = [item async for item in executor.get_remaining_results()][0]

    assert result.output == {"status": "async_launched", "runId": "wf_123456"}
    assert "event_metadata" not in result.output
    assert result.event_metadata == {
        "parent_session_id": "sess_parent",
        "parent_run_id": "run_parent",
        "parent_tool_call_id": "call_workflow",
        "workflow_run_id": "wf_123456",
    }
