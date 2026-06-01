"""Build <task-notification> XML and prompt block for background tasks."""

from __future__ import annotations

from typing import Any, Mapping

from agent.core.background_tasks.models import BackgroundTaskRecord, BackgroundTaskType


BACKGROUND_TASK_PROMPT_BLOCK = (
    "<task-notification> messages are internal worker/system notifications "
    "delivered as user-role messages. They are not new user requests. "
    "Do not thank them. Use the result to continue the user's original task, "
    "synthesize any useful findings for the user, and read output_file only when details are needed."
)


def build_task_notification_xml(record: BackgroundTaskRecord) -> str:
    """Return a <task-notification> XML string for the given terminal record."""
    lines: list[str] = ["<task-notification>"]

    lines.append(f"<task-id>{_esc(record.task_id)}</task-id>")

    if record.task_type == BackgroundTaskType.SUBAGENT and record.agent_id:
        lines.append(f"<agent-id>{_esc(record.agent_id)}</agent-id>")

    lines.append(f"<output-file>{_esc(record.output_file)}</output-file>")
    lines.append(f"<status>{record.status.value}</status>")

    if record.task_type == BackgroundTaskType.SUBAGENT:
        lines.append(
            f'<summary>Agent "{_esc(record.description)}" {record.status.value}</summary>'
        )
    else:
        exit_code = record.exit_code
        exit_hint = f" with exit code {exit_code}" if exit_code is not None else ""
        lines.append(
            f'<summary>Command "{_esc(record.description)}" {record.status.value}{exit_hint}</summary>'
        )

    if record.result_text:
        lines.append(f"<result>{_esc(record.result_text)}</result>")
    if record.error and record.status.value != "completed":
        lines.append(f"<error>{_esc(record.error)}</error>")

    usage = record.usage
    if usage is not None:
        lines.append(_build_usage_xml(usage, record.tool_use_count, record.duration_ms))

    lines.append("</task-notification>")
    return "\n".join(lines)


def _build_usage_xml(
    usage: Mapping[str, Any],
    tool_use_count: int | None,
    duration_ms: int | None,
) -> str:
    parts: list[str] = ["<usage>"]
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
    """Minimal XML escape for notification content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
