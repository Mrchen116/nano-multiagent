"""Built-in `Agent` tool for background and foreground sub-agent execution."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from concurrent.futures import CancelledError, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

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
from agent.platform.tools.subagent_types import (
    DEFAULT_AGENT_TYPE_NAME,
    SubagentTypeDefinition,
    apply_tool_deny,
    iter_agent_types,
    resolve_agent_type,
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
        detail: dict[str, Any] = {
            "description": description,
            "prompt": str(args.get("prompt", "")),
        }
        # bugfix-474-fix1: a continuation call (`agent_id` present) never
        # resolves a type — `_run_continuation` dispatches straight to the
        # existing session, it doesn't call `resolve_agent_type`. Defaulting
        # to DEFAULT_AGENT_TYPE_NAME here would mislabel an Explore/Plan
        # follow-up as general-purpose. Only genuinely new agents (no
        # agent_id) get the default; format_end fills in the real type once
        # the result is available.
        if _normalize_optional_text(args.get("agent_id")) is None:
            detail["subagent_type"] = str(
                args.get("subagent_type") or DEFAULT_AGENT_TYPE_NAME
            )
        return ToolPresentationEvent(
            visible=True,
            label="Agent",
            summary=_truncate(description, 80),
            detail=detail,
        )

    def _resolve_display_type(
        self, args: Mapping[str, Any], output: Any, *, is_continuation: bool
    ) -> str | None:
        """Resolve the type to show in presentation detail, or ``None`` to omit it.

        New agents always show a type — default general-purpose when omitted,
        mirroring `resolve_agent_type`'s actual runtime default. Continuation
        calls never re-resolve a type, so faking the default would mislabel an
        Explore/Plan follow-up; prefer the real type carried on the result
        (``output["agent_type"]``, sourced from the registry record/JSONL
        metadata) and otherwise show nothing rather than a guess.
        """

        explicit = _normalize_optional_text(args.get("subagent_type"))
        if explicit is not None:
            return explicit
        if not is_continuation:
            return DEFAULT_AGENT_TYPE_NAME
        if isinstance(output, Mapping):
            return _normalize_optional_text(output.get("agent_type"))
        return None

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        prompt = str(args.get("prompt", ""))
        is_continuation = _normalize_optional_text(args.get("agent_id")) is not None
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        subagent_type = self._resolve_display_type(
            args, output, is_continuation=is_continuation
        )
        if error:
            # feat-409 failalign: out-of-band 失败态 summary = 干净主参数(description),
            # 不含 error 文本。detail 保留 description + 完整 prompt(失败时 prompt 最有
            # 价值,原型:Agent 展开必含完整派发 prompt),让 AgentCard 渲染 error 一次。
            detail: dict[str, Any] = {
                "description": description,
                "prompt": prompt,
            }
            if subagent_type is not None:
                detail["subagent_type"] = subagent_type
            detail["status"] = "failed"
            detail["error"] = str(error)
            return ToolPresentationEvent(
                visible=True,
                label="Agent",
                summary=_truncate(description, 80) if description else "failed",
                detail=_enforce_cap(detail),
            )
        if isinstance(output, Mapping):
            status = str(output.get("status", "completed"))
            # Order matters: description + full prompt first, result fields after —
            # the front-end renders this top-to-bottom (prompt before result, spec).
            detail = {
                "description": description,
                "prompt": prompt,
            }
            if subagent_type is not None:
                detail["subagent_type"] = subagent_type
            detail.update(
                {
                    "status": status,
                    "agent_id": str(output.get("agent_id", "")),
                    "content": str(output.get("content", "")),
                    "output_file": str(output.get("output_file", "")),
                    # fix 3: coerce to plain str (raw may be None / non-JSON-native) so
                    # detail stays JSON-serializable and shape-stable for the front-end.
                    "error": str(output.get("error", "")),
                }
            )
            detail = _enforce_cap(detail)
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


def _build_description() -> str:
    """Compose the tool description, listing built-in types from the catalog.

    feat-474 决策 5: whenToUse + 缺省行为随 `subagent_types` 目录自动列出，扩展类型
    只需改目录，不必手改这段文案（对齐 CC：类型列表不塞进 schema enum）。
    """

    type_lines = "\n".join(
        f"  - {definition.name}: {definition.when_to_use}"
        for definition in iter_agent_types()
    )
    return (
        "Launch a new agent to handle complex, multi-step tasks autonomously.\n\n"
        "Use this tool for tasks that are complex, multi-step, require independent context, "
        "or can be run in parallel with other work. Do not use it for reading a specific file path, "
        "searching a single symbol, or simple lookups across 2-3 files — use read/bash/search tools instead.\n\n"
        "- description: Short task description (3-5 words).\n"
        "- prompt: Full detailed prompt for the agent. Must include goal, background, constraints, "
        "known information, and expected output. Need a skill loaded? Name it and its usage in the prompt.\n"
        f"- subagent_type: Optional; defaults to '{DEFAULT_AGENT_TYPE_NAME}' when omitted. Available types:\n"
        f"{type_lines}\n"
        "- run_in_background: true=run in background (returns agent_id immediately); false=wait for result. "
        "Default: false. Background tasks complete automatically; do not sleep, poll, or proactively check progress. "
        "A foreground call that runs past the default budget is auto-backgrounded — there is no timeout parameter.\n"
        "- agent_id: Send a follow-up to an existing agent by ID. If running, message is queued; if stopped, resumes from transcript.\n\n"
        "Prompts MUST be in English."
    )


class AgentTool(WiringMixin):
    """Launch autonomous subagents with background/foreground/continuation support."""

    name = "agent"
    is_concurrency_safe = False
    presenter = _AGENT_PRESENTER  # 决策 12: presentation travels with the tool object
    description = _build_description()
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
                "description": (
                    f"Built-in agent type; defaults to '{DEFAULT_AGENT_TYPE_NAME}' "
                    "when omitted. See tool description for the available types."
                ),
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
        },
        "required": ["description", "prompt"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        wiring: Any | None = None,
    ) -> None:
        self._wiring = wiring

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Any:
        """Execute one agent request: background, foreground, or continuation."""

        agent_id = _normalize_optional_text(args.get("agent_id"))
        if agent_id is not None:
            return self._run_continuation(agent_id=agent_id, args=args, ctx=ctx)

        self._validate_new_agent_args(args)
        # Resolve the type before doing anything else (agent_id generation,
        # session creation): an unknown/mis-cased type must fail fast with no
        # side effects, matching CC (决策 8 澄清).
        type_definition = resolve_agent_type(
            _normalize_optional_text(args.get("subagent_type"))
        )
        run_in_background = _normalize_run_in_background(args.get("run_in_background"))

        if run_in_background:
            return self._run_background(
                args=args, ctx=ctx, type_definition=type_definition
            )
        return self._run_foreground(
            args=args, ctx=ctx, type_definition=type_definition
        )

    # ------------------------------------------------------------------
    # Background launch
    # ------------------------------------------------------------------

    def _run_background(
        self,
        args: Mapping[str, Any],
        ctx: ToolContext,
        *,
        type_definition: SubagentTypeDefinition,
    ) -> dict[str, Any]:
        control = self._require_control(ctx)
        wiring = self._require_wiring()
        registry = wiring.registry

        agent_id = generate_agent_id()
        description = _normalize_optional_text(args.get("description")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        agent_type = type_definition.name

        # Create subagent session with metadata
        agent_session_id = self._create_subagent_session(
            control=control,
            ctx=ctx,
            agent_id=agent_id,
            type_definition=type_definition,
            description=description,
        )

        # Subagent sessions are created with workspace_root=ctx.cwd; their JSONL
        # lives under {ctx.cwd}/.nano/sessions/{parent}/subagents/. Thread ctx.cwd
        # so the stateless store can locate it.
        output_file = self._resolve_output_file(
            control, agent_session_id, ctx.session_id, ctx.cwd
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
        # bugfix-443: inherit the parent run's model so the subagent and its
        # whole side-chain (its own compaction/fork/hook) follow the parent
        # model instead of the build-time global default.
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=ctx.session_id or "",
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            on_kill=_make_on_kill(registry, agent_id),
            workspace_root=ctx.cwd,
            llm_session_id=ctx.session_id or None,
            model=control.resolve_run_model(),
        )
        registry.set_stop_handle(agent_id, stopper)
        registry.set_message_handle(agent_id, stopper)

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
        self,
        args: Mapping[str, Any],
        ctx: ToolContext,
        *,
        type_definition: SubagentTypeDefinition,
    ) -> dict[str, Any]:
        control = self._require_control(ctx)
        wiring = self._require_wiring()

        agent_id = generate_agent_id()
        description = _normalize_optional_text(args.get("description")) or ""
        prompt = _normalize_optional_text(args.get("prompt")) or ""
        agent_type = type_definition.name
        # feat-474: the foreground budget is a fixed system default, not a
        # model-tunable schema field (spec Q1 — aligned with CC's ~120s, no
        # `timeout_seconds` parameter).
        timeout_seconds = _DEFAULT_FOREGROUND_BUDGET

        agent_session_id = self._create_subagent_session(
            control=control,
            ctx=ctx,
            agent_id=agent_id,
            type_definition=type_definition,
            description=description,
        )

        # Subagent sessions are created with workspace_root=ctx.cwd; thread it so
        # the stateless store can locate the subagent JSONL.
        output_file = self._resolve_output_file(
            control, agent_session_id, ctx.session_id, ctx.cwd
        )

        handle = wiring.subagent_runner.start_foreground(
            agent_session_id=agent_session_id,
            parent_session_id=ctx.session_id or "",
            prompt=prompt,
            workspace_root=ctx.cwd,
            llm_session_id=ctx.session_id or None,
            model=control.resolve_run_model(),
        )

        try:
            turn = handle.result(timeout=timeout_seconds)
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

            registry.set_stop_handle(agent_id, handle)
            registry.set_message_handle(agent_id, handle)

            _start_registry_watcher(registry, agent_id, handle)

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
        control = self._require_control(ctx)
        parent_workspace_root = control.workspace_root

        # 1. Check in-memory registry
        record = registry.get(agent_id)
        if record is not None and record.task_type.value == "subagent":
            if record.status == BackgroundTaskStatus.RUNNING:
                accepted = registry.send_agent_message(agent_id, prompt)
                if accepted:
                    return {
                        "status": "message_queued",
                        "agent_id": agent_id,
                        "description": record.description,
                        "output_file": record.output_file,
                        # bugfix-474-fix1: real type off the registry record so
                        # the presenter shows it instead of guessing
                        # general-purpose for a still-running continuation.
                        "agent_type": record.agent_type or "",
                    }
                current = registry.get(agent_id)
                if (
                    current is not None
                    and current.status != BackgroundTaskStatus.RUNNING
                ):
                    return self._resume_subagent(
                        agent_id=agent_id,
                        agent_session_id=current.agent_session_id,
                        parent_session_id=current.parent_session_id,
                        resuming_session_id=ctx.session_id,
                        prompt=prompt,
                        description=current.description,
                        output_file=current.output_file,
                        agent_type=current.agent_type,
                        workspace_root=parent_workspace_root,
                        control=control,
                    )
                raise ToolError(
                    (
                        "Running subagent did not confirm live delivery; "
                        "the follow-up was not queued."
                    ),
                    tool_name=self.name,
                    details={"code": "agent_message_not_deliverable"},
                )
            # Terminal but in memory: resume with new turn
            return self._resume_subagent(
                agent_id=agent_id,
                agent_session_id=record.agent_session_id,
                parent_session_id=record.parent_session_id,
                resuming_session_id=ctx.session_id,
                prompt=prompt,
                description=record.description,
                output_file=record.output_file,
                agent_type=record.agent_type,
                workspace_root=parent_workspace_root,
                control=control,
            )

        # 2. Try JSONL rehydrate. The stateless store needs the parent's
        # workspace_root (resolved above) to locate both the index scan and the
        # subagent file.
        parent_session_id = ctx.session_id or ""
        found = control.find_subagent(agent_id)
        if found is None:
            raise ToolError(
                f'No subagent with agent_id="{agent_id}" found in session history.',
                tool_name=self.name,
                details={"code": "agent_not_found"},
            )

        found_session_id = str(found["session_id"])
        metadata = dict(found.get("metadata") or {})
        description = metadata.get("description", "")
        agent_type = metadata.get("agent_type")
        output_file = str(found["output_path"])

        return self._resume_subagent(
            agent_id=agent_id,
            agent_session_id=found_session_id,
            parent_session_id=parent_session_id,
            resuming_session_id=ctx.session_id,
            prompt=prompt,
            description=description,
            output_file=output_file,
            agent_type=agent_type,
            workspace_root=parent_workspace_root,
            control=control,
        )

    def _resume_subagent(
        self,
        *,
        agent_id: str,
        agent_session_id: str | None,
        parent_session_id: str,
        resuming_session_id: str | None,
        prompt: str,
        description: str,
        output_file: str,
        agent_type: str | None,
        workspace_root: Path | None = None,
        control: Any,
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

        # Start the resumed turn through the typed runtime runner. The child
        # conversation is addressed within its parent's workspace root, so that
        # root remains part of the stable SessionRef lookup.
        # bugfix-422 (#129): llm_session_id=parent so the resumed turn's LLM
        # requests group under the parent in the proxy session-inspector.
        # bugfix-443 fix1 C4: resolve the model from the *current resuming run*
        # (resuming_session_id=ctx.session_id), not the original launcher
        # (parent_session_id) — the launcher run may already be terminal and
        # popped from _active_run_models, which would yield None and wrongly fall
        # back to the global default. Path / proxy grouping still key on
        # parent_session_id.
        stopper = wiring.subagent_runner.start(
            agent_session_id=agent_session_id,
            parent_session_id=parent_session_id,
            prompt=prompt,
            on_complete=_make_on_complete(registry, agent_id),
            on_fail=_make_on_fail(registry, agent_id),
            on_kill=_make_on_kill(registry, agent_id),
            workspace_root=workspace_root,
            llm_session_id=parent_session_id or None,
            model=control.resolve_run_model(),
        )
        registry.set_stop_handle(agent_id, stopper)
        registry.set_message_handle(agent_id, stopper)

        return {
            "status": "async_launched",
            "agent_id": agent_id,
            "description": description,
            "output_file": output_file,
            # bugfix-474-fix1: real type (registry record / rehydrated JSONL
            # metadata) so the presenter shows it instead of guessing
            # general-purpose for a resumed continuation.
            "agent_type": agent_type or "",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_subagent_session(
        self,
        *,
        control: Any,
        ctx: ToolContext,
        agent_id: str,
        type_definition: SubagentTypeDefinition,
        description: str,
    ) -> str:
        """Create the child session with an explicit tool set, role prompt, and
        inherited skills (feat-474 决策 2/3/4).

        The child's ``tool_allowlist`` is always written explicitly (never bare
        ``None``): a parent with a persisted allowlist passes it straight
        through; a parent with none (product default) resolves its currently
        active turn's already-resolved tool names via the control's narrow
        window, so this never reaches into runtime private ``_resolve_*``
        methods. The type's ``disallowed_tools`` is then subtracted.

        ``skills`` is read from the parent session as-is (``None`` / non-empty /
        empty) and passed through unfolded — the child must never be wider than
        the parent's configured skill visibility.
        """

        parent_session = control.directory.get(control.ref)
        if parent_session is None:
            raise ToolError(
                "parent session not found while creating subagent",
                tool_name=self.name,
            )
        parent_tools = (
            parent_session.tool_allowlist
            if parent_session.tool_allowlist is not None
            else tuple(control.list_parent_enabled_tool_names())
        )
        effective_tools = apply_tool_deny(
            parent_tools, type_definition.disallowed_tools
        )

        effective_workspace = ctx.cwd
        metadata: dict[str, Any] = {
            "kind": "subagent",
            "agent_id": agent_id,
            "agent_type": type_definition.name,
            "description": description,
            "workspace_root": str(effective_workspace.resolve())
            if effective_workspace
            else None,
        }
        session = control.create_subagent(
            workspace_root=effective_workspace,
            skills=parent_session.skills,
            tool_allowlist=effective_tools,
            prompt_seed=type_definition.role_prompt_seed,
            metadata=metadata,
            parent_session_id=ctx.session_id,
        )
        return str(session.session_id)

    def _resolve_output_file(
        self,
        control: Any,
        agent_session_id: str,
        parent_session_id: str | None,
        workspace_root: Path,
    ) -> Path:
        # Subagent JSONL lives under the parent session's workspace_root, which
        # is the spawning turn's ctx.cwd (also used as the subagent's own
        # workspace_root at create_session time).
        return control.output_path(
            agent_session_id,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id or "",
        )

    def _require_control(self, ctx: ToolContext) -> Any:
        control = ctx.subagent_control
        if control is None:
            raise ToolError("subagent control is not configured", tool_name=self.name)
        return control

    def _validate_new_agent_args(self, args: Mapping[str, Any]) -> None:
        """Validate the two fields every new-agent call still needs.

        feat-474: skill selection and category/subagent_type mutual-exclusion
        no longer exist as schema fields — the JSON Schema's
        ``additionalProperties: false`` already rejects any caller still
        passing the removed ``load_skills`` / ``category`` / `timeout_seconds`
        fields (spec「已删除的仪式字段不可再传」), so this method only checks
        what schema validation cannot: non-empty content for the two required
        strings.
        """

        if _normalize_optional_text(args.get("description")) is None:
            raise ToolError(
                "description must be a non-empty string", tool_name=self.name
            )
        if _normalize_optional_text(args.get("prompt")) is None:
            raise ToolError("prompt must be a non-empty string", tool_name=self.name)

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
    handle: Any,
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
            turn = handle.result()
            result_text = _extract_assistant_text(turn)
            registry.complete(task_id, result_text=result_text)
        except CancelledError:
            registry.kill(task_id, reason="stopped by user", result_text=None)
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


def _extract_assistant_text(turn: TurnResult | Any) -> str | None:
    messages = getattr(turn, "messages", ())
    for message in reversed(messages):
        if getattr(message, "role", None) == "assistant":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None
