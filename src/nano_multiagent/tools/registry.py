from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.types import ToolSpec

from .base import Tool, ToolContext


class ToolRegistry:
    def __init__(self, *, context: ToolContext) -> None:
        self._context = context
        self._tools: dict[str, Tool] = {}

    @property
    def context(self) -> ToolContext:
        return self._context

    def register(self, tool: Tool) -> None:
        name = str(getattr(tool, "name", "")).strip()
        if not name:
            raise ValueError("tool name is required")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool

    def register_many(self, tools: list[Tool] | tuple[Tool, ...]) -> None:
        for tool in tools:
            self.register(tool)

    def list_specs(self) -> tuple[ToolSpec, ...]:
        specs: list[ToolSpec] = []
        for name in sorted(self._tools):
            tool = self._tools[name]
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description,
                    input_schema=dict(tool.input_schema),
                )
            )
        return tuple(specs)

    def execute(self, name: str, args: Mapping[str, Any]) -> Mapping[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(
                f"unknown tool: {name}",
                tool_name=name,
                details={"available": sorted(self._tools.keys())},
            )

        normalized_args = _validate_args(name=name, args=args, schema=tool.input_schema)
        try:
            result = tool.run(normalized_args, self._context)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"tool execution failed: {exc}",
                tool_name=name,
                details={"exception_type": type(exc).__name__},
            ) from exc

        if isinstance(result, Mapping):
            return dict(result)
        return {"result": result}


def _validate_args(*, name: str, args: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise ToolError("tool args must be an object", tool_name=name)

    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise ToolError("tool schema must be type=object", tool_name=name)

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise ToolError("invalid tool schema properties", tool_name=name)

    required = schema.get("required", [])
    if not isinstance(required, list):
        raise ToolError("invalid tool schema required", tool_name=name)

    normalized = dict(args)

    for required_field in required:
        if required_field not in normalized:
            raise ToolError(
                f"missing required argument: {required_field}",
                tool_name=name,
                details={"required": required},
            )

    additional_properties = schema.get("additionalProperties", True)
    if additional_properties is False:
        extras = sorted(set(normalized.keys()) - set(properties.keys()))
        if extras:
            raise ToolError(
                f"unexpected argument(s): {', '.join(extras)}",
                tool_name=name,
                details={"unexpected": extras},
            )

    for key, value in normalized.items():
        field_schema = properties.get(key)
        if not isinstance(field_schema, Mapping):
            continue
        expected_type = field_schema.get("type")
        if expected_type is None:
            continue
        if not _matches_json_type(value, str(expected_type)):
            raise ToolError(
                f"invalid argument type for '{key}'",
                tool_name=name,
                details={"expected": expected_type, "actual": type(value).__name__},
            )

    return normalized


def _matches_json_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, Mapping)
    return True
