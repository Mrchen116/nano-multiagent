"""Exact-name `Workflow` tool for launching restricted Python orchestration."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.session.types import INTERNAL_RUNTIME_KEY
from agent.core.tools.base import ToolContext
from agent.core.types import ToolSpec
from agent.core.workflows import (
    OutputTokenBudget,
    WorkflowCompileError,
    compile_workflow,
)
from agent.platform.permissions.broker import PermissionDecision
from agent.platform.tools.presentation import ToolPresentationEvent, _truncate
from agent.platform.workflows import WorkflowLaunchContext, WorkflowManager
from agent.platform.workflows.consent import WorkflowConsentStore


_BASE_DESCRIPTION = (
    files("agent.platform.tools.builtins")
    .joinpath("workflow_tool_prompt.md")
    .read_text(encoding="utf-8")
    .strip()
)


def workflow_description(size_guideline: str = "medium") -> str:
    guidance = {
        "small": "small — keep workflows under 5 agents",
        "medium": "medium — keep workflows under 15 agents",
        "large": "large — keep workflows under 50 agents",
        "unrestricted": "unrestricted — no advisory agent-count limit",
    }
    resolved = guidance.get(size_guideline, guidance["medium"])
    return (
        _BASE_DESCRIPTION
        + "\nA workflow size guideline is configured for this session: "
        + resolved
        + ". This is a guideline, not a hard limit — follow it unless the user's prompt calls for a different scale."
    )


class _WorkflowPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return self.format_start_for_session(args, {})

    def format_start_for_session(
        self,
        args: Mapping[str, Any],
        session_metadata: Mapping[str, Any],
    ) -> ToolPresentationEvent:
        detail = _workflow_input_detail(args, session_metadata=session_metadata)
        return ToolPresentationEvent(
            visible=True,
            label="Workflow",
            summary=_truncate(str(detail["description"]), 80),
            detail=detail,
        )

    def format_end(
        self, args: Mapping[str, Any], result: Any, duration_ms: int
    ) -> ToolPresentationEvent:
        return self.format_end_for_session(args, result, duration_ms, {})

    def format_end_for_session(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
        session_metadata: Mapping[str, Any],
    ) -> ToolPresentationEvent:
        output = getattr(result, "output", None)
        error = getattr(result, "error", None)
        detail = _workflow_input_detail(args, session_metadata=session_metadata)
        result_fields: Mapping[str, Any] = output if isinstance(output, Mapping) else {}
        guideline = result_fields.get("guideline")
        if isinstance(guideline, str) and guideline:
            detail["guideline"] = guideline
        if error is not None:
            status = "failed"
            error_text = str(error)
        else:
            status = str(result_fields.get("status") or "")
            error_text = str(result_fields.get("error") or "")
        detail.update(
            {
                "status": status,
                "name": str(result_fields.get("name") or ""),
                "runId": str(result_fields.get("runId") or ""),
                "taskId": str(result_fields.get("taskId") or ""),
                "scriptPath": str(result_fields.get("scriptPath") or ""),
                "transcriptDir": str(result_fields.get("transcriptDir") or ""),
                "error": error_text,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Workflow",
            summary=_truncate(str(detail["description"]), 80),
            detail=detail,
        )


def _workflow_input_detail(
    args: Mapping[str, Any], *, session_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    script_path = _optional_string(args.get("scriptPath"))
    inline = args.get("script")
    name = _optional_string(args.get("name"))
    if script_path is not None:
        source = script_path
        script_preview = ""
    elif isinstance(inline, str) and inline:
        source = "inline Python"
        script_preview = inline
    else:
        source = name or ""
        script_preview = ""
    description = str(args.get("description") or args.get("title") or name or source)
    return {
        "description": description,
        "source": source,
        "guideline": _size_guideline(session_metadata),
        "script_preview": script_preview,
    }


class WorkflowTool:
    name = "Workflow"
    is_concurrency_safe = False
    max_result_size_chars = 20_000
    presenter = _WorkflowPresenter()
    description = workflow_description()
    input_schema = {
        "type": "object",
        "properties": {
            "script": {"type": "string", "maxLength": 524288},
            "scriptPath": {"type": "string"},
            "name": {"type": "string"},
            "args": {},
            "resumeFromRunId": {
                "type": "string",
                "pattern": "^wf_[a-z0-9-]{6,}$",
            },
            "description": {"type": "string"},
            "title": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        manager: WorkflowManager,
        named_resolver: Any | None = None,
        size_guideline: str = "medium",
        consent_store: WorkflowConsentStore | None = None,
    ) -> None:
        self._manager = manager
        self._named_resolver = named_resolver
        self._consent_store = consent_store
        self.description = workflow_description(size_guideline)

    def check_permissions(
        self, tool_input: Mapping[str, Any], ctx: Any
    ) -> PermissionDecision:
        source, identity = self._resolve_source(tool_input, ctx)
        try:
            compiled = compile_workflow(source)
        except WorkflowCompileError as exc:
            raise ToolError(str(exc), tool_name=self.name) from exc
        resolved_identity = identity or compiled.meta.name
        if self._consent_store is not None and self._consent_store.contains(
            resolved_identity
        ):
            return PermissionDecision(
                behavior="allow",
                decision_reason={
                    "type": "workflow_consent",
                    "identity": resolved_identity,
                },
            )
        session_metadata = _context_session_metadata(ctx)
        size_guideline, size_guideline_explicit = _size_guideline_setting(
            session_metadata
        )
        return PermissionDecision(
            behavior="ask",
            reason=_approval_question(
                name=compiled.meta.name,
                phases=tuple(phase.title for phase in compiled.meta.phases),
                size_guideline=size_guideline,
                size_guideline_explicit=size_guideline_explicit,
                ultracode=_workflow_ultracode(session_metadata),
            ),
            decision_reason={"type": "workflow_launch", "identity": resolved_identity},
        )

    def spec_for_session(self, session_metadata: Mapping[str, Any]) -> ToolSpec:
        """Project the session's resolved size guideline into the tool prompt."""

        return ToolSpec(
            name=self.name,
            description=workflow_description(_size_guideline(session_metadata)),
            input_schema=dict(self.input_schema),
            is_concurrency_safe=self.is_concurrency_safe,
            max_result_size_chars=self.max_result_size_chars,
        )

    def permission_identity(self, tool_input: Mapping[str, Any], ctx: Any) -> str:
        source, identity = self._resolve_source(tool_input, ctx)
        return identity or compile_workflow(source).meta.name

    def on_permission_decision(
        self, identity: str, decision: str, *, auto_mode: bool
    ) -> None:
        store = self._consent_store
        if store is None:
            return
        if decision == "allow_always" or (
            auto_mode and decision in {"allow_once", "allow_session"}
        ):
            store.add(identity)

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        source, _identity = self._resolve_source(args, ctx)
        size_guideline, size_guideline_explicit = _size_guideline_setting(
            ctx.session_metadata
        )
        runtime_snapshot = _capture_parent_runtime(ctx)
        context = WorkflowLaunchContext(
            parent_session_id=ctx.session_id or "",
            workspace_root=ctx.cwd,
            parent_run_id=_optional_string(ctx.session_metadata.get("run_id")),
            parent_tool_call_id=ctx.tool_call_id,
            subagent_control=ctx.subagent_control,
            workflow_ultracode=_workflow_ultracode(ctx.session_metadata),
            parent_run_origin=str(ctx.session_metadata.get("run_origin") or "user"),
            **runtime_snapshot,
        )
        try:
            launch = self._manager.launch(
                source=source,
                args=args.get("args"),
                context=context,
                resume_from_run_id=_optional_string(args.get("resumeFromRunId")),
                size_guideline=size_guideline,
                size_guideline_explicit=size_guideline_explicit,
                output_budget=_output_budget(ctx.session_metadata),
            )
        except (WorkflowCompileError, OSError, ValueError) as exc:
            raise ToolError(str(exc), tool_name=self.name) from exc
        return {
            "status": launch.status,
            "taskId": launch.task_id,
            "runId": launch.run_id,
            "name": launch.name,
            "scriptPath": launch.script_path,
            "diagnostics": launch.diagnostics,
            "transcriptDir": launch.diagnostics,
            "guideline": size_guideline,
            "parentSessionId": context.parent_session_id,
            "parentRunId": context.parent_run_id,
            "parentToolCallId": context.parent_tool_call_id,
        }

    def result_event_metadata(self, result: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "parent_session_id": result.get("parentSessionId"),
            "parent_run_id": result.get("parentRunId"),
            "parent_tool_call_id": result.get("parentToolCallId"),
            "workflow_run_id": result.get("runId"),
        }

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            return json.dumps(output, ensure_ascii=False)
        return (
            "Workflow launched in the background.\n\n"
            f"task_id: {output.get('taskId')}\n"
            f"run_id: {output.get('runId')}\n"
            f"script_path: {output.get('scriptPath')}\n"
            f"diagnostics: {output.get('diagnostics')}"
        )

    def _resolve_source(
        self, args: Mapping[str, Any], ctx: Any
    ) -> tuple[str, str | None]:
        script_path = _optional_string(args.get("scriptPath"))
        inline = args.get("script")
        name = _optional_string(args.get("name"))
        if script_path is not None:
            path = Path(script_path).expanduser()
            if not path.is_absolute():
                path = _context_cwd(ctx) / path
            try:
                return path.resolve().read_text(encoding="utf-8"), str(path.resolve())
            except OSError as exc:
                raise ToolError(
                    f"Unable to read Workflow scriptPath: {path}", tool_name=self.name
                ) from exc
        if isinstance(inline, str) and inline:
            if len(inline) > 524288:
                raise ToolError(
                    "Workflow script exceeds 524288 characters", tool_name=self.name
                )
            return inline, None
        if name is not None and self._named_resolver is not None:
            resolved = self._named_resolver.resolve(
                name, workspace_root=_context_cwd(ctx)
            )
            if resolved is not None:
                return Path(resolved.path).read_text(encoding="utf-8"), name
        raise ToolError(
            "Workflow requires scriptPath, script, or name",
            tool_name=self.name,
        )


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _context_cwd(ctx: Any) -> Path:
    """Resolve the workspace for both gate HookContext and execution ToolContext."""

    cwd = getattr(ctx, "cwd", None) or getattr(ctx, "repo_root", None)
    if not isinstance(cwd, Path):
        raise ToolError(
            "Workflow workspace is unavailable", tool_name=WorkflowTool.name
        )
    return cwd


