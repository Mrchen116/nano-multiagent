from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.tools.base import ToolContext
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.core.tools.registry import ToolRegistry
from agent.core.types import Message, ToolResult, TurnResult
from agent.platform.workflows.child import _extract_value
from agent.platform.workflows.structured_output import WorkflowStructuredOutputTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
    "additionalProperties": False,
}


async def test_internal_structured_output_projects_exact_schema_and_retries_invalid(
    tmp_path: Path,
) -> None:
    set_tool_safety_factory(ToolSafety)
    set_tool_safety_config_factory(ToolSafetyConfig)
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(WorkflowStructuredOutputTool())
    metadata = {
        "kind": "workflow_subagent",
        "workflow_output_schema": SCHEMA,
    }

    assert registry.list_specs() == ()
    projected = registry.list_specs_for_session(metadata)
    assert len(projected) == 1
    assert projected[0].input_schema == SCHEMA
    with pytest.raises(ToolError, match="expected as `integer`"):
        await registry.execute(
            "WorkflowStructuredOutput",
            {"answer": "not-an-int"},
            hook_context=HookContext(
                session_id="child",
                repo_root=tmp_path,
                metadata=metadata,
            ),
        )


def test_structured_agent_value_comes_only_from_validated_tool_result() -> None:
    turn = TurnResult(
        session_id="child",
        turn_id="turn",
        messages=(Message(message_id="m", role="assistant", content='{"answer": 0}'),),
        tool_results=(
            ToolResult(
                call_id="structured",
                name="WorkflowStructuredOutput",
                output={"answer": 42},
            ),
        ),
    )

    assert _extract_value(turn, SCHEMA) == {"answer": 42}
    with pytest.raises(ValueError, match="StructuredOutput tool"):
        _extract_value(
            TurnResult(
                session_id="child",
                turn_id="turn",
                messages=(
                    Message(
                        message_id="m",
                        role="assistant",
                        content='{"answer": 42}',
                    ),
                ),
            ),
            SCHEMA,
        )
