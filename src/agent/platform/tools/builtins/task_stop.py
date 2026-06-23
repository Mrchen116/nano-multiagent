"""Built-in `task_stop` tool for stopping background subagent and bash tasks."""

from typing import Any, Mapping

from agent.core.background_tasks.models import BackgroundTaskType
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.tools.base import WiringMixin
from agent.platform.tools.presentation import ToolPresentationEvent


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
# ---------------------------------------------------------------------------


class _TaskStopPresenter:
    """Presenter for the `task_stop` tool. Result is ``{status, task_id, ...}``."""

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="TaskStop",
            summary=str(args.get("task_id", "")),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        task_id = str(args.get("task_id", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            # feat-409 failalign: 失败态 summary = 干净主参数(task_id),不含 error 文本。
            # detail 只放 error(task_id 已在折叠行 summary),走前端 ErrorCard 渲染一次。
            return ToolPresentationEvent(
                visible=True,
                label="TaskStop",
                summary=task_id or "failed",
                detail={"error": {"message": str(error)}},
            )
        status = (
            str(output.get("status", "killed"))
            if isinstance(output, Mapping)
            else "killed"
        )
        detail = {
            "task_id": str(output.get("task_id", task_id))
            if isinstance(output, Mapping)
            else task_id,
            "status": status,
        }
        if isinstance(output, Mapping):
            if output.get("task_type"):
                detail["task_type"] = str(output["task_type"])
            if output.get("output_file"):
                detail["output_file"] = str(output["output_file"])
        return ToolPresentationEvent(
            visible=True,
            label="TaskStop",
            # feat-409 protoalign: 折叠 summary 对齐原型 `停止后台任务 bash-21c9`
            # —— 人话动作 + task_id,而非裸 `killed bash-21c9`。
            summary=f"停止后台任务 {task_id}".strip(),
            detail=detail,
        )


_TASK_STOP_PRESENTER = _TaskStopPresenter()


class TaskStopTool(WiringMixin):
    """Stop a running background task (subagent or bash) by ID."""

    name = "task_stop"
    is_concurrency_safe = False
    max_result_size_chars = 2_000
    presenter = (
        _TASK_STOP_PRESENTER  # 决策 12: presentation travels with the tool object
    )
    description = (
        "Stop a running background task by its task_id. "
        "Works for both background subagents (agent_id) and background bash commands (task_id). "
        "The task is marked as killed. Stopping a bash task is confirmed by this "
        "tool's result only (no extra notification is sent). Stopping a subagent "
        "additionally sends a notification carrying the subagent's partial result."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the background task to stop. For subagents, this is the agent_id.",
            },
        },
        "required": ["task_id"],
        "additionalProperties": False,
    }

    def __init__(self, *, wiring: Any | None = None) -> None:
        self._wiring = wiring

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Stop the background task identified by ``task_id``."""
        task_id = str(args.get("task_id", "")).strip()
        if not task_id:
            raise ToolError("task_id is required", tool_name=self.name)

        wiring = self._require_wiring()
        registry = wiring.registry

        record = registry.get(task_id)
        if record is None:
            raise ToolError(
                f"No background task found with ID '{task_id}'.",
                tool_name=self.name,
                details={"code": "task_not_found"},
            )

        if record.status.value in ("completed", "failed", "killed"):
            raise ToolError(
                f"Task '{task_id}' is already {record.status.value}.",
                tool_name=self.name,
                details={
                    "code": "task_already_terminal",
                    "status": record.status.value,
                },
            )

        # Invoke the runner's stop handle (e.g., terminate process tree, abort LLM run).
        stopped = registry.request_stop(task_id)
        if not stopped:
            raise ToolError(
                f"Task '{task_id}' could not be stopped.",
                tool_name=self.name,
                details={"code": "task_stop_failed"},
            )

        # bugfix-420: branch by task type, mirroring CC stopTask.ts.
        #  - subagent: do NOT synchronously kill. request_stop already signalled
        #    a cooperative abort; the worker's abort-unwind path transitions the
        #    record terminal via on_kill, carrying the partial <result>. Killing
        #    here would win the "first terminal" race and drop that result.
        #  - bash: synchronously kill with notified=True so the _NotifyingStore
        #    suppresses the model-facing <task-notification> (the LLM already has
        #    the tool_result; a killed/exit notification would be pure noise).
        if record.task_type != BackgroundTaskType.SUBAGENT:
            registry.kill(task_id, reason="stopped by user", notified=True)

        return {
            "status": "killed",
            "task_id": task_id,
            "task_type": record.task_type.value,
            "output_file": record.output_file,
        }

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            return json_serialize(output)

        if output.get("status") == "killed":
            lines = [
                "Task stopped.",
                "",
                f"task_id: {output.get('task_id', '')}",
                f"task_type: {output.get('task_type', '')}",
                "status: killed",
            ]
            if output.get("output_file"):
                lines.append(f"output_file: {output['output_file']}")
            return "\n".join(lines)

        return json_serialize(output)