def _context_session_metadata(ctx: Any) -> Mapping[str, Any]:
    """Read session metadata from either supported permission context shape."""

    metadata = getattr(ctx, "session_metadata", None)
    if metadata is None:
        metadata = getattr(ctx, "metadata", None)
    return metadata if isinstance(metadata, Mapping) else {}


def _capture_parent_runtime(ctx: ToolContext) -> dict[str, Any]:
    control = ctx.subagent_control
    if control is None:
        return {}
    parent = control.directory.get(control.ref)
    if parent is None:
        raise ToolError(
            "Workflow parent session is not available", tool_name=WorkflowTool.name
        )
    tools = (
        tuple(control.list_parent_enabled_tool_names())
        if parent.tool_allowlist is None
        else tuple(parent.tool_allowlist)
    )
    skills = tuple(parent.skills) if parent.skills is not None else None
    return {
        "parent_runtime_captured": True,
        "parent_model": control.resolve_run_model(),
        "parent_effort": control.resolve_reasoning_effort(),
        "parent_enabled_tools": tools,
        "parent_skills": skills,
    }


def _size_guideline(session_metadata: Mapping[str, Any]) -> str:
    return _size_guideline_setting(session_metadata)[0]


def _size_guideline_setting(
    session_metadata: Mapping[str, Any],
) -> tuple[str, bool]:
    runtime = session_metadata.get(INTERNAL_RUNTIME_KEY)
    if isinstance(runtime, Mapping):
        value = runtime.get("workflow_size_guideline")
        if value in {"unrestricted", "small", "medium", "large"}:
            return str(value), True
    return "medium", False


