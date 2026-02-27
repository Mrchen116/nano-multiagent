from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from time import perf_counter
from typing import Any, Mapping, Protocol

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.ids import make_tool_call_id
from nano_multiagent.core.types import Message, TurnResult

from ..base import ToolContext


class TaskRuntime(Protocol):
    def create_session(self):  # noqa: ANN201
        ...

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        ...

    def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        ...


class TaskTool:
    name = "task"
    description = "Run or schedule a local in-process subagent task."
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["blocking", "non_blocking"],
            },
            "prompt": {"type": "string"},
            "session_id": {"type": "string"},
            "category": {"type": "string"},
            "subagent_type": {"type": "string"},
            "idempotency_key": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["mode"],
        "additionalProperties": False,
    }

    def __init__(self, *, runtime: TaskRuntime | None = None) -> None:
        self._runtime = runtime
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nano-task")

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        mode = str(args["mode"]).strip()
        if mode == "blocking":
            return self._run_blocking(args, ctx)
        if mode == "non_blocking":
            return {
                "task_id": make_tool_call_id(),
                "mode": mode,
                "status": "not_implemented",
            }
        raise ToolError(
            "invalid mode for task tool",
            tool_name=self.name,
            details={"mode": mode, "allowed": ("blocking", "non_blocking")},
        )

    def _run_blocking(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        runtime = self._runtime
        if runtime is None:
            raise ToolError(
                "task runtime is not configured",
                tool_name=self.name,
            )

        task_id = make_tool_call_id()
        timeout_seconds = _resolve_timeout_seconds(args)
        session_id_arg = args.get("session_id")
        task_session_id = str(session_id_arg).strip() if isinstance(session_id_arg, str) else ""
        prompt = str(args.get("prompt", "")).strip()
        continuation = bool(task_session_id)
        if not continuation:
            if not prompt:
                raise ToolError(
                    "prompt is required when session_id is not provided",
                    tool_name=self.name,
                )
            created = runtime.create_session()
            task_session_id = str(created.session_id)

        start = perf_counter()

        def _execute() -> TurnResult:
            if continuation and not prompt:
                return runtime.continue_turn(
                    task_session_id,
                    stream=False,
                    llm_session_id=ctx.session_id,
                )
            return runtime.run(
                task_session_id,
                [{"type": "text", "text": prompt}],
                stream=False,
                llm_session_id=ctx.session_id,
            )

        future = self._executor.submit(_execute)
        try:
            turn = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            duration_ms = _elapsed_ms(start)
            return {
                "task_id": task_id,
                "mode": "blocking",
                "status": "timed_out",
                "session_id": task_session_id,
                "continuation": continuation,
                "duration_ms": duration_ms,
                "error": {
                    "code": "task_timeout",
                    "message": f"task exceeded timeout_seconds={timeout_seconds}",
                },
            }
        except Exception as exc:  # noqa: BLE001
            duration_ms = _elapsed_ms(start)
            return {
                "task_id": task_id,
                "mode": "blocking",
                "status": "failed",
                "session_id": task_session_id,
                "continuation": continuation,
                "duration_ms": duration_ms,
                "error": {
                    "code": "task_execution_failed",
                    "message": str(exc),
                },
            }

        assistant_message = _pick_assistant_message(turn.messages)
        return {
            "task_id": task_id,
            "mode": "blocking",
            "status": "completed",
            "session_id": task_session_id,
            "continuation": continuation,
            "duration_ms": _elapsed_ms(start),
            "output": {
                "turn_id": turn.turn_id,
                "completed": turn.completed,
                "stop_reason": turn.stop_reason,
                "message": {
                    "message_id": assistant_message.message_id if assistant_message is not None else None,
                    "role": assistant_message.role if assistant_message is not None else "assistant",
                    "content": assistant_message.content if assistant_message is not None else "",
                },
            },
        }


def _resolve_timeout_seconds(args: Mapping[str, Any]) -> float:
    raw_timeout = args.get("timeout_seconds")
    if raw_timeout is None:
        return 30.0
    timeout_seconds = float(raw_timeout)
    if timeout_seconds <= 0:
        raise ToolError(
            "timeout_seconds must be > 0",
            tool_name="task",
        )
    return timeout_seconds


def _pick_assistant_message(messages: tuple[Message, ...]) -> Message | None:
    for message in reversed(messages):
        if message.role == "assistant":
            return message
    return None


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
