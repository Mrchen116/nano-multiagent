from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from copy import deepcopy
from threading import Lock
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
        self._idempotent_results: dict[str, dict[str, Any]] = {}
        self._task_results: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        mode = str(args["mode"]).strip()
        if mode not in {"blocking", "non_blocking"}:
            raise ToolError(
                "invalid mode for task tool",
                tool_name=self.name,
                details={"mode": mode, "allowed": ("blocking", "non_blocking")},
            )

        self._validate_task_arguments(args)
        idempotency_key = _normalize_optional_text(args.get("idempotency_key"))
        cached = self._get_cached_result(idempotency_key)
        if cached is not None:
            cached["idempotent_replay"] = True
            return cached

        if mode == "blocking":
            result = self._run_blocking(args, ctx)
        else:
            result = self._run_non_blocking(args, ctx)

        self._cache_result(idempotency_key, result)
        return result

    def _run_blocking(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        runtime = self._require_runtime()
        task_id = make_tool_call_id()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime)

        start = perf_counter()
        future = self._executor.submit(
            self._execute_turn,
            runtime=runtime,
            task_session_id=task_session_id,
            prompt=prompt,
            continuation=continuation,
            llm_session_id=ctx.session_id,
        )
        try:
            turn = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            return _timed_out_payload(
                task_id=task_id,
                mode="blocking",
                session_id=task_session_id,
                continuation=continuation,
                timeout_seconds=timeout_seconds,
                duration_ms=_elapsed_ms(start),
            )
        except Exception as exc:  # noqa: BLE001
            return _failed_payload(
                task_id=task_id,
                mode="blocking",
                session_id=task_session_id,
                continuation=continuation,
                duration_ms=_elapsed_ms(start),
                message=str(exc),
            )

        return _completed_payload(
            task_id=task_id,
            mode="blocking",
            session_id=task_session_id,
            continuation=continuation,
            duration_ms=_elapsed_ms(start),
            turn=turn,
        )

    def _run_non_blocking(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        runtime = self._require_runtime()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_id = make_tool_call_id()
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime)
        receipt = {
            "task_id": task_id,
            "mode": "non_blocking",
            "status": "queued",
            "session_id": task_session_id,
            "continuation": continuation,
            "timeout_seconds": timeout_seconds,
            "idempotent_replay": False,
        }
        with self._lock:
            self._task_results[task_id] = dict(receipt)

        self._executor.submit(
            self._run_non_blocking_worker,
            task_id=task_id,
            task_session_id=task_session_id,
            prompt=prompt,
            continuation=continuation,
            timeout_seconds=timeout_seconds,
            llm_session_id=ctx.session_id,
        )
        return receipt

    def _run_non_blocking_worker(
        self,
        *,
        task_id: str,
        task_session_id: str,
        prompt: str,
        continuation: bool,
        timeout_seconds: float,
        llm_session_id: str | None,
    ) -> None:
        runtime = self._runtime
        if runtime is None:
            return

        start = perf_counter()
        try:
            turn = self._execute_turn(
                runtime=runtime,
                task_session_id=task_session_id,
                prompt=prompt,
                continuation=continuation,
                llm_session_id=llm_session_id,
            )
        except Exception as exc:  # noqa: BLE001
            payload = _failed_payload(
                task_id=task_id,
                mode="non_blocking",
                session_id=task_session_id,
                continuation=continuation,
                duration_ms=_elapsed_ms(start),
                message=str(exc),
            )
            with self._lock:
                self._task_results[task_id] = payload
            return

        duration_ms = _elapsed_ms(start)
        if duration_ms > int(timeout_seconds * 1000):
            payload = _timed_out_payload(
                task_id=task_id,
                mode="non_blocking",
                session_id=task_session_id,
                continuation=continuation,
                timeout_seconds=timeout_seconds,
                duration_ms=duration_ms,
            )
        else:
            payload = _completed_payload(
                task_id=task_id,
                mode="non_blocking",
                session_id=task_session_id,
                continuation=continuation,
                duration_ms=duration_ms,
                turn=turn,
            )

        with self._lock:
            self._task_results[task_id] = payload

    def _execute_turn(
        self,
        *,
        runtime: TaskRuntime,
        task_session_id: str,
        prompt: str,
        continuation: bool,
        llm_session_id: str | None,
    ) -> TurnResult:
        if continuation and not prompt:
            return runtime.continue_turn(
                task_session_id,
                stream=False,
                llm_session_id=llm_session_id,
            )
        return runtime.run(
            task_session_id,
            [{"type": "text", "text": prompt}],
            stream=False,
            llm_session_id=llm_session_id,
        )

    def _resolve_target_session(
        self,
        args: Mapping[str, Any],
        *,
        runtime: TaskRuntime,
    ) -> tuple[str, str, bool]:
        task_session_id = _normalize_optional_text(args.get("session_id")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        continuation = bool(task_session_id)

        if continuation:
            return task_session_id, prompt, True

        if not prompt:
            raise ToolError(
                "prompt is required when session_id is not provided",
                tool_name=self.name,
            )
        created = runtime.create_session()
        return str(created.session_id), prompt, False

    def _validate_task_arguments(self, args: Mapping[str, Any]) -> None:
        category = _normalize_optional_text(args.get("category"))
        subagent_type = _normalize_optional_text(args.get("subagent_type"))
        if category and subagent_type:
            raise ToolError(
                "category and subagent_type are mutually exclusive",
                tool_name=self.name,
            )

    def _require_runtime(self) -> TaskRuntime:
        runtime = self._runtime
        if runtime is None:
            raise ToolError("task runtime is not configured", tool_name=self.name)
        return runtime

    def _get_cached_result(self, idempotency_key: str | None) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        with self._lock:
            cached = self._idempotent_results.get(idempotency_key)
            if cached is None:
                return None
            return deepcopy(cached)

    def _cache_result(self, idempotency_key: str | None, result: Mapping[str, Any]) -> None:
        if not idempotency_key:
            return
        stored = dict(result)
        stored["idempotent_replay"] = False
        with self._lock:
            self._idempotent_results[idempotency_key] = stored


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


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text


def _completed_payload(
    *,
    task_id: str,
    mode: str,
    session_id: str,
    continuation: bool,
    duration_ms: int,
    turn: TurnResult,
) -> dict[str, Any]:
    assistant_message = _pick_assistant_message(turn.messages)
    return {
        "task_id": task_id,
        "mode": mode,
        "status": "completed",
        "session_id": session_id,
        "continuation": continuation,
        "duration_ms": duration_ms,
        "idempotent_replay": False,
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


def _failed_payload(
    *,
    task_id: str,
    mode: str,
    session_id: str,
    continuation: bool,
    duration_ms: int,
    message: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "mode": mode,
        "status": "failed",
        "session_id": session_id,
        "continuation": continuation,
        "duration_ms": duration_ms,
        "idempotent_replay": False,
        "error": {
            "code": "task_execution_failed",
            "message": message,
        },
    }


def _timed_out_payload(
    *,
    task_id: str,
    mode: str,
    session_id: str,
    continuation: bool,
    timeout_seconds: float,
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "mode": mode,
        "status": "timed_out",
        "session_id": session_id,
        "continuation": continuation,
        "duration_ms": duration_ms,
        "idempotent_replay": False,
        "error": {
            "code": "task_timeout",
            "message": f"task exceeded timeout_seconds={timeout_seconds}",
        },
    }


def _pick_assistant_message(messages: tuple[Message, ...]) -> Message | None:
    for message in reversed(messages):
        if message.role == "assistant":
            return message
    return None


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
