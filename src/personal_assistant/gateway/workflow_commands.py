"""Parse and render Workflow commands shared by Web and external IM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent.sdk import WorkflowRunInfo

from personal_assistant.config.local_store import WORKFLOW_SIZE_GUIDELINES


WorkflowCommandKind = Literal[
    "list", "detail", "control", "save", "config", "effort", "invoke", "error"
]


@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    """One parsed Workflow slash command."""

    kind: WorkflowCommandKind
    run_id: str | None = None
    action: str | None = None
    agent_call_id: str | None = None
    scope: str | None = None
    name: str | None = None
    guideline: str | None = None
    effort: str | None = None
    arguments: str = ""
    error: str | None = None


def parse_workflow_command(
    text: str, *, named_workflows: tuple[str, ...]
) -> WorkflowCommand | None:
    """Parse one normalized slash command when Workflow is active."""

    parts = text.strip().split()
    if not parts:
        return None
    head = parts[0]
    if head == "/workflows":
        return _parse_workflows(parts)
    if head == "/config":
        return _parse_workflow_config(parts)
    if head == "/effort":
        if len(parts) == 2 and parts[1] in {"ultracode", "high"}:
            return WorkflowCommand(kind="effort", effort=parts[1])
        return WorkflowCommand(kind="error", error="用法: /effort <ultracode|high>")
    name = head.removeprefix("/")
    if head.startswith("/") and name in named_workflows:
        arguments = text.strip()[len(head) :].strip()
        return WorkflowCommand(kind="invoke", name=name, arguments=arguments)
    return None


def _parse_workflows(parts: list[str]) -> WorkflowCommand:
    if len(parts) == 1:
        return WorkflowCommand(kind="list")
    run_id = parts[1]
    if len(parts) == 2:
        return WorkflowCommand(kind="detail", run_id=run_id)
    action = parts[2]
    if action in {"pause", "resume", "stop"} and len(parts) == 3:
        return WorkflowCommand(kind="control", run_id=run_id, action=action)
    if action == "restart" and len(parts) == 4:
        return WorkflowCommand(
            kind="control",
            run_id=run_id,
            action="restart_agent",
            agent_call_id=parts[3],
        )
    if action == "save" and len(parts) in {4, 5}:
        scope = parts[3]
        if scope in {"project", "personal"}:
            return WorkflowCommand(
                kind="save",
                run_id=run_id,
                scope=scope,
                name=parts[4] if len(parts) == 5 else None,
            )
    return WorkflowCommand(
        kind="error",
        error=(
            "用法: /workflows [run-id [pause|resume|stop|restart <agent-call-id>|"
            "save <project|personal> [name]]]"
        ),
    )


def _parse_workflow_config(parts: list[str]) -> WorkflowCommand:
    if len(parts) == 3 and parts[1] == "workflowSizeGuideline":
        guideline = parts[2]
        if guideline in WORKFLOW_SIZE_GUIDELINES:
            return WorkflowCommand(kind="config", guideline=guideline)
    return WorkflowCommand(
        kind="error",
        error=("用法: /config workflowSizeGuideline <unrestricted|small|medium|large>"),
    )


def format_workflow_run(run: WorkflowRunInfo) -> str:
    """Render one complete SDK snapshot as an ordinary chat reply."""

    lines = [f"Workflow {run.run_id} · {run.name} · {run.status}"]
    if run.current_phase:
        lines.append(f"阶段: {run.current_phase}")
    if run.agents:
        completed = sum(agent.status == "completed" for agent in run.agents)
        lines.append(f"Agent: {completed}/{len(run.agents)} completed")
    if run.result is not None:
        lines.append(f"结果: {run.result}")
    if run.error:
        lines.append(f"错误: {run.error}")
    if run.usage:
        usage = ", ".join(f"{key}={value}" for key, value in run.usage.items())
        lines.append(f"Usage: {usage}")
    if run.duration_ms is not None:
        lines.append(f"耗时: {run.duration_ms / 1000:g}s")
    if run.transcript_dir:
        lines.append(f"诊断: {run.transcript_dir}")
    if run.script_path:
        lines.append(f"脚本: {run.script_path}")
    for warning in run.warnings:
        lines.append(f"警告: {warning}")
    return "\n".join(lines)


def format_workflow_runs(runs: tuple[WorkflowRunInfo, ...]) -> str:
    """Render a compact run list from the SDK truth."""

    if not runs:
        return "暂无 Workflow 运行记录。"
    return "\n".join(f"{run.run_id} · {run.name} · {run.status}" for run in runs)
