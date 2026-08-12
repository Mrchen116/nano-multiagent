"""Internal schema-bound return tool for Workflow child Agents."""

from __future__ import annotations

from typing import Any, Mapping

from agent.core.tools.base import ToolContext
from agent.core.errors import ToolError
from agent.core.types import ToolSpec
from agent.platform.permissions.broker import PermissionDecision


class WorkflowStructuredOutputTool:
    """Expose a child-specific schema without parsing assistant prose."""

    name = "WorkflowStructuredOutput"
    description = "Return the validated value requested by the parent Workflow."
    input_schema: Mapping[str, Any] = {"type": "object"}
    is_concurrency_safe = True
    is_internal = True

    def spec_for_session(self, session_metadata: Mapping[str, Any]) -> ToolSpec | None:
        if session_metadata.get("kind") != "workflow_subagent":
            return None
        schema = session_metadata.get("workflow_output_schema")
        if not isinstance(schema, Mapping):
            return None
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=dict(schema),
            is_concurrency_safe=True,
        )

    def check_permissions(
        self, _tool_input: Mapping[str, Any], _ctx: ToolContext
    ) -> PermissionDecision:
        return PermissionDecision(behavior="allow")

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        schema = ctx.session_metadata.get("workflow_output_schema")
        if not isinstance(schema, Mapping):
            raise ToolError(
                "Workflow structured schema is unavailable", tool_name=self.name
            )
        import jsonschema  # type: ignore[import-untyped]  # noqa: PLC0415

        try:
            jsonschema.validate(dict(args), schema)
        except jsonschema.ValidationError as exc:
            raise ToolError(
                f"Workflow structured output failed validation: {exc.message}",
                tool_name=self.name,
            ) from exc
        return dict(args)

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        return error or "Structured Workflow result accepted."


__all__ = ["WorkflowStructuredOutputTool"]
