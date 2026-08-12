"""Project terminal background records into model XML and structured returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agent.core.background_tasks.models import BackgroundTaskRecord, BackgroundTaskType


BACKGROUND_TASK_PROMPT_BLOCK = (
    "<task-notification> messages are internal worker/system notifications "
    "delivered as user-role messages. They are not new user requests. "
    "Do not thank them. Use the result to continue the user's original task, "
    "synthesize any useful findings for the user, and read output_file only when details are needed."
)


@dataclass(frozen=True, slots=True)
class BackgroundReturnInfo:
    """Describe one raw subagent or Workflow terminal return."""

    task_id: str
    task_type: str
    status: str
    description: str
    agent_id: str | None = None
    workflow_run_id: str | None = None
    result: str | None = None
    error: str | None = None
    usage: Mapping[str, Any] | None = None
    tool_use_count: int | None = None
    duration_ms: int | None = None
    output_file: str | None = None
    diagnostics: str | None = None
    resume_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the compact stream-safe representation, omitting absent fields."""

        values = {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "description": self.description,
            "agent_id": self.agent_id,
            "workflow_run_id": self.workflow_run_id,
            "result": self.result,
            "error": self.error,
            "usage": dict(self.usage) if self.usage is not None else None,
            "tool_use_count": self.tool_use_count,
            "duration_ms": self.duration_ms,
            "output_file": self.output_file,
            "diagnostics": self.diagnostics,
            "resume_hint": self.resume_hint,
        }
        return {key: value for key, value in values.items() if value is not None}


@dataclass(frozen=True, slots=True)
class BackgroundNotification:
    """Hold both projections produced from one terminal task record."""

    xml: str
    background_return: BackgroundReturnInfo | None


@dataclass(frozen=True, slots=True)
class _NotificationProjection:
    task_id: str
    task_type: BackgroundTaskType
    status: str
    description: str
    agent_id: str | None
    workflow_run_id: str | None
    output_file: str
    result: str | None
    error: str | None
    exit_code: int | None
    usage: Mapping[str, Any] | None
    tool_use_count: int | None
    duration_ms: int | None
    diagnostics: str | None
    resume_hint: str | None


def build_background_notification(
    record: BackgroundTaskRecord,
) -> BackgroundNotification:
    """Build model XML and optional UI sidecar from one immutable projection."""

    projection = _project(record)
    return BackgroundNotification(
        xml=_render_xml(projection),
        background_return=_render_background_return(projection),
    )


def build_task_notification_xml(record: BackgroundTaskRecord) -> str:
    """Return the model-facing XML for a terminal task record."""

    return build_background_notification(record).xml


def _project(record: BackgroundTaskRecord) -> _NotificationProjection:
    return _NotificationProjection(
        task_id=record.task_id,
        task_type=record.task_type,
        status=record.status.value,
        description=record.description,
        agent_id=record.agent_id,
        workflow_run_id=record.workflow_run_id,
        output_file=record.output_file,
        result=record.result_text,
        error=record.error,
        exit_code=record.exit_code,
        usage=record.usage,
        tool_use_count=record.tool_use_count,
        duration_ms=record.duration_ms,
        diagnostics=record.diagnostics,
        resume_hint=record.resume_hint,
    )


def _render_xml(projection: _NotificationProjection) -> str:
    lines = ["<task-notification>", f"<task-id>{_esc(projection.task_id)}</task-id>"]
    if projection.agent_id:
        lines.append(f"<agent-id>{_esc(projection.agent_id)}</agent-id>")
    if projection.workflow_run_id:
        lines.append(
            f"<workflow-run-id>{_esc(projection.workflow_run_id)}</workflow-run-id>"
        )
    lines.append(f"<output-file>{_esc(projection.output_file)}</output-file>")
    lines.append(f"<status>{projection.status}</status>")
    if projection.task_type is BackgroundTaskType.SUBAGENT:
        summary = f'Agent "{_esc(projection.description)}" {projection.status}'
    elif projection.task_type is BackgroundTaskType.WORKFLOW:
        summary = f'Workflow "{_esc(projection.description)}" {projection.status}'
    else:
        exit_hint = (
            f" with exit code {projection.exit_code}"
            if projection.exit_code is not None
            else ""
        )
        summary = (
            f'Command "{_esc(projection.description)}" {projection.status}{exit_hint}'
        )
    lines.append(f"<summary>{summary}</summary>")
    if projection.result:
        lines.append(f"<result>{_esc(projection.result)}</result>")
    if projection.error and projection.status != "completed":
        lines.append(f"<error>{_esc(projection.error)}</error>")
    if projection.diagnostics:
        lines.append(f"<diagnostics>{_esc(projection.diagnostics)}</diagnostics>")
    if projection.resume_hint:
        lines.append(f"<resume-hint>{_esc(projection.resume_hint)}</resume-hint>")
    if projection.usage is not None:
        lines.append(
            _build_usage_xml(
                projection.usage,
                projection.tool_use_count,
                projection.duration_ms,
            )
        )
    lines.append("</task-notification>")
    return "\n".join(lines)


def _render_background_return(
    projection: _NotificationProjection,
) -> BackgroundReturnInfo | None:
    if projection.task_type not in {
        BackgroundTaskType.SUBAGENT,
        BackgroundTaskType.WORKFLOW,
    }:
        return None
    return BackgroundReturnInfo(
        task_id=projection.task_id,
        task_type=projection.task_type.value,
        status=projection.status,
        description=projection.description,
        agent_id=projection.agent_id,
        workflow_run_id=projection.workflow_run_id,
        result=projection.result,
        error=projection.error,
        usage=projection.usage,
        tool_use_count=projection.tool_use_count,
        duration_ms=projection.duration_ms,
        output_file=projection.output_file or None,
        diagnostics=projection.diagnostics,
        resume_hint=projection.resume_hint,
    )


def _build_usage_xml(
    usage: Mapping[str, Any],
    tool_use_count: int | None,
    duration_ms: int | None,
) -> str:
    parts = ["<usage>"]
    total = usage.get("total_tokens")
    if isinstance(total, int):
        parts.append(f"<total-tokens>{total}</total-tokens>")
    if isinstance(tool_use_count, int):
        parts.append(f"<tool-uses>{tool_use_count}</tool-uses>")
    if isinstance(duration_ms, int):
        parts.append(f"<duration-ms>{duration_ms}</duration-ms>")
    parts.append("</usage>")
    return "".join(parts)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
