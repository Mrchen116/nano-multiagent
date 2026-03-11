"""Tool registration and execution pipeline with hook interception support."""

import asyncio
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.types import ToolSpec
from nano_multiagent.core.hooks.context import HookContext
from nano_multiagent.core.hooks.runner import HookExecution, HookRunner
from nano_multiagent.core.observability.logger import log_error, log_info
from nano_multiagent.core.observability.tracing import bind_correlation

from .base import Tool, ToolContext


class ToolRegistry:
    """Store tool definitions and execute them with hook-aware lifecycle events."""

    def __init__(self, *, context: ToolContext, hook_runner: HookRunner | None = None) -> None:
        self._context = context
        self._hook_runner = hook_runner
        self._tools: dict[str, Tool] = {}

    @property
    def context(self) -> ToolContext:
        """Return immutable execution context shared by all tools."""

        return self._context

    def register(self, tool: Tool) -> None:
        """Register one tool, rejecting empty or duplicate names."""

        name = str(getattr(tool, "name", "")).strip()
        if not name:
            raise ValueError("tool name is required")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool

    def register_many(self, tools: list[Tool] | tuple[Tool, ...]) -> None:
        """Register a sequence of tools in order."""

        for tool in tools:
            self.register(tool)

    def list_specs(self) -> tuple[ToolSpec, ...]:
        """Return sorted tool specs exposed to model-facing tool calling."""

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

    def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: HookContext | None = None,
    ) -> Mapping[str, Any]:
        """Execute one tool call and apply hook intercept/observe semantics."""

        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(
                f"unknown tool: {name}",
                tool_name=name,
                details={"available": sorted(self._tools.keys())},
            )

        active_hook_context = hook_context or HookContext(
            session_id="tool-registry",
            repo_root=self._context.repo_root,
            metadata={"cwd": str(self._context.cwd)},
        )
        tool_call_id = _extract_tool_call_id(args=args, hook_context=active_hook_context)

        with bind_correlation(
            session_id=active_hook_context.session_id,
            turn_id=active_hook_context.turn_id,
            tool_call_id=tool_call_id,
        ):
            tool_call_payload, _ = self._dispatch_intercept(
                "tool_call",
                {"name": name, "args": dict(args), "block": False, "reason": None},
                active_hook_context,
            )
            if bool(tool_call_payload.get("block")):
                log_error("tool_execution_error", tool_name=name, blocked_by_hook=True)
                raise ToolError(
                    "tool blocked by hook",
                    tool_name=name,
                    details={
                        "blocked_by_hook": True,
                        "reason": tool_call_payload.get("reason"),
                    },
                )

            payload_args = tool_call_payload.get("args")
            effective_args: Mapping[str, Any] = args
            if isinstance(payload_args, Mapping):
                effective_args = dict(payload_args)
            safety_overrides: dict[str, Any] = {}
            if bool(tool_call_payload.get("allow_unlisted")):
                safety_overrides["bash_allow_unlisted"] = True
            normalized_args = _validate_args(name=name, args=effective_args, schema=tool.input_schema)
            event_base_payload = _build_tool_execution_base_payload(
                name=name,
                args=normalized_args,
                hook_context=active_hook_context,
                tool_call_id=tool_call_id,
            )

            def _emit_execution_update(update_payload: Mapping[str, Any]) -> None:
                self._dispatch_observe(
                    "tool_execution_update",
                    {
                        **event_base_payload,
                        **dict(update_payload),
                    },
                    active_hook_context,
                )

            execution_context = self._context.with_session(
                active_hook_context.session_id,
                tool_call_id=tool_call_id,
                safety_overrides=safety_overrides,
                execution_event_callback=_emit_execution_update,
            )
            log_info("tool_execution_start", tool_name=name)
            self._dispatch_observe(
                "tool_execution_start",
                dict(event_base_payload),
                active_hook_context,
            )

            execution_error: ToolError | None = None
            raw_result: Mapping[str, Any] | Any | None = None
            try:
                raw_result = tool.run(normalized_args, execution_context)
            except ToolError as exc:
                execution_error = exc
            except Exception as exc:
                execution_error = ToolError(
                    f"tool execution failed: {exc}",
                    tool_name=name,
                    details={"exception_type": type(exc).__name__},
                )

            if execution_error is None:
                self._dispatch_observe(
                    "tool_execution_update",
                    {
                        **event_base_payload,
                        "output": raw_result,
                    },
                    active_hook_context,
                )
                self._dispatch_observe(
                    "tool_execution_end",
                    {
                        **event_base_payload,
                        "is_error": False,
                    },
                    active_hook_context,
                )
                log_info("tool_execution_end", tool_name=name, is_error=False)
            else:
                self._dispatch_observe(
                    "tool_execution_end",
                    {
                        **event_base_payload,
                        "is_error": True,
                        "error": str(execution_error),
                        "details": execution_error.details,
                    },
                    active_hook_context,
                )
                log_error("tool_execution_error", tool_name=name, error=str(execution_error))

            if self._hook_runner is None:
                if execution_error is not None:
                    raise execution_error
                if isinstance(raw_result, Mapping):
                    return dict(raw_result)
                return {"result": raw_result}

            tool_result_payload: dict[str, Any] = {
                "name": name,
                "args": normalized_args,
                "output": raw_result,
                "is_error": execution_error is not None,
            }
            if execution_error is not None:
                tool_result_payload["error"] = str(execution_error)
                tool_result_payload["details"] = execution_error.details

            rewritten_payload, _ = self._dispatch_intercept(
                "tool_result",
                tool_result_payload,
                active_hook_context,
            )
            rewritten_output: Any = rewritten_payload.get("output", raw_result)

            if bool(rewritten_payload.get("is_error")):
                error_message = rewritten_payload.get("error")
                if not isinstance(error_message, str) or not error_message:
                    error_message = "tool result marked as error by hook"
                details = rewritten_payload.get("details")
                if not isinstance(details, Mapping):
                    details = execution_error.details if execution_error is not None else {}
                raise ToolError(
                    error_message,
                    tool_name=name,
                    details=dict(details),
                )

            if "content" in rewritten_payload:
                content = rewritten_payload["content"]
                if isinstance(content, Mapping):
                    return dict(content)
                if isinstance(content, list):
                    return {"content": content}
                return {"result": content}

            if execution_error is not None and "output" not in rewritten_payload:
                raise execution_error
            if isinstance(rewritten_output, Mapping):
                return dict(rewritten_output)
            return {"result": rewritten_output}

    def _dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> tuple[dict[str, Any], bool]:
        """Dispatch intercept hook event and return rewritten payload."""

        if self._hook_runner is None:
            return dict(payload), False
        try:
            dispatch_result = asyncio.run(
                self._hook_runner.dispatch_intercept(
                    event,
                    payload,
                    hook_ctx,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            # FAIL-OPEN GUARANTEE: hook infra failure must not block tool execution path.
            hook_ctx.logger.warn("hook intercept dispatch failed", event=event, error=str(exc))
            return dict(payload), False
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=dispatch_result.diagnostics)
        return dispatch_result.payload, dispatch_result.stopped

    def _dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        """Dispatch observe hooks while isolating failures from business flow."""

        if self._hook_runner is None:
            return
        try:
            diagnostics = asyncio.run(
                self._hook_runner.dispatch_observe(
                    event,
                    payload,
                    hook_ctx,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            # FAIL-OPEN GUARANTEE: observe hooks are telemetry-only and cannot break tool flow.
            hook_ctx.logger.warn("hook observe dispatch failed", event=event, error=str(exc))
            return
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=diagnostics)

    @staticmethod
    def _log_hook_diagnostics(
        hook_ctx: HookContext,
        *,
        event: str,
        diagnostics: tuple[HookExecution, ...],
    ) -> None:
        for item in diagnostics:
            if item.status == "ok":
                continue
            hook_ctx.logger.warn(
                "hook execution isolated",
                event=event,
                hook_id=item.hook_id,
                status=item.status,
                duration_ms=item.duration_ms,
                error=item.error,
            )


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


def _extract_tool_call_id(*, args: Mapping[str, Any], hook_context: HookContext) -> str | None:
    for key in ("tool_call_id", "call_id"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    metadata_value = hook_context.metadata.get("tool_call_id")
    if isinstance(metadata_value, str) and metadata_value.strip():
        return metadata_value
    return None


def _build_tool_execution_base_payload(
    *,
    name: str,
    args: Mapping[str, Any],
    hook_context: HookContext,
    tool_call_id: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "args": dict(args),
    }
    if hook_context.turn_id is not None:
        payload["turn_id"] = hook_context.turn_id
    if tool_call_id is not None:
        payload["call_id"] = tool_call_id
    run_id = hook_context.metadata.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        payload["run_id"] = run_id.strip()
    return payload


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
