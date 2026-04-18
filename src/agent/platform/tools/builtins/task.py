"""Built-in `task` tool for blocking and background sub-agent execution."""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Protocol

from agent.core.errors import ToolError
from agent.core.ids import make_tool_call_id
from agent.core.skills import resolve_available_skills
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.core.types import Message, TurnResult


class TaskRuntime(Protocol):
    """Runtime surface required by `TaskTool` to create and execute sessions."""

    async def create_session(  # noqa: ANN201
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ):
        """Create a sub-session used by a new task run."""

        ...

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        """Execute one turn in the target task session."""

        ...

    async def continue_turn(
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
    is_concurrency_safe = False
    description = (
        "Spawn agent task with category-based or direct agent selection.\n\n"
        "MUTUALLY EXCLUSIVE: Provide EITHER category OR subagent_type, not both (unless continuing a session).\n\n"
        '- load_skills: ALWAYS REQUIRED. Pass at least one skill name (e.g., ["playwright"], ["git-master", "frontend-ui-ux"]).\n'
        "- category: Use predefined category → Spawns Sisyphus-Junior with category config\n"
        "  Available categories:\n"
        "${categoryList}\n"
        '- subagent_type: Use specific agent directly (e.g., "oracle", "explore")\n'
        "- run_in_background: true=async (returns task_id), false=sync (waits for result). Default: false. "
        "Use background=true ONLY for parallel exploration with 5+ independent queries.\n"
        "- session_id: Existing Task session to continue (from previous task output). Continues agent with FULL CONTEXT PRESERVED - "
        "saves tokens, maintains continuity.\n"
        "- command: The command that triggered this task (optional, for slash command tracking).\n\n"
        "**WHEN TO USE session_id:**\n"
        '- Task failed/incomplete → session_id with "fix: [specific issue]"\n'
        "- Need follow-up on previous result → session_id with additional question\n"
        "- Multi-turn conversation with same agent → always session_id instead of new task\n\n"
        "Prompts MUST be in English."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "load_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Skill names to inject. REQUIRED - pass [] if no skills needed, but IT IS HIGHLY RECOMMENDED to pass "
                    'proper skills like ["playwright"], ["git-master"] for best results.'
                ),
            },
            "description": {"type": "string", "description": "Short task description (3-5 words)"},
            "prompt": {"type": "string", "description": "Full detailed prompt for the agent"},
            "run_in_background": {
                "type": "boolean",
                "description": "true=async (returns task_id), false=sync (waits). Default: false",
            },
            "session_id": {
                "type": "string",
                "description": "Existing Task session to continue",
            },
            "category": {
                "type": "string",
                "description": "Category (e.g., ${categoryExamples}). Mutually exclusive with subagent_type.",
            },
            "subagent_type": {
                "type": "string",
                "description": "Agent name (e.g., 'oracle', 'explore'). Mutually exclusive with category.",
            },
            "command": {
                "type": "string",
                "description": "The command that triggered this task",
            },
            "idempotency_key": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["load_skills", "description", "prompt", "run_in_background"],
        "additionalProperties": False,
    }

    def __init__(self, *, runtime: TaskRuntime | None = None) -> None:
        self._runtime = runtime
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nano-task")
        self._idempotent_results: dict[str, Any] = {}
        self._task_results: dict[str, Any] = {}
        self._lock = Lock()

    def bind_runtime(self, runtime: TaskRuntime | None) -> None:
        """Bind runtime after bootstrap when the tool registry was prebuilt."""

        self._runtime = runtime

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Any:
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
    ) -> dict[str, Any]:
        runtime = self._require_runtime()
        task_id = make_tool_call_id()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime, ctx=ctx)
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
            return {
                "status": "failed",
                "title": "Task timed out",
                "error": f"task exceeded timeout_seconds={timeout_seconds}",
                "sessionId": task_session_id,
                "agent": agent,
                "continuation": continuation,
                "taskId": task_id,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "failed",
                "title": "Task failed",
                "error": str(exc),
                "sessionId": task_session_id,
                "agent": agent,
                "continuation": continuation,
                "taskId": task_id,
            }

        return {
            "status": "completed",
            "content": _pick_assistant_text(turn.messages),
            "sessionId": task_session_id,
            "durationMs": _elapsed_ms(start),
            "agent": agent,
            "continuation": continuation,
            "taskId": task_id,
        }

    def _run_non_blocking(
        self,
        args: Mapping[str, Any],
        ctx: ToolContext,
        *,
        run_in_background: bool,
    ) -> dict[str, Any]:
        runtime = self._require_runtime()
        timeout_seconds = _resolve_timeout_seconds(args)
        task_id = make_tool_call_id()
        task_session_id, prompt, continuation = self._resolve_target_session(args, runtime=runtime, ctx=ctx)
        description = _normalize_optional_text(args.get("description")) or ""
        agent = _resolve_agent_name(args)

        receipt = {
            "status": "async_launched",
            "taskId": task_id,
            "sessionId": task_session_id,
            "description": description,
            "agent": agent,
            "continuation": continuation,
        }
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
            payload = {
                "status": "failed",
                "title": "Task failed",
                "error": str(exc),
                "sessionId": task_session_id,
                "agent": "background",
                "continuation": continuation,
                "taskId": task_id,
            }
            with self._lock:
                self._task_results[task_id] = payload
            return

        duration_ms = _elapsed_ms(start)
        if duration_ms > int(timeout_seconds * 1000):
            payload = {
                "status": "failed",
                "title": "Task timed out",
                "error": f"task exceeded timeout_seconds={timeout_seconds}",
                "sessionId": task_session_id,
                "agent": "background",
                "continuation": continuation,
                "taskId": task_id,
            }
        else:
            payload = {
                "status": "completed",
                "content": _pick_assistant_text(turn.messages),
                "sessionId": task_session_id,
                "durationMs": duration_ms,
                "agent": "background",
                "continuation": continuation,
                "taskId": task_id,
            }

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
        import asyncio

        if continuation and not prompt:
            return asyncio.run(
                runtime.continue_turn(
                    task_session_id,
                    stream=False,
                    llm_session_id=llm_session_id,
                )
            )
        return asyncio.run(
            runtime.run(
                task_session_id,
                [{"type": "text", "text": prompt}],
                stream=False,
                llm_session_id=llm_session_id,
            )
        )

    def _resolve_target_session(
        self,
        args: Mapping[str, Any],
        *,
        runtime: TaskRuntime,
        ctx: ToolContext,
    ) -> tuple[str, str, bool]:
        task_session_id = _normalize_optional_text(args.get("session_id")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        continuation = bool(task_session_id)

        import asyncio

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
            created = asyncio.run(runtime.create_session(workspace_root=ctx.cwd))
            return str(created.session_id), prompt, False

        if not prompt:
            raise ToolError(
                "prompt is required when session_id is not provided",
                tool_name=self.name,
            )
        created = asyncio.run(runtime.create_session(workspace_root=ctx.cwd))
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
            config_resolver=getattr(self._runtime, "config_resolver", None),
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

    def _get_cached_result(self, idempotency_key: str | None) -> Any | None:
        if not idempotency_key:
            return None
        with self._lock:
            return self._idempotent_results.get(idempotency_key)

    def _cache_result(self, idempotency_key: str | None, result: Any) -> None:
        if not idempotency_key:
            return
        with self._lock:
            self._idempotent_results[idempotency_key] = result

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            if isinstance(output, str):
                return output
            return json_serialize(output)

        status = output.get("status")
        if status == "completed":
            return self._format_completed(output)
        if status == "async_launched":
            return self._format_async_launched(output)
        if status == "failed":
            return self._format_failed(output)
        return json_serialize(output)

    def _format_completed(self, output: Mapping[str, Any]) -> str:
        content = output.get("content", "")
        session_id = output.get("sessionId", "unknown")
        duration_ms = output.get("durationMs", 0)
        agent = output.get("agent", "unknown")
        continuation = output.get("continuation", False)
        task_id = output.get("taskId", "unknown")

        if not content or not content.strip():
            content = "(Subagent completed but returned no output.)"

        if continuation:
            return (
                f"Task continued and completed in {duration_ms}ms.\n\n"
                f"---\n\n"
                f"{content}\n\n"
                f"session_id: {session_id} (use task with session_id='{session_id}' to continue)\n"
                f"Agent: {agent}\n"
                f"task_id: {task_id}"
            )
        return (
            f"Task completed in {duration_ms}ms.\n\n"
            f"Agent: {agent}\n\n"
            f"---\n\n"
            f"{content}\n\n"
            f"session_id: {session_id} (use task with session_id='{session_id}' to continue)\n"
            f"task_id: {task_id}"
        )

    def _format_async_launched(self, output: Mapping[str, Any]) -> str:
        task_id = output.get("taskId", "unknown")
        session_id = output.get("sessionId", "unknown")
        description = output.get("description", "")
        agent = output.get("agent", "unknown")
        continuation = output.get("continuation", False)

        status_line = "Background task continued." if continuation else "Background task launched."
        guidance = (
            f"Agent continues with full previous context preserved.\n"
            f"Use `task` with session_id='{session_id}' to continue or check progress."
            if continuation
            else f"System notifies on completion. Use `task` with session_id='{session_id}' to check."
        )
        return (
            f"{status_line}\n\n"
            f"Task ID: {task_id}\n"
            f"Description: {description}\n"
            f"Agent: {agent}\n"
            "Status: queued\n\n"
            f"{guidance}"
        )

    def _format_failed(self, output: Mapping[str, Any]) -> str:
        title = output.get("title", "Task failed")
        error = output.get("error", "Unknown error")
        session_id = output.get("sessionId", "unknown")
        return f"{title}\n\nError: {error}\n\nsession_id: {session_id}"


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


def _pick_assistant_text(messages: tuple[Message, ...]) -> str:
    for message in reversed(messages):
        if message.role == "assistant":
            return message.content.strip()
    return ""


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