def _workflow_ultracode(session_metadata: Mapping[str, Any]) -> bool:
    runtime = session_metadata.get(INTERNAL_RUNTIME_KEY)
    return bool(
        session_metadata.get("workflow_ultracode")
        or (isinstance(runtime, Mapping) and runtime.get("workflow_ultracode") is True)
    )


def _approval_question(
    *,
    name: str,
    phases: tuple[str, ...],
    size_guideline: str,
    size_guideline_explicit: bool,
    ultracode: bool,
) -> str:
    phase_text = ", ".join(phases) if phases else "none declared"
    boundaries = {"small": 5, "medium": 15, "large": 50}
    if size_guideline_explicit and size_guideline in boundaries:
        scale = f"{size_guideline} (<{boundaries[size_guideline]} Agents)"
    elif size_guideline == "unrestricted":
        scale = "unrestricted (no Agent-count advisory boundary)"
    else:
        scale = "medium (default; advisory above 25 Agents)"
    advisory = (
        "Large workflow advisory is suppressed by ultracode."
        if ultracode
        else "Large workflow advisory includes estimated 1.5M tokens."
    )
    return (
        f"Run Python Workflow '{name}'? Phases: {phase_text}. "
        f"Scale: {scale}. {advisory}"
    )


def _output_budget(
    session_metadata: Mapping[str, Any],
) -> OutputTokenBudget | None:
    value = session_metadata.get("workflow_output_token_budget")
    return value if isinstance(value, OutputTokenBudget) else None
