"""Built-in `Agent` tool for background and foreground sub-agent execution."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

from agent.core.agent.run_control import RunController
from agent.core.background_tasks.ids import generate_agent_id
from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.core.types import TurnResult
from agent.platform.tools.base import WiringMixin
from agent.platform.tools.builtins._shared import _normalize_optional_text
from agent.platform.tools.presentation import (
    ToolPresentationEvent,
    _enforce_cap,
    _truncate,
)

# Foreground budget before auto-backgrounding (seconds)
_DEFAULT_FOREGROUND_BUDGET = 120.0


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
# ---------------------------------------------------------------------------


class _AgentPresenter:
    """Presenter for the `agent` tool (feat-337 task→agent 收尾).

    The agent tool's result schema is ``content`` / ``agent_id`` / ``output_file``
    (not the legacy task ``summary`` / ``artifacts``), keyed by ``status``:
    ``completed`` (content), ``async_launched`` / ``message_queued`` (output_file),
    ``failed`` (error). The full dispatch ``prompt`` (from args) is placed in detail
    **before** the result — it is the key signal a human uses to judge whether the
    dispatch was accurate (spec). The prompt is bounded (a few thousand chars) and
    is intentionally NOT in the ``_enforce_cap`` truncation set.
    """

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Agent",
            summary=_truncate(description, 80),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        prompt = str(args.get("prompt", ""))
        subagent_type = str(args.get("subagent_type") or args.get("category") or "")
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            # feat-409 failalign: out-of-band 失败态 summary = 干净主参数(description),
            # 不含 error 文本。detail 保留 description + 完整 prompt(失败时 prompt 最有
            # 价值,原型:Agent 展开必含完整派发 prompt),让 AgentCard 渲染 error 一次。
            return ToolPresentationEvent(
                visible=True,
                label="Agent",
                summary=_truncate(description, 80) if description else "failed",
                detail=_enforce_cap(
                    {
                        "description": description,
                        "prompt": prompt,
                        "subagent_type": subagent_type,
                        "status": "failed",
                        "error": str(error),
                    }
                ),
            )
        if isinstance(output, Mapping):
            status = str(output.get("status", "completed"))
            # Order matters: description + full prompt first, result fields after —
            # the front-end renders this top-to-bottom (prompt before result, spec).
            detail = _enforce_cap(
                {
                    "description": description,
                    "prompt": prompt,
                    "subagent_type": subagent_type,
                    "status": status,
                    "agent_id": str(output.get("agent_id", "")),
                    "content": str(output.get("content", "")),
                    "output_file": str(output.get("output_file", "")),
                    # fix 3: coerce to plain str (raw may be None / non-JSON-native) so
                    # detail stays JSON-serializable and shape-stable for the front-end.
                    "error": str(output.get("error", "")),
                }
            )
            # The agent tool reports in-band failure via output.status == "failed"
            # (foreground exception path) rather than result.error — surface it as a
            # red "failed" summary like the out-of-band error branch above.
            # feat-409 failalign: 失败/成功态 summary 同构 = 干净主参数(description),
            # 不含 error 文本;in-band 失败的 error 已在 detail 里供 AgentCard 渲染。
            if status == "failed":
                summary = _truncate(description, 80) if description else "failed"
            else:
                summary = (
                    _truncate(description, 80) if description else f"status={status}"
                )
            return ToolPresentationEvent(
                visible=True,
                label="Agent",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Agent",
            summary=_truncate(description, 80),
        )


_AGENT_PRESENTER = _AgentPresenter()


class AgentTool(WiringMixin):
    """Launch autonomous subagents with background/foreground/continuation support."""

    name = "agent"
    is_concurrency_safe = False
    presenter = _AGENT_PRESENTER  # 决策 12: presentation travels with the tool object
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

    def bind_runtime(self, runtime: Any | None) -> None:
        """Bind runtime after bootstrap."""
        self._runtime = runtime

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

    def _run_background(
        self, args: Mapping[str, Any], ctx: ToolContext
    ) -> dict[str, Any]:
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
        registry.register_subagent(
            task_id=agent_id,
            parent_session_id=ctx.session_id or "",
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            description=description,
            prompt=prompt,
            agent_type=agent_type,
            output_file=str(output_file),
            workspace_root=str(ctx.repo_root),
        )
        registry.mark_running(agent_id)

        # Start worker
        # bugfix-422 (#129): reuse the parent's session id at the LLM request layer
        # (llm_session_id) so the subagent's provider calls group under the parent
        # in the LLM proxy session-inspector. The subagent keeps its own
        # agent_session_id for JSONL storage / resumption / agent_id lookup.
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=ctx.session_id or "",
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            on_kill=_make_on_kill(registry, agent_id),
            workspace_root=ctx.cwd,
            llm_session_id=ctx.session_id or None,
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

    def _run_foreground(
        self, args: Mapping[str, Any], ctx: ToolContext
    ) -> dict[str, Any]:
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

        # bugfix-418: submit the bare runtime.run(...) coroutine onto the kernel's
        # dedicated event loop (the same loop that created AgentRuntime's per-session
        # locks and the shared httpx client) instead of a private ThreadPoolExecutor
        # running asyncio.run on a transient loop. This eliminates the cross-loop
        # fault and isolates the subagent as an independent Task — its failure stays
        # in the returned future and cannot kill the loop or sibling runs. Bare coro
        # (no completion callback) means an in-budget result is never re-delivered as
        # a <task-notification> (bugfix-417 invariant; see decision 2).
        #
        # bugfix-420 (round-1 C1): thread a RunController so that if this run gets
        # auto-backgrounded and then task_stop'd, the worker can be cooperatively
        # aborted (returning its accumulated messages) — the same mechanism the
        # explicit run_in_background / resume paths use. Without it this third
        # terminal path could not abort and would close as COMPLETED, violating
        # decision 2's "stopped task enters killed terminal".
        controller = RunController()
        # bugfix-422 (#129): pass llm_session_id=parent so the subagent's LLM
        # requests group under the parent in the proxy session-inspector; the
        # subagent's own agent_session_id still drives JSONL storage/resumption.
        future = wiring.subagent_runner.submit_foreground(
            runtime.run(
                agent_session_id,
                [{"type": "text", "text": prompt}],
                stream=False,
                controller=controller,
                parent_session_id=ctx.session_id or "",
                workspace_root=ctx.cwd,
                llm_session_id=ctx.session_id or None,
            )
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
                workspace_root=str(ctx.repo_root),
            )
            registry.mark_running(agent_id)

            # bugfix-420 (round-1 C1): register a stop handle that aborts the
            # controller so task_stop's request_stop actually triggers the
            # cooperative abort (request_stop returns True even with no handle, so
            # without this the stop was a silent no-op).
            registry.set_stop_handle(agent_id, _ControllerStopHandle(controller))

            # Watcher thread updates registry when future completes; on abort it
            # routes to registry.kill(result_text=...) instead of complete().
            _start_registry_watcher(registry, agent_id, future, controller)

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
            workspace_root=str(workspace_root) if workspace_root is not None else None,
        )
        registry.mark_running(agent_id)

        # Start worker for the resumed turn. The subagent JSONL lives under the
        # parent session's workspace_root, threaded here so the stateless store
        # can locate it.
        # bugfix-422 (#129): llm_session_id=parent so the resumed turn's LLM
        # requests group under the parent in the proxy session-inspector.
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            on_kill=_make_on_kill(registry, agent_id),
            workspace_root=workspace_root,
            llm_session_id=parent_session_id or None,
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
        load_skills = _normalize_skill_names(
            args.get("load_skills"), tool_name=self.name
        )
        effective_workspace = ctx.cwd
        metadata: dict[str, Any] = {
            "kind": "subagent",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "description": description,
            "workspace_root": str(effective_workspace.resolve())
            if effective_workspace
            else None,
        }
        # bugfix-418 (decision 1, applied to the creation path): like the turn
        # path, run create_session on the kernel's dedicated loop via the runner —
        # never on a transient loop via bare asyncio.run. Submit directly (no
        # capability probe, no fallback): when no real runner is wired, the
        # turn step would raise anyway, so a create that silently "succeeds" via
        # asyncio.run would only re-open the cross-loop back door. Letting
        # _NoOpSubagentRunner.submit_foreground raise keeps the failure loud.
        wiring = self._require_wiring()
        create_coro = runtime.create_session(
            workspace_root=effective_workspace,
            skills=load_skills if load_skills else None,
            metadata=metadata,
            parent_session_id=ctx.session_id,
        )
        session = wiring.subagent_runner.submit_foreground(create_coro).result()
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

    def _validate_new_agent_args(
        self, args: Mapping[str, Any], *, ctx: ToolContext
    ) -> None:
        if _normalize_optional_text(args.get("description")) is None:
            raise ToolError(
                "description must be a non-empty string", tool_name=self.name
            )
        if _normalize_optional_text(args.get("prompt")) is None:
            raise ToolError("prompt must be a non-empty string", tool_name=self.name)

        load_skills = _normalize_skill_names(
            args.get("load_skills"), tool_name=self.name
        )
        # bugfix-431 决策 3: use runtime.resolve_available_skills so subagent skill
        # validation uses the same resolver as runtime and preview (同源).
        available = self._runtime.resolve_available_skills(
            ctx.repo_root,
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
        return f"Task completed.\n\n---\n\n{content}\n\nagent_id: {agent_id}"

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
            f'Use Agent with agent_id="{agent_id}" only when you want to continue the agent conversation.\n'
            f'Use task_stop with task_id="{agent_id}" to stop it.'
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


def _start_registry_watcher(
    registry: BackgroundTaskRegistry,
    task_id: str,
    future: Any,
    controller: RunController,
) -> None:
    """Start a daemon thread that waits for ``future`` and updates registry.

    bugfix-420 (round-1 C1): on a cooperative abort (task_stop set the
    controller), route to ``registry.kill(result_text=...)`` so the auto-
    backgrounded subagent enters the KILLED terminal carrying its partial result
    — matching the explicit-launch / resume paths (decision 2/3). Otherwise the
    natural completion still closes as COMPLETED.
    """

    def _watch() -> None:
        try:
            turn = future.result()
            result_text = _extract_assistant_text(turn)
            if controller.is_aborted:
                registry.kill(
                    task_id,
                    reason="stopped by user",
                    result_text=result_text,
                )
            else:
                registry.complete(
                    task_id,
                    result_text=result_text,
                )
        except Exception as exc:  # noqa: BLE001
            registry.fail(task_id, error=str(exc))

    threading.Thread(target=_watch, daemon=True).start()


class _ControllerStopHandle:
    """Stop handle that aborts a RunController (auto-background subagent).

    bugfix-420 (round-1 C1): mirrors runtime_runner._ControllerStopper so the
    registry's request_stop → handle.stop() path triggers a cooperative abort on
    the auto-backgrounded foreground run.
    """

    def __init__(self, controller: RunController) -> None:
        self._controller = controller

    def stop(self) -> None:
        self._controller.abort()


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


def _make_on_kill(registry: BackgroundTaskRegistry, agent_id: str) -> Any:
    # bugfix-420 decision 3: the subagent worker routes cooperative aborts
    # (task_stop) here. notified=False (default) lets the _NotifyingStore deliver
    # the killed <task-notification>, now carrying the partial result_text rather
    # than being an empty-shell duplicate of the tool_result.
    def _on_kill(
        *,
        task_id: str,
        result_text: str | None,
        usage: Mapping[str, Any] | None,
        duration_ms: int,
        tool_use_count: int,
    ) -> None:
        registry.kill(
            agent_id,
            reason="stopped by user",
            result_text=result_text,
        )

    return _on_kill


# ------------------------------------------------------------------
# Text / argument helpers
# ------------------------------------------------------------------


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
            raise ToolError(
                "load_skills must be an array of strings", tool_name=tool_name
            )
        name = item.strip()
        if not name:
            raise ToolError(
                "load_skills contains an empty skill name", tool_name=tool_name
            )
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
