"""Built-in `Agent` tool for background and foreground sub-agent execution."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

from agent.core.background_tasks.ids import generate_agent_id
from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.skills import resolve_available_skills
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.core.types import TurnResult

# Foreground budget before auto-backgrounding (seconds)
_DEFAULT_FOREGROUND_BUDGET = 120.0


class AgentTool:
    """Launch autonomous subagents with background/foreground/continuation support."""

    name = "agent"
    is_concurrency_safe = False
    description = (
        "Launch a new agent to handle complex, multi-step tasks autonomously.\n\n"
        "Use this tool for tasks that are complex, multi-step, require independent context, "
        "or can be run in parallel with other work. Do not use it for reading a specific file path, "
        "searching a single symbol, or simple lookups across 2-3 files — use read/bash/search tools instead.\n\n"
        "- description: Short task description (3-5 words).\n"
        "- prompt: Full detailed prompt for the agent. Must include goal, background, constraints, "
        "known information, and expected output.\n"
        "- subagent_type: Specific agent type (e.g., 'oracle', 'explore').\n"
        "- category: Predefined category that selects a specialized agent. Mutually exclusive with subagent_type for new tasks.\n"
        "- load_skills: Skill names to inject. Pass [] when no extra skills are needed.\n"
        "- run_in_background: true=run in background (returns agent_id immediately); false=wait for result. "
        "Default: false. Background tasks complete automatically; do not sleep, poll, or proactively check progress.\n"
        "- agent_id: Send a follow-up to an existing agent by ID. If running, message is queued; if stopped, resumes from transcript.\n"
        "- timeout_seconds: Maximum foreground wait before auto-backgrounding. Overrides the default 120s budget.\n\n"
        "Prompts MUST be in English."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "A short (3-5 word) description of the task.",
            },
            "prompt": {
                "type": "string",
                "description": (
                    "The task or follow-up instruction for the agent to perform. "
                    "For a fresh agent, include enough context for it to act independently. "
                    "When agent_id is provided, this is the follow-up message for that existing agent."
                ),
            },
            "subagent_type": {
                "type": "string",
                "description": "The type of specialized agent to use for this task.",
            },
            "category": {
                "type": "string",
                "description": "Predefined category that selects a specialized agent. Mutually exclusive with subagent_type for new tasks.",
            },
            "load_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skill names to load for the spawned agent. Pass [] when no extra skills are needed.",
            },
            "run_in_background": {
                "type": "boolean",
                "description": (
                    "Set true to run this agent in the background. The call returns immediately with agent_id and output_file. "
                    "You will be notified automatically when it completes; do not sleep, poll, or proactively check progress."
                ),
            },
            "agent_id": {
                "type": "string",
                "description": (
                    "Send a follow-up instruction to an existing agent by ID with full context preserved. "
                    "If the agent is running, the message is queued and delivered at the agent's next tool-round boundary. "
                    "If the agent is stopped, it resumes from its transcript. "
                    "Do not use this to check background progress or output; read output_file for output."
                ),
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Maximum foreground wait before this call stops waiting. Overrides the default 120 second auto-background budget.",
            },
        },
        "required": ["load_skills", "description", "prompt"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        runtime: Any | None = None,
        wiring: Any | None = None,
    ) -> None:
        self._runtime = runtime
        self._wiring = wiring
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nano-agent")

    def bind_runtime(self, runtime: Any | None) -> None:
        """Bind runtime after bootstrap."""
        self._runtime = runtime

    def bind_wiring(self, wiring: Any | None) -> None:
        """Bind background task wiring after bootstrap."""
        self._wiring = wiring

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Any:
        """Execute one agent request: background, foreground, or continuation."""

        agent_id = _normalize_optional_text(args.get("agent_id"))
        if agent_id is not None:
            return self._run_continuation(agent_id=agent_id, args=args, ctx=ctx)

        run_in_background = _normalize_run_in_background(args.get("run_in_background"))
        self._validate_new_agent_args(args, ctx=ctx)

        if run_in_background:
            return self._run_background(args=args, ctx=ctx)
        return self._run_foreground(args=args, ctx=ctx)

    # ------------------------------------------------------------------
    # Background launch
    # ------------------------------------------------------------------

    def _run_background(self, args: Mapping[str, Any], ctx: ToolContext) -> dict[str, Any]:
        runtime = self._require_runtime()
        wiring = self._require_wiring()
        registry = wiring.registry

        agent_id = generate_agent_id()
        description = _normalize_optional_text(args.get("description")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        agent_type = _resolve_agent_name(args)

        # Create subagent session with metadata
        agent_session_id = self._create_subagent_session(
            runtime=runtime,
            ctx=ctx,
            agent_id=agent_id,
            agent_type=agent_type,
            description=description,
            args=args,
        )

        # Subagent sessions are created with workspace_root=ctx.cwd; their JSONL
        # lives under {ctx.cwd}/.nano/sessions/{parent}/subagents/. Thread ctx.cwd
        # so the stateless store can locate it.
        output_file = self._resolve_output_file(
            runtime, agent_session_id, ctx.session_id, ctx.cwd
        )

        # Register background task
        record = registry.register_subagent(
            task_id=agent_id,
            parent_session_id=ctx.session_id or "",
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            description=description,
            prompt=prompt,
            agent_type=agent_type,
            output_file=str(output_file),
        )
        registry.mark_running(agent_id)

        # Start worker
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=ctx.session_id or "",
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            workspace_root=ctx.cwd,
        )
        registry.set_stop_handle(agent_id, stopper)

        return {
            "status": "async_launched",
            "agent_id": agent_id,
            "description": description,
            "output_file": str(output_file),
        }

    # ------------------------------------------------------------------
    # Foreground with auto-background
    # ------------------------------------------------------------------

    def _run_foreground(self, args: Mapping[str, Any], ctx: ToolContext) -> dict[str, Any]:
        runtime = self._require_runtime()
        wiring = self._require_wiring()

        agent_id = generate_agent_id()
        description = _normalize_optional_text(args.get("description")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        agent_type = _resolve_agent_name(args)
        timeout_seconds = _resolve_timeout_seconds(args)

        agent_session_id = self._create_subagent_session(
            runtime=runtime,
            ctx=ctx,
            agent_id=agent_id,
            agent_type=agent_type,
            description=description,
            args=args,
        )

        # Subagent sessions are created with workspace_root=ctx.cwd; thread it so
        # the stateless store can locate the subagent JSONL.
        output_file = self._resolve_output_file(
            runtime, agent_session_id, ctx.session_id, ctx.cwd
        )

        # Submit worker to executor
        future = self._executor.submit(
            _run_subagent_turn_sync,
            runtime=runtime,
            session_id=agent_session_id,
            prompt=prompt,
            parent_session_id=ctx.session_id or "",
            workspace_root=ctx.cwd,
        )

        try:
            turn = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            # Auto-background: register task and let worker continue
            registry = wiring.registry
            registry.register_subagent(
                task_id=agent_id,
                parent_session_id=ctx.session_id or "",
                agent_id=agent_id,
                agent_session_id=agent_session_id,
                description=description,
                prompt=prompt,
                agent_type=agent_type,
                output_file=str(output_file),
            )
            registry.mark_running(agent_id)

            # Watcher thread updates registry when future completes
            _start_registry_watcher(registry, agent_id, future)

            return {
                "status": "async_launched",
                "agent_id": agent_id,
                "description": description,
                "output_file": str(output_file),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "failed",
                "error": str(exc),
                "agent_id": agent_id,
            }

        # Foreground completed within budget
        result_text = _extract_assistant_text(turn)
        return {
            "status": "completed",
            "content": result_text or "(Agent completed but returned no output.)",
            "agent_id": agent_id,
        }

    # ------------------------------------------------------------------
    # Continuation / message to existing agent
    # ------------------------------------------------------------------

    def _run_continuation(
        self,
        *,
        agent_id: str,
        args: Mapping[str, Any],
        ctx: ToolContext,
    ) -> dict[str, Any]:
        wiring = self._require_wiring()
        registry = wiring.registry
        prompt = _normalize_optional_text(args.get("prompt")) or ""

        # Subagent JSONL lives under the parent session's workspace_root; the
        # parent turn (ctx.session_id) is what invoked this tool, so the runtime
        # holds the parent's workspace_root in memory.
        runtime = self._require_runtime()
        parent_workspace_root = runtime.session_workspace_root(ctx.session_id or "")

        # 1. Check in-memory registry
        record = registry.get(agent_id)
        if record is not None and record.task_type.value == "subagent":
            if record.status == BackgroundTaskStatus.RUNNING:
                registry.enqueue_agent_message(agent_id, prompt)
                return {
                    "status": "message_queued",
                    "agent_id": agent_id,
                    "description": record.description,
                    "output_file": record.output_file,
                }
            # Terminal but in memory: resume with new turn
            return self._resume_subagent(
                agent_id=agent_id,
                agent_session_id=record.agent_session_id,
                parent_session_id=record.parent_session_id,
                prompt=prompt,
                description=record.description,
                output_file=record.output_file,
                agent_type=record.agent_type,
                workspace_root=parent_workspace_root,
            )

        # 2. Try JSONL rehydrate. The stateless store needs the parent's
        # workspace_root (resolved above) to locate both the index scan and the
        # subagent file.
        store = runtime._session_manager.store
        parent_session_id = ctx.session_id or ""
        found_session_id = store.find_session_by_metadata(
            parent_session_id=parent_session_id,
            match={"agent_id": agent_id},
            workspace_root=parent_workspace_root,
        )
        if found_session_id is None:
            raise ToolError(
                f'No subagent with agent_id="{agent_id}" found in session history.',
                tool_name=self.name,
                details={"code": "agent_not_found"},
            )

        # Load session config to get metadata
        try:
            load_result = runtime._session_manager.load(
                found_session_id,
                workspace_root=parent_workspace_root,
                parent_session_id=parent_session_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise ToolError(
                f"Failed to load subagent session: {exc}",
                tool_name=self.name,
                details={"code": "agent_not_found"},
            ) from exc

        config = load_result.config
        metadata = dict(config.metadata) if config.metadata else {}
        description = metadata.get("description", "")
        agent_type = metadata.get("agent_type")
        output_file = str(
            store.resolve_path(
                found_session_id,
                workspace_root=parent_workspace_root,
                parent_session_id=parent_session_id,
            )
        )

        return self._resume_subagent(
            agent_id=agent_id,
            agent_session_id=found_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            description=description,
            output_file=output_file,
            agent_type=agent_type,
            workspace_root=parent_workspace_root,
        )

    def _resume_subagent(
        self,
        *,
        agent_id: str,
        agent_session_id: str | None,
        parent_session_id: str,
        prompt: str,
        description: str,
        output_file: str,
        agent_type: str | None,
        workspace_root: Path | None = None,
    ) -> dict[str, Any]:
        if agent_session_id is None:
            raise ToolError(
                "agent_session_id is required for resumption",
                tool_name=self.name,
            )

        wiring = self._require_wiring()
        registry = wiring.registry

        # Register/resume task in registry
        registry.register_subagent(
            task_id=agent_id,
            parent_session_id=parent_session_id,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            description=description,
            prompt=prompt,
            agent_type=agent_type,
            output_file=output_file,
        )
        registry.mark_running(agent_id)

        # Start worker for the resumed turn. The subagent JSONL lives under the
        # parent session's workspace_root, threaded here so the stateless store
        # can locate it.
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            workspace_root=workspace_root,
        )
        registry.set_stop_handle(agent_id, stopper)

        return {
            "status": "async_launched",
            "agent_id": agent_id,
            "description": description,
            "output_file": output_file,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_subagent_session(
        self,
        *,
        runtime: Any,
        ctx: ToolContext,
        agent_id: str,
        agent_type: str,
        description: str,
        args: Mapping[str, Any],
    ) -> str:
        import asyncio

        load_skills = _normalize_skill_names(args.get("load_skills"), tool_name=self.name)
        effective_workspace = ctx.cwd
        metadata: dict[str, Any] = {
            "kind": "subagent",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "description": description,
            "workspace_root": str(effective_workspace.resolve()) if effective_workspace else None,
        }
        session = asyncio.run(
            runtime.create_session(
                workspace_root=effective_workspace,
                skills=load_skills if load_skills else None,
                metadata=metadata,
                parent_session_id=ctx.session_id,
            )
        )
        return str(session.session_id)

    def _resolve_output_file(
        self,
        runtime: Any,
        agent_session_id: str,
        parent_session_id: str | None,
        workspace_root: Path,
    ) -> Path:
        # Subagent JSONL lives under the parent session's workspace_root, which
        # is the spawning turn's ctx.cwd (also used as the subagent's own
        # workspace_root at create_session time).
        store = runtime._session_manager.store
        return store.resolve_path(
            agent_session_id,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id or "",
        )

    def _require_runtime(self) -> Any:
        runtime = self._runtime
        if runtime is None:
            raise ToolError("agent runtime is not configured", tool_name=self.name)
        return runtime

    def _require_wiring(self) -> Any:
        wiring = self._wiring
        if wiring is None:
            raise ToolError("background task wiring is not configured", tool_name=self.name)
        return wiring

    def _validate_new_agent_args(self, args: Mapping[str, Any], *, ctx: ToolContext) -> None:
        if _normalize_optional_text(args.get("description")) is None:
            raise ToolError("description must be a non-empty string", tool_name=self.name)
        if _normalize_optional_text(args.get("prompt")) is None:
            raise ToolError("prompt must be a non-empty string", tool_name=self.name)

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
        if category and subagent_type:
            raise ToolError(
                "category and subagent_type are mutually exclusive",
                tool_name=self.name,
            )
        if not category and not subagent_type:
            raise ToolError(
                "either category or subagent_type is required for new agent",
                tool_name=self.name,
            )

    # ------------------------------------------------------------------
    # Result formatting
    # ------------------------------------------------------------------

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
        if status == "message_queued":
            return self._format_message_queued(output)
        if status == "failed":
            return self._format_failed(output)
        return json_serialize(output)

    def _format_completed(self, output: Mapping[str, Any]) -> str:
        content = output.get("content", "")
        agent_id = output.get("agent_id", "unknown")
        return (
            f"Task completed.\n\n"
            f"---\n\n"
            f"{content}\n\n"
            f"agent_id: {agent_id}"
        )

    def _format_async_launched(self, output: Mapping[str, Any]) -> str:
        agent_id = output.get("agent_id", "unknown")
        description = output.get("description", "")
        output_file = output.get("output_file", "")
        return (
            f"Background agent launched.\n\n"
            f"agent_id: {agent_id}\n"
            f"description: {description}\n"
            f"status: running\n"
            f"output_file: {output_file}\n\n"
            f"The agent is working in the background. You will be notified automatically when it completes.\n"
            f"Do not duplicate this agent's work. Work on non-overlapping tasks, or briefly tell the user what you launched and continue.\n"
            f"Use Read on output_file to inspect progress or final output.\n"
            f"Use Agent with agent_id=\"{agent_id}\" only when you want to continue the agent conversation.\n"
            f"Use task_stop with task_id=\"{agent_id}\" to stop it."
        )

    def _format_message_queued(self, output: Mapping[str, Any]) -> str:
        agent_id = output.get("agent_id", "unknown")
        description = output.get("description", "")
        output_file = output.get("output_file", "")
        return (
            f"Message queued for agent.\n\n"
            f"agent_id: {agent_id}\n"
            f"description: {description}\n"
            f"status: running\n"
            f"output_file: {output_file}\n\n"
            f"The message will be delivered at the agent's next tool-round boundary.\n"
            f"Do not poll. You will be notified when the agent completes."
        )

    def _format_failed(self, output: Mapping[str, Any]) -> str:
        error = output.get("error", "Unknown error")
        agent_id = output.get("agent_id", "unknown")
        return f"Agent failed.\n\nError: {error}\n\nagent_id: {agent_id}"


# ------------------------------------------------------------------
# Worker helpers
# ------------------------------------------------------------------

def _run_subagent_turn_sync(
    runtime: Any,
    session_id: str,
    prompt: str,
    parent_session_id: str,
    workspace_root: Path | None = None,
) -> TurnResult:
    """Run one subagent turn synchronously (called in executor thread).

    ``workspace_root`` is the parent turn's ctx.cwd (also the subagent's own
    workspace_root), threaded so the stateless store can locate the JSONL.
    """
    return asyncio.run(
        runtime.run(
            session_id,
            [{"type": "text", "text": prompt}],
            stream=False,
            parent_session_id=parent_session_id,
            workspace_root=workspace_root,
        )
    )


def _start_registry_watcher(
    registry: BackgroundTaskRegistry,
    task_id: str,
    future: Any,
) -> None:
    """Start a daemon thread that waits for ``future`` and updates registry."""

    def _watch() -> None:
        try:
            turn = future.result()
            result_text = _extract_assistant_text(turn)
            registry.complete(
                task_id,
                result_text=result_text,
            )
        except Exception as exc:  # noqa: BLE001
            registry.fail(task_id, error=str(exc))

    threading.Thread(target=_watch, daemon=True).start()


def _make_on_complete(registry: BackgroundTaskRegistry, agent_id: str) -> Any:
    def _on_complete(
        *,
        task_id: str,
        result_text: str | None,
        usage: Mapping[str, Any] | None,
        duration_ms: int,
        tool_use_count: int,
    ) -> None:
        # runner passes agent_session_id as task_id; we use captured agent_id
        registry.complete(
            agent_id,
            result_text=result_text,
            usage=usage,
            duration_ms=duration_ms,
            tool_use_count=tool_use_count,
        )

    return _on_complete


def _make_on_fail(registry: BackgroundTaskRegistry, agent_id: str) -> Any:
    def _on_fail(*, task_id: str, error: str) -> None:
        registry.fail(agent_id, error=error)

    return _on_fail


# ------------------------------------------------------------------
# Text / argument helpers
# ------------------------------------------------------------------

def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text


def _normalize_run_in_background(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ToolError("run_in_background must be a boolean", tool_name="agent")
    return value


def _resolve_timeout_seconds(args: Mapping[str, Any]) -> float:
    raw = args.get("timeout_seconds")
    if raw is None:
        return _DEFAULT_FOREGROUND_BUDGET
    timeout = float(raw)
    if timeout <= 0:
        raise ToolError("timeout_seconds must be > 0", tool_name="agent")
    return timeout


def _normalize_skill_names(value: Any, *, tool_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ToolError("load_skills must be an array of strings", tool_name=tool_name)
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ToolError("load_skills must be an array of strings", tool_name=tool_name)
        name = item.strip()
        if not name:
            raise ToolError("load_skills contains an empty skill name", tool_name=tool_name)
        normalized.append(name)
    return tuple(normalized)


def _resolve_agent_name(args: Mapping[str, Any]) -> str:
    subagent_type = _normalize_optional_text(args.get("subagent_type"))
    if subagent_type is not None:
        return subagent_type
    category = _normalize_optional_text(args.get("category"))
    if category is not None:
        return category
    return "unknown"


def _extract_assistant_text(turn: TurnResult | Any) -> str | None:
    messages = getattr(turn, "messages", ())
    for message in reversed(messages):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None
