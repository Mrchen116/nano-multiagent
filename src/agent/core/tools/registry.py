"""Canonical tool registration and execution pipeline with hook support."""

import asyncio
from pathlib import Path
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.observability.logger import log_error, log_info
from agent.core.observability.tracing import bind_correlation
from agent.core.types import ToolSpec

from .base import Tool, ToolContext, _build_default_tool_safety_config, _require_tool_safety_factory
from .result_budget import DEFAULT_MAX_RESULT_SIZE_CHARS
from .session_file_state import SessionFileState


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

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        """Register one tool, optionally replacing an earlier layer.

        Args:
            tool: Tool object exposing the canonical name/description/schema/run contract.
            replace: When ``True``, a same-name tool from a higher-priority layer
                replaces the previously registered one. When ``False``, duplicates
                are rejected to preserve legacy strictness for direct callers.
        """

        name = str(getattr(tool, "name", "")).strip()
        if not name:
            raise ValueError("tool name is required")
        if name in self._tools and not replace:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool

    def register_many(self, tools: list[Tool] | tuple[Tool, ...]) -> None:
        """Register a sequence of tools in order."""

        for tool in tools:
            self.register(tool)

    def list_specs(self) -> tuple[ToolSpec, ...]:
        """Return tool specs in registration order for layer-aware callers.

        Returns:
            Immutable tool specs preserving the effective precedence order after
            built-ins, product tools, and higher-priority user overrides are loaded.
        """

        return tuple(
            ToolSpec(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.input_schema),
                is_concurrency_safe=getattr(tool, "is_concurrency_safe", False),
                max_result_size_chars=getattr(tool, "max_result_size_chars", DEFAULT_MAX_RESULT_SIZE_CHARS),
            )
            for tool in self._tools.values()
        )

    def get(self, name: str) -> Tool | None:
        """Return one registered tool by name.

        Args:
            name: Canonical tool identifier.

        Returns:
            The registered tool instance, or ``None`` when the name is unknown.
        """

        return self._tools.get(name)

    def get_tool(self, name: str) -> Tool | None:
        """Alias for ``get`` to satisfy the ``ToolRegistryLike`` protocol."""
        return self.get(name)

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: HookContext | None = None,
        session_file_state: SessionFileState | None = None,
    ) -> Mapping[str, Any]:
        """Execute one tool call and apply hook intercept/observe semantics."""

        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(
                f"unknown tool: {name}",
                tool_name=name,
                details={"available": sorted(self._tools.keys())},
            )

        _base_hook_context = hook_context or HookContext(
            session_id="tool-registry",
            repo_root=self._context.repo_root,
            metadata={"cwd": str(self._context.cwd)},
        )
        # M6 (bugfix-355 D10): inject self as tool_registry so auto_mode_gate can call
        # tool.check_permissions without a hardcoded per-tool block (step 1 / step 5).
        # Merge without overwriting caller-supplied values; caller may already have set
        # tool_registry (e.g. agent loop injects its own registry reference).
        _existing_meta = dict(_base_hook_context.metadata)
        if "tool_registry" not in _existing_meta:
            _existing_meta["tool_registry"] = self
        import dataclasses
        active_hook_context = dataclasses.replace(_base_hook_context, metadata=_existing_meta)
        tool_call_id = _extract_tool_call_id(args=args, hook_context=active_hook_context)

        with bind_correlation(
            session_id=active_hook_context.session_id,
            turn_id=active_hook_context.turn_id,
            tool_call_id=tool_call_id,
        ):
            # bugfix-367: payload 同时携带 `call_id` 与 `arguments` 别名，以便
            # observe handler（realtime_stream.on_tool_call）拿到与原 loop.py 触发时
            # 相同的字段。registry 是 tool_call hook 唯一的触发点，gate 通过后
            # observe handler 才会运行，前端因此只在真正开始执行时看到 "运行中"。
            _run_id_meta = active_hook_context.metadata.get("run_id") if isinstance(active_hook_context.metadata, Mapping) else None
            tool_call_payload, _ = await self._dispatch_intercept(
                "tool_call",
                {
                    "name": name,
                    "args": dict(args),
                    "arguments": dict(args),
                    "call_id": tool_call_id,
                    "run_id": _run_id_meta if isinstance(_run_id_meta, str) and _run_id_meta else None,
                    "block": False,
                    "reason": None,
                },
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

            # Collect execution updates emitted during tool.run() and flush them
            # after the synchronous run completes.
            _pending_updates: list[dict[str, Any]] = []

            def _emit_execution_update(update_payload: Mapping[str, Any]) -> None:
                _pending_updates.append({**event_base_payload, **dict(update_payload)})

            execution_base_context = _resolve_execution_context(self._context, active_hook_context)
            # Forward session metadata from hook context so product tools (e.g.
            # send_message) can read runtime-injected fields like gateway_dispatch_url.
            execution_context = execution_base_context.with_session(
                active_hook_context.session_id,
                tool_call_id=tool_call_id,
                safety_overrides=safety_overrides,
                execution_event_callback=_emit_execution_update,
                session_metadata=dict(active_hook_context.metadata) if active_hook_context.metadata else {},
                session_file_state=session_file_state,
            )
            log_info("tool_execution_start", tool_name=name)
            await self._dispatch_observe(
                "tool_execution_start",
                dict(event_base_payload),
                active_hook_context,
            )

            execution_error: ToolError | None = None
            raw_result: Mapping[str, Any] | Any | None = None
            try:
                raw_result = await asyncio.to_thread(tool.run, normalized_args, execution_context)
            except ToolError as exc:
                execution_error = exc
            except Exception as exc:
                execution_error = ToolError(
                    f"tool execution failed: {exc}",
                    tool_name=name,
                    details={"exception_type": type(exc).__name__},
                )

            # Flush any tool-execution updates that accumulated during the run.
            for update in _pending_updates:
                await self._dispatch_observe("tool_execution_update", update, active_hook_context)

            if execution_error is None:
                await self._dispatch_observe(
                    "tool_execution_update",
                    {
                        **event_base_payload,
                        "output": raw_result,
                    },
                    active_hook_context,
                )
                await self._dispatch_observe(
                    "tool_execution_end",
                    {
                        **event_base_payload,
                        "is_error": False,
                    },
                    active_hook_context,
                )
                log_info("tool_execution_end", tool_name=name, is_error=False)
            else:
                await self._dispatch_observe(
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

            rewritten_payload, _ = await self._dispatch_intercept(
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

    async def _dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> tuple[dict[str, Any], bool]:
        """Dispatch intercept hook event and return rewritten payload."""

        if self._hook_runner is None:
            return dict(payload), False
        try:
            dispatch_result = await self._hook_runner.dispatch_intercept(
                event,
                payload,
                hook_ctx,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warn("hook intercept dispatch failed", event=event, error=str(exc))
            return dict(payload), False
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=dispatch_result.diagnostics)
        return dispatch_result.payload, dispatch_result.stopped

    async def _dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        """Dispatch observe hooks while isolating failures from business flow."""

        if self._hook_runner is None:
            return
        try:
            diagnostics = await self._hook_runner.dispatch_observe(
                event,
                payload,
                hook_ctx,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
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
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ToolError("invalid tool schema required list", tool_name=name)

    additional_properties = schema.get("additionalProperties", True)
    if isinstance(additional_properties, bool):
        allow_unknown = additional_properties
    else:
        allow_unknown = True

    normalized = dict(args)

    missing = [field for field in required if field not in normalized]
    if missing:
        if "load_skills" in missing:
            raise ToolError(
                "missing required argument: load_skills",
                tool_name=name,
                details={"missing": missing},
            )
        if len(missing) == 1:
            raise ToolError(
                f"missing required argument: {missing[0]}",
                tool_name=name,
                details={"missing": missing},
            )
        raise ToolError(
            "missing required tool args",
            tool_name=name,
            details={"missing": missing},
        )

    if not allow_unknown:
        unknown = sorted(key for key in normalized if key not in properties)
        if unknown:
            raise ToolError(
                "unexpected tool args",
                tool_name=name,
                details={"unknown": unknown},
            )

    for field_name, field_schema in properties.items():
        if field_name not in normalized:
            continue
        _validate_value(
            tool_name=name,
            field_name=field_name,
            value=normalized[field_name],
            schema=field_schema,
        )

    return normalized


def _validate_value(*, tool_name: str, field_name: str, value: Any, schema: Any) -> None:
    if not isinstance(schema, Mapping):
        return

    expected_type = schema.get("type")
    if expected_type == "string":
        if not isinstance(value, str):
            raise ToolError(
                "tool arg has invalid type",
                tool_name=tool_name,
                details={"field": field_name, "expected": "string"},
            )
    elif expected_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolError(
                "tool arg has invalid type",
                tool_name=tool_name,
                details={"field": field_name, "expected": "integer"},
            )
    elif expected_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolError(
                "tool arg has invalid type",
                tool_name=tool_name,
                details={"field": field_name, "expected": "number"},
            )
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            raise ToolError(
                "tool arg has invalid type",
                tool_name=tool_name,
                details={"field": field_name, "expected": "boolean"},
            )
    elif expected_type == "array":
        if not isinstance(value, list):
            raise ToolError(
                "tool arg has invalid type",
                tool_name=tool_name,
                details={"field": field_name, "expected": "array"},
            )


def _extract_tool_call_id(*, args: Mapping[str, Any], hook_context: HookContext) -> str | None:
    metadata = hook_context.metadata
    if isinstance(metadata, Mapping):
        raw_tool_call_id = metadata.get("tool_call_id")
        if isinstance(raw_tool_call_id, str) and raw_tool_call_id:
            return raw_tool_call_id
    raw_arg_call_id = args.get("tool_call_id")
    if isinstance(raw_arg_call_id, str) and raw_arg_call_id:
        return raw_arg_call_id
    return None


def _resolve_execution_context(base_context: ToolContext, hook_context: HookContext) -> ToolContext:
    """Return base tool context or clone it with session-scoped cwd override."""
    resolved_cwd = _metadata_path(hook_context.metadata, key="cwd")
    if resolved_cwd is None:
        return base_context
    # When the session workspace differs from the global repo root, rebuild the
    # safety sandbox so that file tools can access files in the workspace.
    if resolved_cwd != base_context.repo_root:
        safety_config = getattr(base_context.safety, "config", None) or _build_default_tool_safety_config()
        safety = _require_tool_safety_factory()(repo_root=resolved_cwd, config=safety_config)
        repo_root = resolved_cwd
    else:
        safety = base_context.safety
        repo_root = base_context.repo_root
    return ToolContext(
        repo_root=repo_root,
        cwd=resolved_cwd,
        safety=safety,
        session_id=base_context.session_id,
        tool_call_id=base_context.tool_call_id,
        safety_overrides=base_context.safety_overrides,
        execution_event_callback=base_context.execution_event_callback,
        llm_client=base_context.llm_client,
    )


def _metadata_path(metadata: Mapping[str, Any], *, key: str) -> Path | None:
    """Resolve one absolute path-like metadata field when present."""
    raw_value = metadata.get(key)
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    candidate = Path(normalized).expanduser()
    if not candidate.is_absolute():
        return None
    return candidate.resolve()


def _build_tool_execution_base_payload(
    *,
    name: str,
    args: Mapping[str, Any],
    hook_context: HookContext,
    tool_call_id: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": hook_context.session_id,
        "turn_id": hook_context.turn_id,
        "name": name,
        "args": dict(args),
    }
    if tool_call_id is not None:
        payload["tool_call_id"] = tool_call_id
    run_id = hook_context.metadata.get("run_id") if isinstance(hook_context.metadata, Mapping) else None
    if isinstance(run_id, str) and run_id:
        payload["run_id"] = run_id
    return payload
