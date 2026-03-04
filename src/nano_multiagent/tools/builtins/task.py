"""Built-in `task` tool for blocking and background sub-agent execution."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Lock
from time import perf_counter
from typing import Any, Mapping, Protocol

from nano_multiagent.core.errors import ToolError
from nano_multiagent.core.ids import make_tool_call_id
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.skills.workspace import resolve_available_skills

from ..base import ToolContext


class TaskRuntime(Protocol):
    """Runtime surface required by `TaskTool` to create and execute sessions."""

    def create_session(self):  # noqa: ANN201
        """Create a sub-session used by a new task run."""

        ...

    def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        """Execute one turn in the target task session."""

        ...

    def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        """Continue a session without appending a new user prompt."""

        ...


class TaskTool:
    """Schedule or execute in-process sub-agent tasks with idempotent replay."""

    name = "task"
    description = "Run or schedule a local in-process subagent task."
    input_schema = {
        "type": "object",
        "properties": {
            "load_skills": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "prompt": {"type": "string"},
            "run_in_background": {"type": "boolean"},
            "session_id": {
                "type": "string",
                "description": "Existing task session id returned by a previous task call; omit for new tasks.",
            },
            "category": {"type": "string"},
            "subagent_type": {"type": "string"},
            "command": {"type": "string"},
            "idempotency_key": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["load_skills", "description", "prompt", "run_in_background"],
        "additionalProperties": False,
    }

    def __init__(self, *, runtime: TaskRuntime | None = None) -> None:
        self._runtime = runtime
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nano-task")
        self._idempotent_results: dict[str, str] = {}
        self._task_results: dict[str, str] = {}
        self._lock = Lock()

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> str:
        """Execute one task request in blocking or non-blocking mode."""

        run_in_background = _normalize_run_in_background(args.get("run_in_background"))
        mode = "non_blocking" if run_in_background else "blocking"

        self._validate_task_arguments(args, ctx=ctx)
        idempotency_key = _normalize_optional_text(args.get("idempotency_key"))
        cached = self._get_cached_result(idempotency_key)
        if cached is not None:
            return cached

        if mode == "blocking":
            result = self._run_blocking(args, ctx, run_in_background=run_in_background)
        else:
            result = self._run_non_blocking(args, ctx, run_in_background=run_in_background)

        self._cache_result(idempotency_key, result)
        return result

    def _run_blocking(
        self,
        args: Mapping[str, Any],
        ctx: ToolContext,
        *,
        run_in_background: bool,
    ) -> str:
        runtime = self._require_runtime()
        task_id = make_tool_call_id()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime)
        description = _normalize_optional_text(args.get("description")) or ""
        agent = _resolve_agent_name(args)

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
            return _error_message(
                title="Task timed out",
                message=f"task exceeded timeout_seconds={timeout_seconds}",
                task_id=task_id,
                session_id=task_session_id,
                continuation=continuation,
                subagent=_resolve_subagent(args),
            )
        except Exception as exc:  # noqa: BLE001
            return _error_message(
                title="Task failed",
                message=str(exc),
                task_id=task_id,
                session_id=task_session_id,
                continuation=continuation,
                subagent=_resolve_subagent(args),
            )

        return _sync_success_message(
            task_id=task_id,
            description=description,
            agent=agent,
            session_id=task_session_id,
            continuation=continuation,
            duration_ms=_elapsed_ms(start),
            turn=turn,
            subagent=_resolve_subagent(args),
        )

    def _run_non_blocking(
        self,
        args: Mapping[str, Any],
        ctx: ToolContext,
        *,
        run_in_background: bool,
    ) -> str:
        runtime = self._require_runtime()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_id = make_tool_call_id()
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime)
        description = _normalize_optional_text(args.get("description")) or ""
        agent = _resolve_agent_name(args)
        receipt = _background_receipt_message(
            task_id=task_id,
            description=description,
            session_id=task_session_id,
            continuation=continuation,
            agent=agent,
            subagent=_resolve_subagent(args),
        )
        with self._lock:
            self._task_results[task_id] = receipt

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
            payload = _error_message(
                title="Task failed",
                message=str(exc),
                task_id=task_id,
                session_id=task_session_id,
                continuation=continuation,
                subagent=None,
            )
            with self._lock:
                self._task_results[task_id] = payload
            return

        duration_ms = _elapsed_ms(start)
        if duration_ms > int(timeout_seconds * 1000):
            payload = _error_message(
                title="Task timed out",
                message=f"task exceeded timeout_seconds={timeout_seconds}",
                task_id=task_id,
                session_id=task_session_id,
                continuation=continuation,
                subagent=None,
            )
        else:
            payload = _sync_success_message(
                task_id=task_id,
                description="background worker result",
                agent="background",
                session_id=task_session_id,
                continuation=continuation,
                duration_ms=duration_ms,
                turn=turn,
                subagent=None,
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
            exists = _runtime_session_exists(runtime, task_session_id)
            if exists is not False:
                return task_session_id, prompt, True
            if not prompt:
                raise ToolError(
                    "prompt is required when session_id does not exist",
                    tool_name=self.name,
                    details={"session_id": task_session_id},
                )
            created = runtime.create_session()
            return str(created.session_id), prompt, False

        if not prompt:
            raise ToolError(
                "prompt is required when session_id is not provided",
                tool_name=self.name,
            )
        created = runtime.create_session()
        return str(created.session_id), prompt, False

    def _validate_task_arguments(self, args: Mapping[str, Any], *, ctx: ToolContext) -> None:
        if _normalize_optional_text(args.get("description")) is None:
            raise ToolError(
                "description must be a non-empty string",
                tool_name=self.name,
            )
        if _normalize_optional_text(args.get("prompt")) is None:
            raise ToolError(
                "prompt must be a non-empty string",
                tool_name=self.name,
            )

        load_skills = _normalize_skill_names(args.get("load_skills"), tool_name=self.name)
        available = resolve_available_skills(
            workspace_root=ctx.repo_root,
            include_names=load_skills,
        )
        available_names = {skill.name for skill in available}
        missing_skills = [name for name in load_skills if name not in available_names]
        if missing_skills:
            raise ToolError(
                "unknown skills requested",
                tool_name=self.name,
                details={"missing_skills": missing_skills},
            )

        category = _normalize_optional_text(args.get("category"))
        subagent_type = _normalize_optional_text(args.get("subagent_type"))
        continuation = _normalize_optional_text(args.get("session_id")) is not None
        if continuation:
            return
        if category and subagent_type:
            raise ToolError(
                "category and subagent_type are mutually exclusive",
                tool_name=self.name,
            )
        if not category and not subagent_type:
            raise ToolError(
                "either category or subagent_type is required for new task",
                tool_name=self.name,
            )

    def _require_runtime(self) -> TaskRuntime:
        runtime = self._runtime
        if runtime is None:
            raise ToolError("task runtime is not configured", tool_name=self.name)
        return runtime

    def _get_cached_result(self, idempotency_key: str | None) -> str | None:
        if not idempotency_key:
            return None
        with self._lock:
            cached = self._idempotent_results.get(idempotency_key)
            if cached is None:
                return None
            return str(cached)

    def _cache_result(self, idempotency_key: str | None, result: str) -> None:
        if not idempotency_key:
            return
        with self._lock:
            self._idempotent_results[idempotency_key] = str(result)


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


def _normalize_run_in_background(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ToolError(
            "run_in_background must be a boolean",
            tool_name="task",
        )
    return value


def _runtime_session_exists(runtime: TaskRuntime, session_id: str) -> bool | None:
    getter = getattr(runtime, "get_session", None)
    if not callable(getter):
        return None
    try:
        return getter(session_id) is not None
    except Exception:  # noqa: BLE001
        return None


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text


def _normalize_skill_names(value: Any, *, tool_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ToolError(
            "load_skills must be an array of strings",
            tool_name=tool_name,
        )

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ToolError(
                "load_skills must be an array of strings",
                tool_name=tool_name,
            )
        skill_name = item.strip()
        if not skill_name:
            raise ToolError(
                "load_skills contains an empty skill name",
                tool_name=tool_name,
            )
        normalized.append(skill_name)
    return tuple(normalized)


def _resolve_agent_name(args: Mapping[str, Any]) -> str:
    subagent_type = _normalize_optional_text(args.get("subagent_type"))
    if subagent_type is not None:
        return subagent_type
    category = _normalize_optional_text(args.get("category"))
    if category is not None:
        return f"{category} (category: {category})"
    return "unknown"


def _resolve_subagent(args: Mapping[str, Any]) -> str | None:
    subagent_type = _normalize_optional_text(args.get("subagent_type"))
    if subagent_type is not None:
        return subagent_type
    return _normalize_optional_text(args.get("category"))


def _background_receipt_message(
    *,
    task_id: str,
    description: str,
    agent: str,
    session_id: str,
    continuation: bool,
    subagent: str | None,
) -> str:
    status_line = "Background task continued." if continuation else "Background task launched."
    guidance = (
        'Agent continues with full previous context preserved.\nUse `background_output` with task_id="{task_id}" to check progress.'
        if continuation
        else 'System notifies on completion. Use `background_output` with task_id="{task_id}" to check.'
    )
    return (
        f"{status_line}\n\n"
        f"Task ID: {task_id}\n"
        f"Description: {description}\n"
        f"Agent: {agent}\n"
        "Status: queued\n\n"
        f"{guidance.format(task_id=task_id)}\n\n"
        f"{_task_metadata_block(session_id=session_id, subagent=subagent if continuation else None)}"
    )


def _sync_success_message(
    *,
    task_id: str,
    description: str,
    agent: str,
    session_id: str,
    continuation: bool,
    duration_ms: int,
    turn: TurnResult,
    subagent: str | None,
) -> str:
    del task_id, description
    output_text = _pick_assistant_text(turn.messages)
    if continuation:
        return (
            f"Task continued and completed in {duration_ms}ms.\n\n"
            "---\n\n"
            f"{output_text}\n\n"
            f"{_task_metadata_block(session_id=session_id, subagent=subagent)}"
        )
    return (
        f"Task completed in {duration_ms}ms.\n\n"
        f"Agent: {agent}\n\n"
        "---\n\n"
        f"{output_text}\n\n"
        f"{_task_metadata_block(session_id=session_id, subagent=None)}"
    )


def _error_message(
    *,
    title: str,
    message: str,
    task_id: str,
    session_id: str,
    continuation: bool,
    subagent: str | None,
) -> str:
    del task_id, continuation
    return (
        f"{title}\n\n"
        f"**Error**: {message}\n\n"
        f"{_task_metadata_block(session_id=session_id, subagent=subagent)}"
    )


def _pick_assistant_text(messages: tuple[Message, ...]) -> str:
    for message in reversed(messages):
        if message.role == "assistant":
            content = message.content.strip()
            return content or "(No text output)"
    return "(No text output)"


def _task_metadata_block(*, session_id: str, subagent: str | None) -> str:
    lines = ["<task_metadata>", f"session_id: {session_id}"]
    if subagent is not None:
        lines.append(f"subagent: {subagent}")
    lines.append("</task_metadata>")
    return "\n".join(lines)


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
