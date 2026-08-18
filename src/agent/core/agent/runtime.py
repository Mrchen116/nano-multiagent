"""High-level runtime orchestration over sessions, hooks, loop, and compaction."""

import asyncio
import contextlib
import json
import logging
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from agent.core.agent.liveness import (
    _broker_publish_adapter,
    _emit_liveness_heartbeats,
)
from agent.core.errors import CompactionError, ModelError
from agent.core.ids import make_message_id, make_tool_call_id, make_turn_id
from agent.core.types import (
    Message,
    TokenUsage,
    ToolCall,
    ToolResult,
    ToolSpec,
    TurnResult,
)
from agent.core.hooks.context import HookContext, HookModelCall, HookModelResult
from agent.core.hooks.runner import HookRunner, log_hook_diagnostics
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
from agent.core.llm.model_registry import context_window_for_model, provider_of
from agent.core.session.conversation import ConversationState
from agent.core.session.transcript import USER_INTERRUPT_RECOVERY_CONTENT
from agent.core.session.types import INTERNAL_RUNTIME_KEY, SessionConfig, TurnRequest
from agent.core.skills import (
    build_skill_search_roots,
    SkillMetadata,
    make_skill_resolver,
    resolve_available_skills,
)
from agent.core.skills.usage import SkillSessionRef, skill_refs_for_session
from agent.core.tools.result_budget import ToolResultCompressor
from agent.core.workspace import WorkspaceExecutionScope
from agent.core.session.context_state import (
    MemorySnapshot,
    SessionFileState,
    read_file_slice,
)
from .compaction.applier import CompactionApplier
from .compaction.planner import CompactionPlanner
from .compaction.summarizer import CompactionSummarizer
from .compaction.types import CompactionReason, CompactionResult, CompactionSettings
from .context_fork import AgentContextFork
from .loop import AgentLoop, ToolRegistryLike
from .policies import AgentPolicies
from .run_control import RunController
from .prompting import build_system_prompt
from .skill_commands import SkillCommand, parse_skill_command, rewrite_skill_command
from .state import (
    AgentState,
    InputPart,
    parse_input_parts,
    render_user_content_parts,
    render_user_text,
)


def _rewrite_skill_command_in_parts(
    parts: Sequence[InputPart],
) -> tuple[InputPart, ...]:
    """Rewrite the `/skill:` shortcut on the single text part that carries it.

    feat-430 fix-r2: in a multi-part turn the command lives in one specific text part
    (the current message), which may be the last part (group buffered context) or a
    non-last part accompanying a trailing image. Rewriting per-part keeps the
    transformation on that part wherever the multi-part split later places it, instead
    of rewriting the joined text (which misses non-first lines and mis-reads an
    `[image:placeholder]` line as a `[sender]` prefix). At most one command exists, so
    the first matching text part is rewritten and the rest pass through untouched.
    """

    out: list[InputPart] = []
    rewritten = False
    for part in parts:
        if not rewritten and part.type == "text" and part.text is not None:
            new_text = rewrite_skill_command(part.text)
            if new_text != part.text:
                part = replace(part, text=new_text)
                rewritten = True
        out.append(part)
    return tuple(out)


def _parse_skill_command_in_parts(parts: Sequence[InputPart]) -> SkillCommand | None:
    for part in parts:
        if part.type == "text" and part.text is not None:
            command = parse_skill_command(part.text)
            if command is not None:
                return command
    return None


from agent.core.session.entries import message_from_turn_entry
from agent.core.agent.prompt_sections.base import (
    PromptSection,
    resolve_effective_prompt,
)
from agent.core.agent.prompt_sections.wiring import (
    build_prompt_context_from_metadata,
    resolve_flags_from_metadata,
)
from agent.core.agent import agents_md as agents_md_loader
from agent.core.memory.path import derive_memory_root
from agent.core.memory.store import MemoryStore

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from agent.core.hooks.registry import HookRegistry


class AgentEngine:
    """Execute agent algorithms against caller-owned conversation state."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        llm_client_factory: Callable[[LLMFactoryConfig], LLMClient] | None = None,
        llm_clients: dict[str, LLMClient] | None = None,
        model: str | None = None,
        policies: AgentPolicies | None = None,
        hook_runner: HookRunner | None = None,
        repo_root: Path | None = None,
        available_skills: Sequence[SkillMetadata] | None = None,
        compaction_settings: CompactionSettings | None = None,
        tool_registry: ToolRegistryLike | None = None,
        system_prompt: str | None = None,
        # bugfix-431 决策 1/3: replaced config_resolver (legacy ProductProfile field,
        # always None since refactor-406) with explicit workspace_config_dirname +
        # skill_search_roots so runtime skill resolution uses the same make_skill_resolver
        # helper as Kernel.list_skills / assemble_prompt_preview.
        workspace_config_dirname: str | None = None,
        workspace_skill_dirnames: tuple[str, ...] | None = None,
        skill_search_roots: tuple[Path, ...] = (),
        default_tool_ids: list[str] | None = None,
        permission_broker: Any | None = None,
        prompt_sections: Sequence[PromptSection] | None = None,
        execution_scope_resolver: Callable[[Path], WorkspaceExecutionScope]
        | None = None,
    ) -> None:
        env_llm_config = LLMFactoryConfig.from_env()
        self._llm_config = LLMFactoryConfig(
            provider=env_llm_config.provider,
            model=model or env_llm_config.model,
            base_url=env_llm_config.base_url,
            api_key=env_llm_config.api_key,
            timeout_seconds=env_llm_config.timeout_seconds,
        )
        # Prefer explicit client > factory > error.
        # unit tests pass llm_client directly and do not need a factory.
        # Production paths (create_app, build_kernel) must inject llm_client_factory.
        if llm_client is not None:
            active_llm_client = llm_client
        elif llm_client_factory is not None:
            active_llm_client = llm_client_factory(self._llm_config)
        else:
            raise ValueError(
                "AgentEngine requires either llm_client or llm_client_factory; "
                "pass llm_client for unit tests, llm_client_factory for production wiring"
            )
        # bugfix-429 fix-r1 #3: removed dead self._llm_client_factory field — its only
        # reader was reconfigure_llm (retired). The factory is used at construction only.
        self._llm_client = active_llm_client
        # bugfix-429 决策3: per-provider client map for routing each run to the
        # client of its model's registered provider. None → single-client path
        # (unit tests / legacy callers): active_llm_client serves every model.
        self._llm_clients = llm_clients
        self._hook_runner = hook_runner
        self._repo_root = (repo_root or Path.cwd()).expanduser().resolve()
        # bugfix-431 决策 1: store resolver inputs so per-session resolver can be
        # constructed on demand via make_skill_resolver (same as Kernel.list_skills).
        self._workspace_config_dirname = workspace_config_dirname
        self._workspace_skill_dirnames = workspace_skill_dirnames
        self._skill_search_roots = skill_search_roots
        self._compaction_settings = compaction_settings or CompactionSettings()
        resolved_skills = (
            tuple(available_skills) if available_skills is not None else ()
        )
        # PermissionBroker wired by platform layer (create_app). None in contexts that
        # don't support the ask flow (unit tests, CI without interactive terminal).
        # Stored here so _build_hook_context can inject permission_requester per call.
        self._permission_broker = permission_broker
        # Optional consumer-supplied can_use_tool callback. When set (injected by
        # Kernel.__init__ for CLI products), _build_hook_context races the callback
        # against the broker future so the CLI's interactive prompt resolves the ask
        # without needing an IM card.  PA products leave this None and resolve via
        # Kernel.submit_permission_decision (IM card flow).
        self._can_use_tool: Any | None = None
        # Product default tool ids used when no per-session tool_allowlist is set.
        # None means "all tools in registry" (platform default behavior).
        self._default_tool_ids = default_tool_ids
        self._tool_registry = tool_registry
        self._execution_scope_resolver = execution_scope_resolver
        self._active_state: ContextVar[ConversationState | None] = ContextVar(
            "agent_engine_active_conversation", default=None
        )
        self._active_execution_scope: ContextVar[WorkspaceExecutionScope | None] = (
            ContextVar("agent_engine_workspace_execution_scope", default=None)
        )
        # Prompt sections for segment-based assembly; empty list = no sections registered (legacy path).
        self._prompt_sections: list[PromptSection] = (
            list(prompt_sections) if prompt_sections else []
        )
        self._skill_batch_review_queued: set[str] = set()
        self._skill_batch_review_running: set[str] = set()
        self._skill_batch_review_triggers: dict[str, Any] = {}
        self._skill_batch_review_drain_scheduler: Callable[[Any], None] | None = None
        tool_results_dir = self._repo_root / ".nano" / "tool-results"
        self._tool_result_compressor = ToolResultCompressor(tool_results_dir)
        self._context_fork = AgentContextFork(
            llm_client=active_llm_client,
            llm_clients=llm_clients,
            model=self._llm_config.model,
            policies=policies,
            system_prompt=system_prompt,
            available_skills=resolved_skills,
            tool_registry=tool_registry,
            current_working_directory=self._repo_root,
        )
        self._compaction_planner = CompactionPlanner(
            min_kept_messages=self._compaction_settings.min_kept_messages
        )
        # Use a dedicated fork with summary_model when configured so that
        # the summarizer calls a separate model instead of the main agent model.
        summary_model = self._compaction_settings.summary_model
        if summary_model:
            _summary_fork = AgentContextFork(
                llm_client=active_llm_client,
                model=summary_model,
                policies=policies,
                system_prompt=system_prompt,
                current_working_directory=self._repo_root,
            )
        else:
            _summary_fork = self._context_fork
        # bugfix-429 fix-r1 #2: when a dedicated summary_model fork is configured it
        # has its own fixed model — don't override it with the run's model. Only the
        # shared fork follows the per-run model.
        self._summary_fork_has_dedicated_model = bool(summary_model)
        self._compaction_summarizer = CompactionSummarizer(
            fork=_summary_fork,
            has_dedicated_model=self._summary_fork_has_dedicated_model,
        )
        self._compaction_applier = CompactionApplier()
        self._loop = AgentLoop(
            llm_client=active_llm_client,
            llm_clients=llm_clients,
            model=self._llm_config.model,
            policies=policies,
            hook_runner=hook_runner,
            available_skills=resolved_skills,
            tool_registry=tool_registry,
            current_working_directory=self._repo_root,
            system_prompt=system_prompt,
            tool_result_compressor=self._tool_result_compressor,
            compaction_entries=lambda: self._state().transcript.list_event_entries(),
            compaction_planner=self._compaction_planner,
            compaction_summarizer=self._compaction_summarizer,
            compaction_settings=self._compaction_settings,
            automatic_compaction_failures=lambda: (
                self._state().automatic_compaction_failures
            ),
            on_compaction=self._invalidate_memory_snapshot,
            capture_compaction_epoch=lambda: self._state().transcript.external_epoch,
            commit_compaction=self._commit_threshold_compaction,
            build_skill_reinjection=self._build_skill_reinjection_message,
        )

    async def execute_turn(
        self, state: ConversationState, request: TurnRequest
    ) -> TurnResult:
        """Execute one turn while the owning ConversationSession holds its gate."""

        token = self._active_state.set(state)
        scope_token = self._active_execution_scope.set(
            self._scope_for_workspace(state.config.workspace_root)
        )
        try:
            return await self._run_locked(
                session_id=state.ref.session_id,
                parts=request.parts,
                llm_session_id=request.llm_session_id,
                run_id=request.run_id,
                trace_id=request.trace_id,
                controller=request.controller,
                parent_session_id=state.ref.parent_session_id,
                workspace_root=state.ref.workspace_root,
                origin=request.origin,
                model=request.model,
                source_background_returns=request.source_background_returns,
                replay_last_user=request.replay_last_user,
            )
        finally:
            self._active_execution_scope.reset(scope_token)
            self._active_state.reset(token)

    def _state(self) -> ConversationState:
        state = self._active_state.get()
        if state is None:
            raise RuntimeError("agent engine method requires an active conversation")
        return state

    async def compact(
        self,
        state: ConversationState,
        *,
        focus: str | None = None,
        idempotency_key: str | None = None,
    ) -> CompactionResult | None:
        """Run manual compaction against one caller-owned conversation state."""

        token = self._active_state.set(state)
        scope_token = self._active_execution_scope.set(
            self._scope_for_workspace(state.config.workspace_root)
        )
        try:
            return await self._compact_session(
                session_id=state.ref.session_id,
                reason=CompactionReason.MANUAL,
                focus=focus,
                idempotency_key=idempotency_key,
            )
        finally:
            self._active_execution_scope.reset(scope_token)
            self._active_state.reset(token)

    def set_execution_scope_resolver(
        self, resolver: Callable[[Path], WorkspaceExecutionScope] | None
    ) -> None:
        """Install the SDK-owned resolver used at each session execution boundary."""

        self._execution_scope_resolver = resolver

    def _scope_for_workspace(
        self, workspace_root: Path
    ) -> WorkspaceExecutionScope | None:
        resolver = self._execution_scope_resolver
        return resolver(workspace_root) if resolver is not None else None

    def _current_scope(self) -> WorkspaceExecutionScope | None:
        """Return the immutable scope captured for the active turn, if any."""

        return self._active_execution_scope.get()

    def _current_tool_registry(self) -> ToolRegistryLike | None:
        scope = self._current_scope()
        return scope.tool_registry if scope is not None else self._tool_registry

    def _current_hook_runner(self) -> HookRunner | None:
        scope = self._current_scope()
        return scope.hook_runner if scope is not None else self._hook_runner

    async def _run_locked(
        self,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        *,
        llm_session_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        controller: RunController | None = None,
        parent_session_id: str | None = None,
        workspace_root: Path | None = None,
        origin: Any = None,
        model: str | None = None,
        source_background_returns: tuple[Mapping[str, Any], ...] = (),
        replay_last_user: bool = False,
    ) -> TurnResult:
        """Internal run implementation (assumes session lock is held)."""

        state = self._state()
        history = state.history
        config = state.config
        path = state.transcript.path

        session_created_at = config.created_at
        session_workspace_root = config.workspace_root
        session_available_skills = self._resolve_session_available_skills_from_config(
            config
        )
        session_available_tools = self._resolve_session_available_tools_from_config(
            config
        )
        frozen_system_prompt = config.system_prompt

        last_user: Message | None = None
        if replay_last_user:
            last_user = next(
                (message for message in reversed(history) if message.role == "user"),
                None,
            )
            if last_user is None:
                raise ValueError("replay-last-user requires a prior user message")
            user_text = last_user.content if isinstance(last_user.content, str) else ""
            if last_user.parts:
                input_parts = parse_input_parts(
                    [{"type": "text", "text": user_text}]
                    if not any(
                        isinstance(part, Mapping) and part.get("type") == "text"
                        for part in last_user.parts
                    )
                    else list(last_user.parts)
                )
            else:
                input_parts = parse_input_parts(
                    [{"type": "text", "text": user_text}] if user_text else []
                )
            if not user_text:
                user_text = render_user_text(input_parts)
        else:
            input_parts = parse_input_parts(parts)
            user_text = render_user_text(input_parts)
            if not user_text:
                raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        state.partial_turn_id = turn_id
        state.partial_messages = []
        state.partial_tool_calls = ()
        state.partial_usage = None
        hook_metadata: dict[str, Any] = (
            dict(config.metadata) if isinstance(config.metadata, Mapping) else {}
        )
        hook_metadata["cwd"] = str(session_workspace_root)
        hook_metadata["transcript_path"] = str(path)
        if config.skills is not None:
            hook_metadata["skills"] = list(config.skills)
        # feat-436: 按当前 run 的 model 取上下文窗口（前端 token 显示分母随之 per-model）；
        # 未配 / 未知 / 注册表未初始化时回退全局默认。
        hook_metadata["context_window"] = (
            context_window_for_model(model) or self._compaction_settings.context_window
        )
        # Thread workspace_root per-turn so MemoryTool + _ensure_memory_snapshot share
        # the same derivation path (both use derive_memory_root for isolation).
        if session_workspace_root is not None:
            hook_metadata["workspace_root"] = str(session_workspace_root)
        if isinstance(run_id, str) and run_id.strip():
            hook_metadata["run_id"] = run_id.strip()
        if isinstance(trace_id, str) and trace_id.strip():
            hook_metadata["trace_id"] = trace_id.strip()
        # Thread RunRecord.origin through to hook_metadata so auto_mode_gate can
        # detect unattended contexts (RunOrigin.HEARTBEAT etc.) without importing
        # RunOrigin in core hooks. Use .value (string) for decoupling.
        if origin is not None:
            hook_metadata["run_origin"] = getattr(origin, "value", str(origin))
        from agent.core.workflows.activation import (  # noqa: PLC0415
            output_token_budget_for_turn,
        )

        workflow_budget = output_token_budget_for_turn(
            origin=str(hook_metadata.get("run_origin") or ""),
            human_text=user_text,
        )
        if workflow_budget is not None:
            hook_metadata["workflow_output_token_budget"] = workflow_budget
        if source_background_returns:
            hook_metadata["source_background_returns"] = [
                dict(item) for item in source_background_returns
            ]
        runtime_payload = config.metadata.get(INTERNAL_RUNTIME_KEY)
        if (
            isinstance(runtime_payload, Mapping)
            and runtime_payload.get("workflow_ultracode") is True
        ):
            hook_metadata["workflow_ultracode"] = True
        hook_ctx = self._build_hook_context(
            session_id=session_id,
            turn_id=turn_id,
            metadata=hook_metadata,
            controller=controller,
        )

        input_payload, handled = await self._dispatch_intercept(
            "input",
            {
                "text": user_text,
                "images": _extract_input_images(input_parts),
            },
            hook_ctx,
        )
        if handled:
            return TurnResult(
                session_id=session_id,
                turn_id=turn_id,
                messages=(),
                completed=True,
                stop_reason="handled_by_hook",
            )
        transformed_text = input_payload.get("text", user_text)
        if isinstance(transformed_text, str):
            user_text = transformed_text
        if not user_text and not replay_last_user:
            raise ValueError("empty input parts are not allowed")
        # feat-430 fix-r2: rewrite the `/skill:` shortcut on the command-bearing text part.
        # Single-part turns rewrite the (possibly hook-transformed) user_text directly.
        # Multi-part turns rewrite the specific text part holding the command and re-derive
        # user_text from the rewritten parts, so the transformation survives the later
        # last-part split (group buffered context OR text + trailing image) and never
        # corrupts the joined/persisted text by mis-reading an image placeholder line.
        # replay 不再次解析 /skill:，避免把已经执行过的快捷指令再跑一遍。
        slash_skill_command = None
        if not replay_last_user:
            slash_skill_command = (
                _parse_skill_command_in_parts(input_parts)
                if len(input_parts) > 1
                else parse_skill_command(user_text)
            )
            if len(input_parts) > 1:
                input_parts = _rewrite_skill_command_in_parts(input_parts)
                user_text = render_user_text(input_parts)
            else:
                user_text = rewrite_skill_command(user_text)

        before_payload, _ = await self._dispatch_intercept(
            "before_agent_start",
            {"message": user_text, "system_prompt": None},
            hook_ctx,
        )
        message_override = before_payload.get("message")
        if isinstance(message_override, str):
            user_text = message_override
        if not user_text and not replay_last_user:
            raise ValueError("empty input parts are not allowed")
        hook_system_prompt_override = before_payload.get("system_prompt")
        if isinstance(hook_system_prompt_override, str):
            hook_system_prompt_override = hook_system_prompt_override.strip() or None
        else:
            hook_system_prompt_override = None

        # Determine final system prompt for this turn.
        # Priority: hook override > frozen session prompt > segment assembly.
        use_frozen_system_prompt = False
        pre_rendered_system_prompt: str | None = (
            None  # non-None → loop skips build_system_prompt
        )
        if hook_system_prompt_override:
            system_prompt_override: str | None = hook_system_prompt_override
        elif frozen_system_prompt:
            system_prompt_override = frozen_system_prompt
            use_frozen_system_prompt = True
        elif self._prompt_sections:
            # Segment-based assembly: freeze memory snapshot on first turn, build ctx,
            # then resolve effective prompt via assemble_system_prompt.
            snapshot = self._ensure_memory_snapshot(session_id, hook_metadata)
            active_tools_for_prompt = session_available_tools or ()
            flags = resolve_flags_from_metadata(metadata=hook_metadata)
            cwd_str = (
                str(session_workspace_root)
                if session_workspace_root
                else str(self._repo_root)
            )
            from agent.core.agent.prompt_sections.base import RenderMode  # noqa: PLC0415

            ctx = build_prompt_context_from_metadata(
                metadata=hook_metadata,
                available_tools=list(active_tools_for_prompt),
                available_skills=list(session_available_skills),
                current_datetime=session_created_at,
                cwd=cwd_str,
                memory_content=snapshot["memory_content"],
                memory_pct=snapshot["memory_pct"],
                user_profile_content=snapshot["user_profile_content"],
                user_pct=snapshot["user_pct"],
                agents_md_content=snapshot["agents_md_content"],
                render_mode=RenderMode.RUNTIME,
                flags=flags,
                vars={
                    "custom_prompt": str(hook_metadata.get("custom_prompt", "")),
                    # feat-394-M9: heartbeat/cron gates moved to ctx.flags via
                    # FEATURE_REGISTRY (decision D).  vars injection retired.
                },
                # refactor-406 决策 8: thread the consumer's per-session PromptSlots
                # so the kernel skeleton's slot sections render product text.
                prompt_slots=state.prompt_seed,
            )
            pre_rendered_system_prompt = resolve_effective_prompt(
                sections=self._prompt_sections,
                ctx=ctx,
                override=None,
            )
            system_prompt_override = None
        else:
            system_prompt_override = None

        await self._dispatch_observe(
            "agent_start",
            {"session_id": session_id, "turn_id": turn_id},
            hook_ctx,
        )

        turn_count = sum(1 for message in history if message.role == "user")
        if replay_last_user:
            assert last_user is not None
            user_msg = last_user
            loop_history = tuple(
                message
                for message in history
                if message.message_id != last_user.message_id
            )
        else:
            user_message_id = make_message_id()

            # bugfix-433 决策2/4: carry structured image blocks on the user turn so they
            # both reach the provider this turn and persist for cross-turn replay. None
            # for text-only turns keeps content:str and writes no `parts` (text golden).
            user_content_parts = render_user_content_parts(input_parts)
            user_msg = Message(
                message_id=user_message_id,
                parent_message_id=history[-1].message_id if history else None,
                role="user",
                content=user_text,
                parts=tuple(user_content_parts) if user_content_parts else None,
            )
            history.append(user_msg)
            state.transcript.append_messages(
                [user_msg],
                durable=True,
                turn_id=turn_id,
            )
            loop_history = tuple(history[:-1])
        preloop_messages: list[Message] = []
        if (
            slash_skill_command is not None
            and self._current_tool_registry() is not None
            and any(tool.name == "skill_view" for tool in session_available_tools)
        ):
            preloop_messages = await self._execute_slash_skill_view(
                command=slash_skill_command,
                session_id=session_id,
                turn_id=turn_id,
                hook_ctx=hook_ctx,
                parent_message_id=user_msg.message_id,
            )
            for preloop_msg in preloop_messages:
                history.append(preloop_msg)
                state.transcript.append_messages(
                    [preloop_msg],
                    durable=preloop_msg.role == "tool",
                    turn_id=turn_id,
                )
            if preloop_messages:
                await state.transcript.flush_async()

        # Remove the user message we just added from history passed to loop.
        if not replay_last_user:
            loop_history = tuple(history[:-1])
            if preloop_messages:
                loop_history = tuple(history[: -1 - len(preloop_messages)]) + tuple(
                    preloop_messages
                )

        # Multi-part expansion (M246)
        effective_user_text = user_text
        effective_input_parts = input_parts
        if len(input_parts) > 1:
            extra_parts = input_parts[:-1]
            last_part = input_parts[-1:]
            # bugfix-433 CRITICAL-1: an extra image part must carry structured parts so
            # build_chat_messages (history side) restores it as an image block. Rendering
            # it via render_user_text alone would emit "[image:placeholder]" and drop the
            # image — the reason multi-image turns lost all but the last image.
            # bugfix-433-fix1 #7: anchor extra parts to user_msg (the turn they belong to),
            # not to loop_history[-1] (the message BEFORE this turn) — otherwise the
            # parent chain is misordered. In-memory only (not persisted), low impact, but
            # keeps the logical tree correct.
            extra_messages = tuple(
                Message(
                    message_id=make_message_id(),
                    parent_message_id=user_msg.message_id,
                    role="user",
                    content=render_user_text([part]),
                    parts=tuple(blocks)
                    if (blocks := render_user_content_parts([part]))
                    else None,
                )
                for part in extra_parts
                if render_user_text([part]) or render_user_content_parts([part])
            )
            loop_history = loop_history + extra_messages
            # feat-430 fix-r2: input_parts were already skill-rewritten per-part above, so
            # last_part / extra_parts carry the rewritten command wherever it sits.
            effective_user_text = render_user_text(last_part)
            effective_input_parts = last_part

        all_messages: list[Message] = [user_msg, *preloop_messages]
        state.partial_messages = all_messages
        _overflow_retried = False
        _run_cancelled = False
        try:
            async for msg in self._execute_loop(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history=loop_history,
                input_parts=effective_input_parts,
                user_text=effective_user_text,
                user_message_id=user_msg.message_id,
                hook_ctx=hook_ctx,
                system_prompt_override=system_prompt_override,
                pre_rendered_system_prompt=pre_rendered_system_prompt,
                llm_session_id=llm_session_id,
                session_created_at=session_created_at,
                current_working_directory_override=session_workspace_root,
                workspace_root=session_workspace_root,
                available_skills_override=()
                if use_frozen_system_prompt
                else session_available_skills,
                available_tools_override=session_available_tools,
                controller=controller,
                model_override=model,
            ):
                if msg.role == "turn_meta":
                    all_messages.append(msg)
                    continue
                all_messages.append(msg)
                if msg.metadata.get("is_compact_summary"):
                    post_compact_messages = _post_compact_messages_from(msg)
                    history[:] = [msg, *post_compact_messages]
                    for post_compact_msg in post_compact_messages:
                        all_messages.append(post_compact_msg)
                    continue
                history.append(msg)
                state.transcript.append_messages(
                    [msg],
                    durable=msg.role == "tool",
                    turn_id=turn_id,
                )
            await state.transcript.flush_async()
            # bugfix-410-M2 R1: orphaned tool_call recovery moved to the run
            # `finally` below (see _recover_orphaned_tool_calls). The bugfix-402
            # eager-recovery that lived here keyed on turn_meta stop_reason, so a
            # raw CancelledError unwinding before any turn_meta was produced (the
            # gateway run-idle watchdog cancelling a parked tool/LLM await)
            # skipped it entirely, leaving an orphaned tool_call AND a dirty
            # cache → session bricked until restart (#82 reopen). The finally is
            # stop_reason-independent and covers every termination path.
        except asyncio.CancelledError:
            # Flag so finally writes the recovery under asyncio.shield (the I/O
            # would otherwise be re-cancelled). Re-raise to preserve cancel
            # semantics for the caller (gateway watchdog / interrupt).
            _run_cancelled = True
            raise
        except CompactionError:
            await self._emit_compaction_failure(
                session_id=session_id,
                turn_id=turn_id,
                parent_message_id=user_msg.message_id,
                hook_ctx=hook_ctx,
            )
            raise
        except ModelError as exc:
            await state.transcript.flush_async()
            # Attempt overflow recovery: compact then retry once.
            if (
                not _overflow_retried
                and _is_context_overflow_error(exc)
                and self._compaction_settings.enabled
            ):
                _overflow_retried = True
                try:
                    compact_result = await self._compact_session(
                        session_id=session_id,
                        reason=CompactionReason.OVERFLOW,
                        overflow_cause=exc,
                    )
                except CompactionError:
                    await self._emit_compaction_failure(
                        session_id=session_id,
                        turn_id=turn_id,
                        parent_message_id=user_msg.message_id,
                        hook_ctx=hook_ctx,
                    )
                    raise
                if compact_result is not None:
                    # Rebuild history from session store after compaction.
                    reloaded = state.transcript.load().messages
                    history.clear()
                    history.extend(reloaded)
                    # user_msg was written before the overflow; it's in the reloaded history.
                    # Rebuild loop_history excluding it, then re-run.
                    retry_history = tuple(
                        m for m in history if m.message_id != user_msg.message_id
                    )
                    all_messages = [user_msg]
                    state.partial_messages = all_messages
                    try:
                        async for msg in self._execute_loop(
                            session_id=session_id,
                            turn_id=turn_id,
                            turn_count=turn_count,
                            history=retry_history,
                            input_parts=effective_input_parts,
                            user_text=effective_user_text,
                            user_message_id=user_msg.message_id,
                            hook_ctx=hook_ctx,
                            system_prompt_override=system_prompt_override,
                            pre_rendered_system_prompt=pre_rendered_system_prompt,
                            llm_session_id=llm_session_id,
                            session_created_at=session_created_at,
                            current_working_directory_override=session_workspace_root,
                            workspace_root=session_workspace_root,
                            available_skills_override=()
                            if use_frozen_system_prompt
                            else session_available_skills,
                            available_tools_override=session_available_tools,
                            controller=controller,
                            model_override=model,
                        ):
                            if msg.role == "turn_meta":
                                all_messages.append(msg)
                                continue
                            all_messages.append(msg)
                            if msg.metadata.get("is_compact_summary"):
                                post_compact_messages = _post_compact_messages_from(msg)
                                history[:] = [msg, *post_compact_messages]
                                all_messages.extend(post_compact_messages)
                                continue
                            history.append(msg)
                            state.transcript.append_messages(
                                [msg],
                                durable=msg.role == "tool",
                                turn_id=turn_id,
                            )
                        await state.transcript.flush_async()
                    except CompactionError:
                        await self._emit_compaction_failure(
                            session_id=session_id,
                            turn_id=turn_id,
                            parent_message_id=user_msg.message_id,
                            hook_ctx=hook_ctx,
                        )
                        raise
                else:
                    raise
            else:
                # bugfix-380: synthesize a user-visible error assistant message before re-raising.
                # This surfaces the upstream error in IM/CLI without changing the existing
                # run_status=failed telemetry path (registry._mark_failed_async is triggered
                # by the re-raised ModelError as before).
                error_msg = _build_provider_error_message(
                    exc,
                    model=model or state.active_model,
                    parent_message_id=user_msg.message_id,
                )
                history.append(error_msg)
                state.transcript.append_messages(
                    [error_msg],
                    durable=True,
                    turn_id=turn_id,
                )
                # bugfix-380: run_id must be in message_end payload so realtime_stream hook
                # can publish assistant_message SSE before run_status=failed arrives.
                _error_run_id = hook_ctx.metadata.get("run_id") if hook_ctx else None
                message_end_payload: dict[str, Any] = {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "message_id": error_msg.message_id,
                    "content": error_msg.content,
                    "role": "assistant",
                }
                if isinstance(_error_run_id, str) and _error_run_id.strip():
                    message_end_payload["run_id"] = _error_run_id.strip()
                await self._dispatch_observe(
                    "message_end",
                    message_end_payload,
                    hook_ctx,
                )
                # bugfix-380 R3: dispatch turn_end(completed=False) AFTER message_end so
                # Gateway observer locks the bubble only after seeing the error content.
                # loop.py's finally skips turn_end on the failure path; runtime owns it here.
                turn_end_run_id = _error_run_id
                turn_end_payload: dict[str, Any] = {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "completed": False,
                }
                if isinstance(turn_end_run_id, str) and turn_end_run_id.strip():
                    turn_end_payload["run_id"] = turn_end_run_id.strip()
                await self._dispatch_observe("turn_end", turn_end_payload, hook_ctx)
                raise
        finally:
            # bugfix-429 fix-r1 #2: this run is done — stop publishing its model.
            if model:
                state.active_model = None
            # bugfix-410-M2 R1: close any orphaned tool_call on EVERY exit path
            # (normal completion = no-op empty orphan set; cooperative abort/
            # cancel; raw CancelledError pass-through; ModelError re-raise). Must
            # be stop_reason-independent — see _recover_orphaned_tool_calls.
            await self._recover_orphaned_tool_calls(
                session_id=session_id,
                all_messages=all_messages,
                workspace_root=session_workspace_root,
                parent_session_id=parent_session_id,
                cancelled=_run_cancelled,
                user_interrupt=controller is not None and controller.is_user_interrupt,
            )

        turn_result = build_turn_result(session_id, turn_id, all_messages)
        if turn_result.usage is not None and turn_result.usage.prompt_tokens > 0:
            state.last_prompt_tokens = turn_result.usage.prompt_tokens

        # Extract tool_iterations from turn_meta for nudge counter signal flow.
        # turn_meta is the last message in all_messages when present.
        tool_iterations = 0
        if all_messages:
            last_msg = all_messages[-1]
            if last_msg.role == "turn_meta":
                tool_iterations = int(last_msg.metadata.get("tool_iterations", 0))

        agent_end_payload = {
            "session_id": session_id,
            "turn_id": turn_id,
            "completed": turn_result.completed,
            "stop_reason": turn_result.stop_reason,
            # Expose the tool_iterations milestone for background hook nudge logic.
            "tool_iterations": tool_iterations,
            "turn_count": turn_count,
        }

        await self._dispatch_observe("agent_end", agent_end_payload, hook_ctx)

        # Dispatch background hooks with fork_conversation injected.
        # Background hooks (e.g. self-improvement) fire after main turn completes.
        # anti-recursion: fork_conversation is never available inside a fork side-chain
        # because the side-chain runs via AgentContextFork which has no hook_runner
        # with background registrations — but we also set fork_conversation=None when
        # building contexts for fork side-chains as an explicit belt-and-suspenders guard.
        hook_runner = self._current_hook_runner()
        if hook_runner is not None:
            background_registrations = hook_runner.registry.background_handlers_for(
                "agent_end"
            )
            if background_registrations:
                from agent.core.agent.context_fork import make_fork_conversation

                # Build fork_conversation using the current session's rendered state.
                # We resolve the fork tools and system prompt from the session config.
                fork_system_prompt: str | None = None
                fork_active_tools: tuple[ToolSpec, ...] = ()
                if state.config is not None:
                    fork_config = state.config
                    fork_active_skills = (
                        self._resolve_session_available_skills_from_config(fork_config)
                    )
                    fork_active_tools = (
                        self._resolve_session_available_tools_from_config(fork_config)
                    )
                    fork_system_prompt = build_system_prompt(
                        system_prompt=fork_config.system_prompt
                        or self._loop._system_prompt,
                        available_skills=fork_active_skills,
                        available_tools=fork_active_tools,
                        current_working_directory=fork_config.workspace_root,
                    )

                messages_snapshot = list(history)
                fork_fn = make_fork_conversation(
                    context_fork=self._context_fork,
                    rendered_system_prompt=fork_system_prompt or "",
                    active_tools=fork_active_tools,
                    messages_snapshot=messages_snapshot,
                    session_id=session_id,
                    tool_allowlist=(),  # caller (background hook) specifies allowlist
                    # Inherit the turn's execution context (model_caller /
                    # permission_requester) so hooks work inside the fork.
                    parent_hook_ctx=hook_ctx,
                    # bugfix-429 fix-r1 #2: background fork runs on this run's model.
                    model=model,
                )

                # replace() derives from the turn's hook_ctx, preserving every field
                # (model_caller / permission_requester / message_history) and only
                # attaching fork_conversation. The hand-listed rebuild had been
                # dropping permission_requester + message_history.
                background_hook_ctx = replace(hook_ctx, fork_conversation=fork_fn)
                hook_runner.dispatch_background(
                    "agent_end", agent_end_payload, background_hook_ctx
                )

        return turn_result

    def get_llm_config(self) -> LLMFactoryConfig:
        """Return active LLM configuration used by the runtime."""

        return self._llm_config

    def bind_tool_registry(self, tool_registry: ToolRegistryLike | None) -> None:
        """Bind or unbind runtime tool registry.

        Must propagate to _context_fork because in app.py the runtime is constructed
        before the registry is available (tool_registry=None at __init__ time).
        Without this, the fork side-chain runs with tool_registry=None and exits with
        stop_reason='tool_registry_unavailable' after the LLM returns a tool_use call.

        Also updates self._tool_registry so _build_hook_context can inject it into
        HookContext metadata for auto_mode_gate (bugfix-355 Anchor C / Issue #1).
        """
        self._tool_registry = tool_registry
        self._loop.bind_tool_registry(tool_registry)
        self._context_fork.bind_tool_registry(tool_registry)

    def enqueue_skill_batch_review(self, trigger: Any) -> bool:
        """Record one per-skill batch review enqueue request with per-skill dedupe."""

        self._ensure_skill_batch_review_state()
        queue_key = _skill_batch_review_key(trigger)
        if not queue_key:
            return False
        if (
            queue_key in self._skill_batch_review_queued
            or queue_key in self._skill_batch_review_running
        ):
            return False
        self._skill_batch_review_queued.add(queue_key)
        self._skill_batch_review_triggers[queue_key] = trigger
        scheduler = self._skill_batch_review_drain_scheduler
        if scheduler is not None:
            scheduler(trigger)
        return True

    def set_skill_batch_review_drain_scheduler(
        self, scheduler: Callable[[Any], None] | None
    ) -> None:
        """Install a product-owned callback fired after a new F4 enqueue."""

        self._skill_batch_review_drain_scheduler = scheduler

    def pop_queued_skill_batch_reviews(
        self, *, skill_root: Path | None = None
    ) -> tuple[Any, ...]:
        """Move queued skill batch reviews into running state and return triggers."""

        self._ensure_skill_batch_review_state()
        requested_root = _skill_batch_review_root_key(skill_root)
        triggers: list[Any] = []
        for queue_key in tuple(sorted(self._skill_batch_review_queued)):
            trigger = self._skill_batch_review_triggers.get(queue_key)
            if requested_root is not None and (
                trigger is None
                or _skill_batch_review_root_key(getattr(trigger, "skill_root", None))
                != requested_root
            ):
                continue
            self._skill_batch_review_queued.discard(queue_key)
            if trigger is None:
                continue
            self._skill_batch_review_running.add(queue_key)
            triggers.append(trigger)
        return tuple(triggers)

    def finish_skill_batch_review(self, trigger_or_skill_name: Any) -> None:
        """Release per-skill running state after a batch review finishes."""

        self._ensure_skill_batch_review_state()
        queue_key = _skill_batch_review_key(trigger_or_skill_name)
        if not queue_key and isinstance(trigger_or_skill_name, str):
            queue_key = trigger_or_skill_name
        if not queue_key:
            return
        self._skill_batch_review_running.discard(queue_key)
        self._skill_batch_review_triggers.pop(queue_key, None)

    def _ensure_skill_batch_review_state(self) -> None:
        if not hasattr(self, "_skill_batch_review_queued"):
            self._skill_batch_review_queued = set()
        if not hasattr(self, "_skill_batch_review_running"):
            self._skill_batch_review_running = set()
        if not hasattr(self, "_skill_batch_review_triggers"):
            self._skill_batch_review_triggers = {}
        if not hasattr(self, "_skill_batch_review_drain_scheduler"):
            self._skill_batch_review_drain_scheduler = None

    @property
    def hook_runner(self) -> HookRunner | None:
        """Expose active hook runner."""

        return self._current_hook_runner()

    def resolve_available_skills(
        self,
        workspace_root: Path,
        include_names: Sequence[str] | None = None,
    ) -> tuple[SkillMetadata, ...]:
        """Resolve skills for a workspace using the same roots as preview/list_skills.

        Uses make_skill_resolver (core→core same-layer call) so runtime skill
        resolution is always same-source as Kernel.list_skills / assemble_prompt_preview
        (bugfix-431 决策 3). Returns an empty tuple when workspace_config_dirname was
        not supplied at build time, matching the cleaned-up default_skill_search_roots
        behavior (决策 4).

        Args:
            workspace_root: Per-session workspace directory to search under.
            include_names: Optional filter — only return skills whose name is in this
                sequence. None means "return all discovered skills".

        Returns:
            Tuple of SkillMetadata for skills found on disk (non-existent skill names
            are silently omitted, mirroring preview behavior).
        """
        resolver = make_skill_resolver(
            workspace_root,
            self._workspace_config_dirname,
            self._skill_search_roots,
            self._workspace_skill_dirnames,
        )
        if resolver is None:
            return ()
        return resolve_available_skills(
            workspace_root=workspace_root,
            include_names=include_names,
            config_resolver=resolver,
        )

    @property
    def hook_registry(self) -> "HookRegistry | None":
        """Expose active hook registry when runner is configured."""

        hook_runner = self._current_hook_runner()
        if hook_runner is None:
            return None
        return hook_runner.registry

    def resolve_run_model(self, session_id: str | None) -> str | None:
        """Return the model registered for an active run's session, or ``None``.

        bugfix-443: the platform layer (the ``agent`` tool) reads this so a
        subagent it dispatches mid-run inherits the parent run's model — the same
        same conversation-owned scalar that hook/compaction side-chains read,
        keeping a single source of truth. Returns a bare value: ``None`` means no
        matching active conversation is registered; the
        degenerate fallback to the build-time default is handled once, in
        ``run`` (``model_override or self._model``), not duplicated here.
        """

        state = self._active_state.get()
        if state is None or session_id != state.ref.session_id:
            return None
        return state.active_model

    def resolve_active_enabled_tool_names(self, session_id: str) -> tuple[str, ...]:
        """Return the resolved tool names for a session's currently active run.

        feat-474: the ``agent`` tool needs its parent's already-resolved
        effective tool set (whether the parent's persisted ``tool_allowlist``
        is ``None`` — the product-default case) to build a child's explicit
        allowlist, without reaching into this engine's private
        ``_resolve_session_available_tools_from_config``. This mirrors the
        ``resolve_run_model`` pattern: only valid when called from within
        ``session_id``'s own active turn (i.e. by a tool it is currently
        executing), which is exactly when the ``agent`` tool calls it.

        Args:
            session_id: The session whose active turn is expected to be
                running right now (the caller's own session, not the child's).

        Returns:
            The resolved tool names for that active run, honoring its
            ``tool_allowlist`` (``None`` → product default set; explicit tuple,
            including empty, used as-is).

        Raises:
            RuntimeError: No conversation is active for ``session_id`` — this
                is a caller invariant violation (must be called from inside
                that session's own turn), not a normal "not found" outcome.
        """

        state = self._active_state.get()
        if state is None or session_id != state.ref.session_id:
            raise RuntimeError(
                "resolve_active_enabled_tool_names requires an active run for "
                f"session {session_id!r}"
            )
        tools = self._resolve_session_available_tools_from_config(state.config)
        return tuple(tool.name for tool in tools)

    async def _recover_orphaned_tool_calls(
        self,
        *,
        session_id: str,
        all_messages: list[Message],
        workspace_root: Path | None,
        parent_session_id: str | None,
        cancelled: bool,
        user_interrupt: bool = False,
    ) -> None:
        """Close any tool_call left open when a run ends (bugfix-410-M2 R1).

        Called unconditionally from the run ``finally`` — on a normally completed
        run the orphan set is empty (every tool_call has a matching tool result),
        so this is a no-op. When a run is interrupted (cooperative abort/cancel,
        or a raw ``CancelledError`` unwinding before any turn_meta), the orphan
        set is non-empty and each open call is closed so the next request the LLM
        sees is well-formed (most providers reject an unanswered tool_call).

        Recovery is one conversation-owned transaction: append the synthetic tool
        result, flush it durably, then refresh this conversation's scalar history
        from its transcript. During cancellation the transaction is shielded so a
        second cancellation cannot expose a durable orphan through stale live state.

        The recovery reason does not depend on turn_meta: a cooperative
        abort/cancel carries ``stop_reason`` we honour; a raw ``CancelledError``
        carries no turn_meta at all, so we synthesize ``interrupted``.
        """

        closed_calls: set[str] = {
            m.tool_call_id for m in all_messages if m.role == "tool" and m.tool_call_id
        }
        orphans: list[tuple[str, str | None]] = []
        for msg in all_messages:
            if msg.role != "assistant":
                continue
            for tc in msg.metadata.get("tool_calls") or ():
                cid = tc.get("call_id") or tc.get("id")
                if cid and cid not in closed_calls:
                    orphans.append((cid, tc.get("name")))
        if not orphans:
            return

        run_stop_reason = next(
            (
                m.metadata.get("stop_reason")
                for m in all_messages
                if m.role == "turn_meta"
            ),
            None,
        )
        if run_stop_reason in ("cancelled", "aborted"):
            # bugfix-410-fix-r1: both cooperative-cancel ("cancelled") and abort map to
            # "interrupted". The IM badge's REASON_LABEL_KEYS only renders
            # denied/timed_out/interrupted — emitting a bare "cancelled" would leave the
            # badge with no label. "interrupted" is the semantically-equivalent recovery
            # reason the frontend already understands.
            reason = "interrupted"
        else:
            # No turn_meta (raw CancelledError pass-through) or any other
            # non-cooperative termination → synthesize interrupted.
            reason = "interrupted"

        # bugfix-417-M5 (#114): decouple the recovery CONTENT from the badge reason.
        # An explicit user /stop / CLI Ctrl-C backfills the CC-identical
        # "[Request interrupted by user for tool use]" — the same content both the
        # model reads in the transcript (so it stops and waits, not retries/apologises)
        # and the user sees on the IM tool card. A system interrupt (watchdog reap /
        # crash) keeps the generic "[interrupted]" — never falsely attributing it to
        # the user. The badge stays "已中断" in both cases (reason unchanged).
        content = USER_INTERRUPT_RECOVERY_CONTENT if user_interrupt else None

        state = self._state()

        # Persist recovery before releasing the conversation operation permit.
        async def _write_recovery() -> None:
            for cid, name in orphans:
                state.transcript.append_tool_call_recovery(
                    tool_call_id=cid,
                    tool_name=name,
                    reason=reason,
                    content=content,
                )
            await state.transcript.flush_async()
            state.history[:] = state.transcript.load().messages

        if cancelled:
            try:
                await asyncio.shield(_write_recovery())
            except asyncio.CancelledError:
                # The shielded conversation transaction continues to durable flush
                # and refresh its scalar history before the operation permit drains.
                raise
        else:
            await _write_recovery()

    def _resolve_session_available_skills_from_config(
        self, config: SessionConfig
    ) -> tuple[SkillMetadata, ...]:
        if config.skills is None:
            return self._loop.available_skills
        if not config.skills:
            return ()
        # bugfix-431: use resolve_available_skills via self.resolve_available_skills so
        # runtime and preview both use the make_skill_resolver helper (决策 1/3).
        return self.resolve_available_skills(
            config.workspace_root,
            include_names=config.skills,
        )

    def _resolve_session_available_tools_from_config(
        self, config: SessionConfig
    ) -> tuple[ToolSpec, ...]:
        registry = self._current_tool_registry()
        if registry is None:
            all_specs = ()
        else:
            session_specs = getattr(registry, "list_specs_for_session", None)
            all_specs = (
                session_specs(config.metadata)
                if callable(session_specs)
                else registry.list_specs()
            )
        if config.tool_allowlist is None:
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(config.tool_allowlist)
        return tuple(tool for tool in all_specs if tool.name in requested)

    async def _dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> tuple[dict[str, Any], bool]:
        hook_runner = self._current_hook_runner()
        if hook_runner is None:
            return dict(payload), False
        try:
            dispatch_result = await hook_runner.dispatch_intercept(
                event,
                payload,
                hook_ctx,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warning(
                "hook intercept dispatch failed", event=event, error=str(exc)
            )
            return dict(payload), False
        log_hook_diagnostics(
            hook_ctx, event=event, diagnostics=dispatch_result.diagnostics
        )
        return dispatch_result.payload, dispatch_result.stopped

    async def _dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        hook_runner = self._current_hook_runner()
        if hook_runner is None:
            return
        try:
            diagnostics = await hook_runner.dispatch_observe(
                event,
                payload,
                hook_ctx,
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warning(
                "hook observe dispatch failed", event=event, error=str(exc)
            )
            return
        log_hook_diagnostics(hook_ctx, event=event, diagnostics=diagnostics)

    def _build_hook_context(
        self,
        *,
        session_id: str,
        turn_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        controller: RunController | None = None,
    ) -> HookContext:
        session_event_publisher = None
        scope = self._current_scope()
        hook_runner = self._current_hook_runner()
        if hook_runner is not None:
            session_event_publisher = _resolve_session_event_publisher(
                registry=hook_runner.registry,
                session_id=session_id,
            )
        if session_event_publisher is not None and controller is not None:
            unguarded_publisher = session_event_publisher

            def _run_guarded_publisher(event: str, data: Mapping[str, Any]) -> None:
                # Assistant content must be wholly before or after /stop. Keep
                # lifecycle/tool closure events unguarded so consumers can still
                # finalize in-flight UI after cancellation.
                if event != "assistant_message":
                    unguarded_publisher(event, data)
                    return
                controller.publish_if_active(lambda: unguarded_publisher(event, data))

            session_event_publisher = _run_guarded_publisher

        # Build permission_requester closure when broker is available.
        # The closure captures the broker and session_event_publisher so
        # auto_mode_gate can park (register future + emit SSE) without knowing
        # whether the product is CLI or PA — the publisher routes to the right channel.
        permission_requester = None
        broker = self._permission_broker
        resolved_metadata = dict(metadata or {})
        if broker is not None:
            run_id_for_broker = resolved_metadata.get(
                "workflow_run_id"
            ) or resolved_metadata.get("run_id")
            workflow_parent_session_id = resolved_metadata.get(
                "workflow_parent_session_id"
            )
            publisher_for_broker = session_event_publisher
            if (
                hook_runner is not None
                and isinstance(workflow_parent_session_id, str)
                and workflow_parent_session_id.strip()
            ):
                publisher_for_broker = _resolve_session_event_publisher(
                    registry=hook_runner.registry,
                    session_id=workflow_parent_session_id,
                )
            permission_correlation = {
                key: resolved_metadata[key]
                for key in (
                    "workflow_parent_session_id",
                    "workflow_run_id",
                    "agent_call_id",
                )
                if resolved_metadata.get(key) is not None
            }

            can_use_tool = self._can_use_tool

            async def _permission_requester(req: Any) -> Any:
                # Register the future before emitting the SSE event so the
                # inbound endpoint can immediately resolve it if it arrives fast.
                future = broker.register_request(req.id, run_id=run_id_for_broker)
                if publisher_for_broker is not None:
                    # Emit 'permission_request' SSE event — PA inbound_pipeline
                    # already listens for this event name (see personal_assistant/main.py).
                    publisher_for_broker(
                        "permission_request",
                        {
                            "run_id": run_id_for_broker,
                            "request_id": req.id,
                            "tool_name": req.tool_name,
                            "tool_input": dict(req.tool_input)
                            if hasattr(req, "tool_input")
                            else {},
                            "question": req.question
                            if hasattr(req, "question")
                            else "",
                            "options": [
                                {
                                    "id": o.id,
                                    "label": o.label,
                                    "description": o.description,
                                }
                                for o in (
                                    req.options if hasattr(req, "options") else ()
                                )
                            ],
                            **permission_correlation,
                        },
                    )
                response: Any = None
                # bugfix-417-M3 R3: parking on a human permission decision is the third
                # alive-but-quiet window — it can legitimately last minutes with no
                # business event. Run an await-bound liveness ticker so both watchdogs see
                # periodic run_heartbeat (same event type as tool/LLM liveness) and never
                # reap a run that is merely waiting for the user (decision 4). The ticker
                # is torn down in the finally below, so a post-decision stall — or a
                # Gateway/kernel crash that stops the heartbeat — is still reaped normally.
                _perm_publish = _broker_publish_adapter(publisher_for_broker)
                # Only spawn the ticker when it can actually emit (publisher + run_id
                # present). Without this guard a CLI run (no event hub → publish None /
                # run_id None) would build a heartbeat task that just parks forever —
                # mirrors liveness_ticker's no-op-when-missing contract (bugfix-417-M4
                # fix-r1 cleanup) without re-indenting this whole permission-wait block.
                _perm_heartbeat: asyncio.Task[None] | None = (
                    asyncio.create_task(
                        _emit_liveness_heartbeats(
                            publish=_perm_publish,
                            run_id=run_id_for_broker,
                            source="permission",
                        )
                    )
                    if _perm_publish is not None and run_id_for_broker
                    else None
                )
                try:
                    if can_use_tool is not None and not permission_correlation:
                        # Race can_use_tool callback against broker future.
                        # CLI products supply can_use_tool for interactive prompts;
                        # PA leaves it None and resolves via submit_permission_decision.
                        # Workflow children publish tagged requests to the parent
                        # session's long-lived consumer, which must be the sole prompt
                        # owner so the process callback cannot display a duplicate.
                        can_use_task: asyncio.Task[Any] = asyncio.create_task(
                            can_use_tool(
                                req.tool_name, getattr(req, "tool_input", {}), req
                            )
                        )

                        async def _await_future(f: "asyncio.Future[Any]") -> Any:
                            return await asyncio.shield(f)

                        try:
                            done, pending = await asyncio.wait(
                                {
                                    can_use_task,
                                    asyncio.ensure_future(_await_future(future)),
                                },
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                        except asyncio.CancelledError:
                            # Outer coroutine cancelled — clean up can_use_task to
                            # prevent task leak (feat-394-M14 finding 2).
                            can_use_task.cancel()
                            await asyncio.gather(can_use_task, return_exceptions=True)
                            raise

                        for t in pending:
                            t.cancel()
                        # Drain cancelled losers so they don't generate unhandled
                        # exceptions after this coroutine exits.
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)

                        if future.done() and not future.cancelled():
                            # Broker future resolved first (interrupt/external decision).
                            response = future.result()
                        else:
                            # can_use_tool returned first — map decision to response.
                            # Build a minimal duck-typed response: architecture boundary
                            # forbids core from importing platform types (see contract
                            # test_core_no_platform_imports); broker only reads
                            # .decision / .reason / .request_id.
                            try:
                                raw_decision: Any = can_use_task.result()
                            except asyncio.CancelledError:
                                # can_use_task was cancelled (e.g. run interrupt raced
                                # asyncio.wait before broker future resolved).
                                # CancelledError is BaseException, not Exception — must
                                # be caught explicitly (feat-394-M14 finding 2b).
                                # Treat as deny; re-raise is NOT needed here because we
                                # already cleaned up pending in the except block above.
                                raw_decision = type(
                                    "_D",
                                    (),
                                    {
                                        "behavior": "deny",
                                        "reason": "can_use_tool cancelled",
                                    },
                                )()
                            except Exception:
                                raw_decision = type(
                                    "_D",
                                    (),
                                    {
                                        "behavior": "deny",
                                        "reason": "can_use_tool raised",
                                    },
                                )()
                            explicit_decision = getattr(raw_decision, "decision", None)
                            behavior = getattr(raw_decision, "behavior", "deny")
                            reason = getattr(raw_decision, "reason", "")
                            allowed_decisions = {
                                "allow_once",
                                "allow_session",
                                "allow_always",
                                "deny",
                            }
                            if explicit_decision in allowed_decisions:
                                broker_decision = explicit_decision
                            elif behavior in allowed_decisions:
                                broker_decision = behavior
                            else:
                                broker_decision = (
                                    "deny" if behavior == "deny" else "allow_once"
                                )
                            response = type(
                                "_R",
                                (),
                                {
                                    "decision": broker_decision,
                                    "reason": reason,
                                    "request_id": req.id,
                                    "rule_update": None,
                                },
                            )()
                            # "Whoever pops owns it" — same semantic as
                            # cancel_all_pending.  If cancel_all_pending already
                            # popped and scheduled deny via call_soon_threadsafe,
                            # owned is None here and we skip set_result entirely,
                            # closing the double-set_result → InvalidStateError
                            # window (feat-394-M14 findings 1 + 3 + last).
                            with broker._lock:  # noqa: SLF001
                                owned = broker._pending.pop(req.id, None)  # noqa: SLF001
                            if owned is not None and not future.done():
                                future.get_loop().call_soon_threadsafe(
                                    future.set_result, response
                                )
                    else:
                        response = await future
                except asyncio.CancelledError:
                    response = type(
                        "_R",
                        (),
                        {
                            "decision": "deny",
                            "reason": "cancelled: run interrupted or timed out",
                            "request_id": req.id,
                            "rule_update": None,
                        },
                    )()
                    with broker._lock:  # noqa: SLF001
                        owned = broker._pending.pop(req.id, None)  # noqa: SLF001
                    if owned is not None and not future.done():
                        future.get_loop().call_soon_threadsafe(
                            future.set_result, response
                        )
                    raise
                finally:
                    # bugfix-417-M3 R3: stop the liveness ticker the instant the wait
                    # ends (resolve / deny / cancel), so the heartbeat proves only the
                    # active wait — never "the Task still exists" past the decision.
                    if _perm_heartbeat is not None:
                        _perm_heartbeat.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await _perm_heartbeat
                    # Emit 'permission_resolved' SSE event so IM card updates to
                    # resolved state.  Use the local `response` variable rather than
                    # re-reading future.done(): call_soon_threadsafe is asynchronous,
                    # so future.done() may still be False at this point even when we
                    # just scheduled a set_result (feat-394-M14 finding 1).
                    if publisher_for_broker is not None and response is not None:
                        try:
                            publisher_for_broker(
                                "permission_resolved",
                                {
                                    "run_id": run_id_for_broker,
                                    "request_id": req.id,
                                    "decision": getattr(response, "decision", "deny"),
                                    **permission_correlation,
                                },
                            )
                        except Exception as exc:
                            # Delivery failure must not abort the permission flow; log so
                            # the drop is observable (refactor-395-M1).
                            logger.warning(
                                "permission_resolved event delivery failed: %s", exc
                            )
                return response

            permission_requester = _permission_requester
            # Also inject broker into metadata so auto_mode_gate can access deny-count
            # and session-allowlist state (the hook reads metadata['permission_broker']).
            resolved_metadata["permission_broker"] = broker

        # Inject tool_registry into metadata so auto_mode_gate.on_tool_call can call
        # tool.check_permissions (bugfix-355 Anchor C / Issue #1).
        # Without this injection metadata.get("tool_registry") is always None, making
        # the bypass-immune safety_check chain (W1) and WebFetch preapproved logic (S1)
        # silently inactive even though tool.check_permissions is correctly implemented.
        registry = self._current_tool_registry()
        if registry is not None:
            resolved_metadata["tool_registry"] = registry

        final_metadata: Mapping[str, Any] = (
            scope.metadata(resolved_metadata)
            if scope is not None
            else resolved_metadata
        )

        return HookContext(
            session_id=session_id,
            turn_id=turn_id,
            repo_root=(
                scope.layout.workspace_root if scope is not None else self._repo_root
            ),
            metadata=final_metadata,
            model_caller=self._call_hook_model,
            session_event_publisher=session_event_publisher,
            permission_requester=permission_requester,
            subagent_control=self._state().subagent_control,
        )

    def _client_for_model(self, model: str) -> LLMClient:
        """Select the LLM client for ``model``'s provider (bugfix-429 fix-r1 #2).

        Mirrors AgentLoop._client_for_model so side-chain calls (hook model_caller)
        route by the model's registered provider. Without a per-provider map
        (unit-test single-client path), the lone client serves every model.
        """
        if not self._llm_clients:
            return self._llm_client
        provider = provider_of(model)
        client = self._llm_clients.get(provider)
        if client is None:
            raise ValueError(
                f"no llm client configured for provider {provider!r} (model {model!r})"
            )
        return client

    async def _call_hook_model(self, call: HookModelCall) -> HookModelResult:
        """Execute one hook-initiated model call under runtime configuration."""

        normalized_session = call.session_id.strip()
        if not normalized_session:
            raise ValueError("session_id is required")
        # bugfix-429 fix-r1 #2: explicit call.model wins; else follow the current
        # run's per-agent model; else the build-time default. Route to that model's
        # provider client (not always the default-provider client).
        model = (
            call.model
            or self.resolve_run_model(normalized_session)
            or self._llm_config.model
        ).strip()
        if not model:
            raise ValueError("model is required")

        stream = self._client_for_model(model).generate(
            LLMGenerateRequest(
                session_id=normalized_session,
                model=model,
                messages=(
                    LLMMessage(role="system", content=call.system_prompt),
                    LLMMessage(role="user", content=call.user_prompt),
                ),
                temperature=call.temperature,
                max_tokens=call.max_tokens,
                stop_sequences=call.stop_sequences,
                metadata=dict(call.metadata),
                extra_body=dict(call.extra_body)
                if call.extra_body is not None
                else None,
            )
        )

        content_parts: list[str] = []
        raw: dict[str, Any] = {}
        finish_reason: str | None = None
        usage = None
        async for msg in stream:
            if msg.finish_reason is not None:
                finish_reason = msg.finish_reason
                usage = msg.usage
                raw["finish_reason"] = finish_reason
                if usage is not None:
                    raw["usage"] = {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                continue
            if isinstance(msg.content, str):
                content_parts.append(msg.content)
            raw["role"] = msg.role

        content = "".join(content_parts)
        return HookModelResult(
            model=model,
            content=content,
            raw=raw,
        )

    async def _execute_slash_skill_view(
        self,
        *,
        command: SkillCommand,
        session_id: str,
        turn_id: str,
        hook_ctx: HookContext,
        parent_message_id: str,
    ) -> list[Message]:
        """Execute `/skill:<name>` through the normal `skill_view` tool pipeline."""

        registry = self._current_tool_registry()
        if registry is None or registry.get("skill_view") is None:
            return []
        call_id = make_tool_call_id()
        args = {"name": command.name}
        assistant_msg = Message(
            message_id=make_message_id(),
            parent_message_id=parent_message_id,
            role="assistant",
            content="",
            metadata={
                "tool_calls": [
                    {
                        "call_id": call_id,
                        "name": "skill_view",
                        "arguments": args,
                    }
                ]
            },
        )
        tool_hook_ctx = replace(
            hook_ctx,
            metadata={**dict(hook_ctx.metadata), "tool_call_id": call_id},
        )
        run_id = hook_ctx.metadata.get("run_id")
        tool_call_payload: dict[str, Any] = {
            "session_id": session_id,
            "turn_id": turn_id,
            "call_id": call_id,
            "name": "skill_view",
            "arguments": args,
        }
        if isinstance(run_id, str) and run_id.strip():
            tool_call_payload["run_id"] = run_id.strip()
        await self._dispatch_observe("tool_call", tool_call_payload, tool_hook_ctx)
        output: Mapping[str, Any] | None = None
        error: str | None = None
        try:
            output = await registry.execute(
                "skill_view",
                args,
                hook_context=tool_hook_ctx,
                session_file_state=self._state().file_state,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        tool_result_payload: dict[str, Any] = {
            "session_id": session_id,
            "turn_id": turn_id,
            "call_id": call_id,
            "name": "skill_view",
            "arguments": args,
            "output": output,
            "error": error,
            "duration_ms": 0,
        }
        if isinstance(run_id, str) and run_id.strip():
            tool_result_payload["run_id"] = run_id.strip()
        await self._dispatch_observe("tool_result", tool_result_payload, tool_hook_ctx)
        tool = registry.get("skill_view")
        if tool is not None and hasattr(tool, "serialize_result"):
            content = tool.serialize_result(output or {}, error=error)
        elif error is not None:
            content = error
        else:
            content = json.dumps(output or {}, ensure_ascii=False)
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        tool_msg = Message(
            message_id=make_message_id(),
            parent_message_id=assistant_msg.message_id,
            role="tool",
            content=content,
            tool_call_id=call_id,
            metadata={
                "tool_name": "skill_view",
                "tool_call_id": call_id,
                "tool_output": output,
                "tool_error": error,
            },
        )
        return [assistant_msg, tool_msg]

    async def _execute_loop(
        self,
        *,
        session_id: str,
        turn_id: str,
        turn_count: int,
        history: tuple[Message, ...],
        input_parts: Sequence[InputPart],
        user_text: str,
        user_message_id: str | None,
        hook_ctx: HookContext,
        system_prompt_override: str | None,
        pre_rendered_system_prompt: str | None = None,
        available_skills_override: tuple[SkillMetadata, ...] | None,
        available_tools_override: tuple[ToolSpec, ...] | None,
        llm_session_id: str | None,
        session_created_at: str,
        current_working_directory_override: Path | None,
        workspace_root: Path | None = None,
        controller: RunController | None = None,
        model_override: str | None = None,
    ):
        session_file_state = self._state().file_state
        # bugfix-468-M2: when the session has an explicit tool_allowlist (including
        # the empty tuple), narrow execution to the resolved available tools.
        # None keeps the legacy unrestricted path for CLI / kernel defaults.
        config = self._state().config
        runtime_payload = config.metadata.get(INTERNAL_RUNTIME_KEY)
        reasoning_effort = (
            runtime_payload.get("reasoning_effort")
            if isinstance(runtime_payload, Mapping)
            and isinstance(runtime_payload.get("reasoning_effort"), str)
            else None
        )
        if config.tool_allowlist is not None:
            tool_execution_allowlist = tuple(
                tool.name for tool in (available_tools_override or ())
            )
        else:
            tool_execution_allowlist = None
        async for msg in self._loop.run(
            AgentState(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history_messages=history,
                input_parts=input_parts,
                user_text=user_text,
                user_message_id=user_message_id,
            ),
            controller=controller,
            hook_ctx=hook_ctx,
            system_prompt_override=system_prompt_override,
            pre_rendered_system_prompt=pre_rendered_system_prompt,
            available_skills_override=available_skills_override,
            available_tools_override=available_tools_override,
            llm_session_id=llm_session_id,
            session_created_at=session_created_at,
            current_working_directory_override=current_working_directory_override,
            workspace_root=workspace_root,
            session_file_state=session_file_state,
            tool_execution_allowlist=tool_execution_allowlist,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
            prior_prompt_tokens=self._state().last_prompt_tokens,
            on_progress=self._record_turn_progress,
        ):
            yield msg

    def _record_turn_progress(
        self, usage: TokenUsage | None, tool_calls: tuple[ToolCall, ...]
    ) -> None:
        state = self._state()
        state.partial_usage = usage
        state.partial_tool_calls = tool_calls

    def _ensure_memory_snapshot(
        self,
        session_id: str,
        metadata: Mapping[str, Any],
    ) -> MemorySnapshot:
        """Lazy freeze of memory/user content for one session.

        Returns cached snapshot on hit; renders + caches on first call per session.
        Freezing on first turn keeps the stable prefix byte-identical across turns
        so provider prefix-cache hits are maximised.  Compaction invalidates the
        cache via _invalidate_memory_snapshot so the next turn reflects updated memory.
        """
        conversation = self._state()
        if conversation.memory_snapshot is not None:
            return conversation.memory_snapshot

        # feat-428 机制 A: workspace-root AGENTS.md is read here regardless of the
        # memory_curation flag or workspace_config_dirname — it depends only on
        # workspace_root, and 机制 A is the non-optional baseline (decision 5/spec).
        # Reading its root path into loaded_agents_md preseeds 机制 B's dedup set
        # (decision 4): the same SessionFileState instance read.py will use.
        agents_md_content = self._read_workspace_agents_md(session_id, metadata)

        flags = resolve_flags_from_metadata(metadata=metadata)
        if not flags.get("memory_curation", True):
            snapshot: MemorySnapshot = {
                "memory_content": None,
                "memory_pct": 0,
                "user_profile_content": None,
                "user_pct": 0,
                "agents_md_content": agents_md_content,
            }
            conversation.memory_snapshot = snapshot
            return snapshot

        workspace_root_raw = metadata.get("workspace_root")
        dirname = metadata.get("workspace_config_dirname")
        if not workspace_root_raw or not dirname:
            snapshot = {
                "memory_content": None,
                "memory_pct": 0,
                "user_profile_content": None,
                "user_pct": 0,
                "agents_md_content": agents_md_content,
            }
            conversation.memory_snapshot = snapshot
            return snapshot

        memory_root = derive_memory_root(Path(str(workspace_root_raw)), str(dirname))
        store = MemoryStore(memory_root=memory_root)
        memory_content = store.format_for_prompt("memory")
        memory_pct = store.format_pct_for_prompt("memory") if memory_content else 0
        user_content = store.format_for_prompt("user")
        user_pct = store.format_pct_for_prompt("user") if user_content else 0
        snapshot = {
            "memory_content": memory_content or None,
            "memory_pct": memory_pct,
            "user_profile_content": user_content or None,
            "user_pct": user_pct,
            "agents_md_content": agents_md_content,
        }
        conversation.memory_snapshot = snapshot
        return snapshot

    def _read_workspace_agents_md(
        self,
        session_id: str,
        metadata: Mapping[str, Any],
    ) -> str | None:
        """Read workspace-root AGENTS.md (@import expanded) and preseed dedup set.

        feat-428 机制 A: returns the expanded AGENTS.md text for the session's
        workspace root, or None when there is no workspace_root or no AGENTS.md.
        On success the root file's absolute path is preseeded into the session's
        SessionFileState.loaded_agents_md so 机制 B (read.py) skips re-injecting
        the same root (decision 4). Uses the same SessionFileState instance the
        run loop later reuses via setdefault on the same session_id.
        """
        workspace_root_raw = metadata.get("workspace_root")
        if not workspace_root_raw:
            return None
        root_md = (
            Path(str(workspace_root_raw)).expanduser()
            / agents_md_loader.AGENTS_MD_FILENAME
        )
        content = agents_md_loader.load_agents_md(root_md)
        if content is None:
            return None
        self._state().file_state.loaded_agents_md.add(str(root_md.resolve()))
        return content

    def _invalidate_memory_snapshot(self, session_id: str) -> None:
        """Reset prompt and file-window state after a durable compaction.

        The summary has already captured the old window. Replacing the complete
        SessionFileState makes threshold, overflow, and manual compaction share
        one refresh boundary: AGENTS.md, memory, and read-window dedup are rebuilt
        on the next turn rather than leaking state from the compacted prefix.
        """
        state = self._state()
        state.memory_snapshot = None
        state.file_state = SessionFileState()

    def _commit_threshold_compaction(
        self,
        summary: Message,
        reinjections: tuple[Message, ...],
        reason: str,
        restored_files: tuple[str, ...],
        expected_external_epoch: int,
    ) -> bool:
        """Commit a loop-produced summary only while its capture is current."""

        return self._state().transcript.append_compaction(
            summary=summary,
            reinjections=reinjections,
            reason=reason,
            restored_files=restored_files,
            expected_external_epoch=expected_external_epoch,
        )

    async def _emit_compaction_failure(
        self,
        *,
        session_id: str,
        turn_id: str,
        parent_message_id: str,
        hook_ctx: HookContext,
    ) -> None:
        """Publish the safe user notice before the run reaches failed terminal."""

        message = _build_compaction_error_message(parent_message_id=parent_message_id)
        run_id = hook_ctx.metadata.get("run_id")
        message_payload: dict[str, Any] = {
            "session_id": session_id,
            "turn_id": turn_id,
            "message_id": message.message_id,
            "content": message.content,
            "role": "assistant",
        }
        turn_end_payload: dict[str, Any] = {
            "session_id": session_id,
            "turn_id": turn_id,
            "completed": False,
        }
        if isinstance(run_id, str) and run_id.strip():
            message_payload["run_id"] = run_id.strip()
            turn_end_payload["run_id"] = run_id.strip()
        await self._dispatch_observe("message_end", message_payload, hook_ctx)
        await self._dispatch_observe("turn_end", turn_end_payload, hook_ctx)

    async def _compact_session(
        self,
        *,
        session_id: str,
        reason: CompactionReason,
        focus: str | None = None,
        idempotency_key: str | None = None,
        overflow_cause: ModelError | None = None,
    ) -> CompactionResult | None:
        # Compaction always runs on a session that has been loaded by a prior
        # run(), so its config (and thus workspace_root) is cached here.
        conversation = self._state()
        failure_tracker = conversation.automatic_compaction_failures
        if reason is CompactionReason.MANUAL and idempotency_key:
            prior = conversation.transcript.find_manual_compaction(idempotency_key)
            if prior is not None:
                return CompactionResult(
                    reason=CompactionReason.MANUAL,
                    entry_id=str(prior["entry_id"]),
                    first_kept_event_id=str(prior["first_kept_event_id"]),
                    summary=str(prior["summary"]),
                    dropped_event_ids=tuple(prior["dropped_event_ids"]),
                    kept_event_ids=tuple(prior["kept_event_ids"]),
                )
        captured_external_epoch = conversation.transcript.external_epoch
        config = conversation.config
        compaction_workspace_root = config.workspace_root
        entries = conversation.transcript.list_event_entries()
        plan = self._compaction_planner.plan(events=entries, reason=reason)
        if plan is None:
            return None

        rendered_system_prompt: str | None = None
        if config is not None:
            active_skills = self._resolve_session_available_skills_from_config(config)
            active_tools = self._resolve_session_available_tools_from_config(config)
            rendered_system_prompt = build_system_prompt(
                system_prompt=config.system_prompt or self._loop._system_prompt,
                available_skills=active_skills,
                available_tools=active_tools,
                current_working_directory=config.workspace_root,
            )

        dropped_messages = tuple(
            message_from_turn_entry(entry) for entry in plan.dropped_events
        )
        summary_kwargs: dict[str, Any] = {
            "session_id": session_id,
            "system_prompt": rendered_system_prompt,
            "dropped_messages": dropped_messages,
            "model_override": self.resolve_run_model(session_id),
            "hook_ctx": self._build_hook_context(session_id=session_id),
        }
        if reason is CompactionReason.MANUAL:
            summary_kwargs["focus"] = focus
        if reason is CompactionReason.OVERFLOW and failure_tracker.exhausted:
            raise CompactionError(
                trigger=reason.value,
                failure_kind="summary",
                consecutive_failures=failure_tracker.consecutive_failures,
                overflow_cause=overflow_cause,
            )
        summary = await self._compaction_summarizer.summarize(
            **summary_kwargs,
        )
        if summary is None:
            consecutive_failures = (
                failure_tracker.record_summary_failure()
                if reason is CompactionReason.OVERFLOW
                else failure_tracker.consecutive_failures
            )
            raise CompactionError(
                trigger=reason.value,
                failure_kind="summary",
                consecutive_failures=consecutive_failures,
                overflow_cause=overflow_cause,
            )

        # Post-compact file restore: read up to 5 most recently accessed files.
        file_state = conversation.file_state
        restored_files: list[str] = []
        if file_state is not None:
            for state in reversed(file_state._states.values()):
                content = read_file_slice(
                    file_path=state.file_path,
                    offset=state.offset,
                    limit=state.limit,
                )
                if content is not None:
                    lines_str = (
                        f"lines {state.offset}-{state.offset + state.limit - 1}"
                        if state.offset is not None and state.limit is not None
                        else "full file"
                    )
                    restored_files.append(
                        f"[Post-compact file restore] {state.file_path} ({lines_str}):\n{content}"
                    )
                if len(restored_files) >= 5:
                    break

        # Generate the summary message up front so its id is the single source of
        # truth for both the on-disk compact_boundary and the observed result
        # entry_id (bugfix-437 decision 2: no drift between write and observe).
        last_preserved_id = None
        history = conversation.history
        if history:
            last_preserved_id = history[-1].message_id

        summary_msg = Message(
            message_id=make_message_id(),
            parent_message_id=last_preserved_id,
            role="user",
            content=summary,
            metadata={"is_compact_summary": True, "is_meta": True},
        )
        reinjection_msg = self._build_skill_reinjection_message(
            session_id,
            compaction_workspace_root,
            summary_msg.message_id,
        )
        compacted_messages = (
            [summary_msg, reinjection_msg]
            if reinjection_msg is not None
            else [summary_msg]
        )

        # Write compact_boundary + summary directly via JSONL writer and reset the
        # in-process history cache. This is the SINGLE persistence path for
        # compaction (bugfix-437 decision 2): the redundant apply()->append_compaction
        # second write is removed. The memory reset is load-bearing — the next run's
        # conversation state is the cache-first source, so replace it only after
        # the boundary and summary are durably committed.
        result = self._compaction_applier.apply(
            plan=plan,
            summary=summary,
            summary_uuid=summary_msg.message_id,
        )
        try:
            committed = conversation.transcript.append_compaction(
                summary=summary_msg,
                reinjections=(reinjection_msg,) if reinjection_msg is not None else (),
                reason=reason.value,
                restored_files=restored_files,
                expected_external_epoch=captured_external_epoch,
                manual_idempotency_key=(
                    idempotency_key if reason is CompactionReason.MANUAL else None
                ),
                result_data={
                    "first_kept_event_id": result.first_kept_event_id,
                    "dropped_event_ids": list(result.dropped_event_ids),
                    "kept_event_ids": list(result.kept_event_ids),
                },
            )
        except Exception as exc:
            raise CompactionError(
                trigger=reason.value,
                failure_kind="persistence",
                consecutive_failures=failure_tracker.consecutive_failures,
                cause=exc,
                overflow_cause=overflow_cause,
            ) from exc
        if not committed:
            if reason is CompactionReason.MANUAL:
                raise CompactionError(
                    trigger=reason.value,
                    failure_kind="stale",
                    consecutive_failures=failure_tracker.consecutive_failures,
                )
            return None
        conversation.history[:] = compacted_messages
        conversation.last_prompt_tokens = None
        failure_tracker.reset()
        self._invalidate_memory_snapshot(session_id)

        # Build the result object from the already-persisted direct write (no
        # second persistence): entry_id aligns with the on-disk summary_uuid.
        await self._dispatch_observe(
            "session_compact",
            {
                "session_id": session_id,
                "reason": reason.value,
                "entry_id": result.entry_id,
                "first_kept_event_id": result.first_kept_event_id,
                "dropped_event_ids": result.dropped_event_ids,
                "kept_event_ids": result.kept_event_ids,
            },
            self._build_hook_context(session_id=session_id),
        )
        return result

    def _build_skill_reinjection_message(
        self,
        session_id: str,
        workspace_root: Path | None,
        compact_entry_id: str,
    ) -> Message | None:
        """Build the post-compaction skill reminder for viewed skills."""

        payload = self._build_skill_reinjection_payload(
            session_id=session_id,
            workspace_root=workspace_root,
        )
        if payload is None:
            return None
        content, refs = payload
        return Message(
            message_id=make_message_id(),
            role="user",
            content=content,
            parent_message_id=compact_entry_id,
            metadata={
                "is_meta": True,
                "is_skill_reinjection": True,
                "skill_reinjection_refs": refs,
                "compact_entry_id": compact_entry_id,
            },
        )

    def _build_skill_reinjection_payload(
        self,
        *,
        session_id: str,
        workspace_root: Path | None,
    ) -> tuple[str, list[dict[str, str]]] | None:
        roots = self._skill_roots_for_workspace(workspace_root=workspace_root)
        refs = skill_refs_for_session(skill_roots=roots, session_id=session_id)
        blocks: list[str] = []
        metadata_refs: list[dict[str, str]] = []
        for ref in refs:
            content = _read_skill_ref(ref)
            if content is None:
                continue
            metadata_refs.append(
                {
                    "name": ref.name,
                    "location": str(ref.location),
                    "root_id": ref.root_id,
                }
            )
            blocks.append(f"Skill: {ref.name}\nLocation: {ref.location}\n\n{content}")
        if not blocks:
            return None
        reminder = (
            "<system-reminder>\n"
            "The following skill content was reloaded from the current SKILL.md files "
            "after compaction. Use it as refreshed context for skills already viewed "
            "in this session.\n\n" + "\n\n---\n\n".join(blocks) + "\n</system-reminder>"
        )
        return reminder, metadata_refs

    def _skill_roots_for_workspace(
        self, *, workspace_root: Path | None
    ) -> tuple[Path, ...]:
        effective_root = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root is not None
            else self._repo_root
        )
        return build_skill_search_roots(
            workspace_root=effective_root,
            workspace_config_dirname=self._workspace_config_dirname,
            workspace_skill_dirnames=self._workspace_skill_dirnames,
            shared_skill_roots=self._skill_search_roots,
        )

    def _history_without_message(
        self,
        *,
        session_id: str,
        message_id: str,
    ) -> tuple[Message, ...]:
        history = self._state().history
        messages = list(history)
        if messages and messages[-1].message_id == message_id:
            messages.pop()
        return tuple(messages)


_SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY = "session_event_publisher_factory"


def _resolve_session_event_publisher(*, registry: "HookRegistry", session_id: str):
    factory = registry.get_extension_state(_SESSION_EVENT_PUBLISHER_FACTORY_STATE_KEY)
    if not callable(factory):
        return None
    publisher = factory(session_id)
    if not callable(publisher):
        return None
    return publisher


def _serialize_input_parts(parts: Sequence[InputPart]) -> tuple[dict[str, Any], ...]:
    serialized: list[dict[str, Any]] = []
    for part in parts:
        payload: dict[str, Any] = {"type": part.type}
        if part.text is not None:
            payload["text"] = part.text
        if part.image_url is not None:
            payload["image_url"] = part.image_url
        if part.mime_type is not None:
            payload["mime_type"] = part.mime_type
        payload.update(part.metadata)
        serialized.append(payload)
    return tuple(serialized)


def _extract_input_images(parts: Sequence[InputPart]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for part in parts:
        if part.type != "image":
            continue
        payload: dict[str, Any] = {}
        if part.image_url is not None:
            payload["image_url"] = part.image_url
        if part.mime_type is not None:
            payload["mime_type"] = part.mime_type
        payload.update(part.metadata)
        images.append(payload)
    return images


def _estimate_context_tokens(*, history: Sequence[Message]) -> int:
    total = 0
    for message in history:
        total += _estimate_text_tokens(message.content)
    total += 4 + len(history) * 2
    return total


def _estimate_text_tokens(text: str) -> int:
    normalized = " ".join(text.split())
    if not normalized:
        return 1
    return max(1, (len(normalized) + 7) // 8)


def _is_context_overflow_error(error: ModelError) -> bool:
    status_code = error.details.get("status_code")
    if isinstance(status_code, str) and status_code.isdigit():
        status_code = int(status_code)
    if status_code not in (None, 400, 413):
        return False
    response_text = str(error.details.get("response", "")).lower()
    message_text = error.message.lower()
    markers = (
        "maximum context length",
        "context length exceeded",
        "context overflow",
        "payload too large",
        "too many tokens",
        "token limit",
    )
    return any(marker in response_text or marker in message_text for marker in markers)


def build_turn_result(
    session_id: str, turn_id: str, messages: list[Message]
) -> TurnResult:
    """Assemble TurnResult from a stream of messages yielded by AgentLoop.

    The last message is expected to be a turn_meta message carrying stop_reason,
    completed flag, and usage. If absent, sensible defaults are applied.
    """
    if not messages:
        return TurnResult(
            session_id=session_id,
            turn_id=turn_id,
            completed=False,
            stop_reason="error",
        )

    *body, turn_meta = messages
    if turn_meta.role != "turn_meta":
        meta: dict[str, Any] = {}
        body = messages
    else:
        meta = dict(turn_meta.metadata)

    assistant_msgs = [m for m in body if m.role == "assistant"]
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []

    for msg in body:
        if msg.role == "assistant":
            for tc in msg.metadata.get("tool_calls", []):
                tool_calls.append(
                    ToolCall(
                        call_id=tc["call_id"],
                        name=tc["name"],
                        arguments=tc.get("arguments", {}),
                    )
                )
        elif msg.role == "tool":
            tool_results.append(
                ToolResult(
                    call_id=msg.tool_call_id or "",
                    name=msg.metadata.get("tool_name", ""),
                    content=msg.content,
                    output=msg.metadata.get("tool_output"),
                    error=msg.metadata.get("tool_error"),
                )
            )

    usage = meta.get("usage")
    if usage is not None and not isinstance(usage, TokenUsage):
        usage = None

    return TurnResult(
        session_id=session_id,
        turn_id=turn_id,
        messages=tuple(assistant_msgs),
        tool_calls=tuple(tool_calls),
        tool_results=tuple(tool_results),
        completed=meta.get("completed", False),
        stop_reason=meta.get("stop_reason", "completed"),
        usage=usage,
    )


def _read_skill_ref(ref: SkillSessionRef) -> str | None:
    if not ref.location.is_file():
        return None
    return ref.location.read_text(encoding="utf-8")


def _post_compact_messages_from(msg: Message) -> tuple[Message, ...]:
    raw = msg.metadata.pop("_post_compact_messages", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(item for item in raw if isinstance(item, Message))


def _skill_batch_review_key(trigger: Any) -> str:
    skill_name = getattr(trigger, "skill_name", None)
    if not isinstance(skill_name, str) or not skill_name:
        return ""
    root = _skill_batch_review_root_key(getattr(trigger, "skill_root", None))
    if root is None:
        return skill_name
    return f"{root}:{skill_name}"


def _skill_batch_review_root_key(skill_root: Any) -> str | None:
    try:
        if skill_root is None:
            return None
        return str(Path(skill_root).expanduser().resolve())
    except TypeError:
        return None


# bugfix-380: maximum length for provider error text embedded in the assistant message content.
_PROVIDER_ERROR_MAX_CHARS = 1024

_COMPACTION_FAILURE_TEXT = (
    "上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。"
    "请稍后重试，或发送 /compact <希望保留的重点> 后继续。"
)


def _build_provider_error_message(
    exc: ModelError,
    *,
    model: str | None = None,
    parent_message_id: str | None = None,
) -> Message:
    """Build a synthetic assistant Message that surfaces a provider error to the user.

    The message is persisted with is_provider_error=True so build_chat_messages can
    filter it out of the next LLM history (CC isSyntheticApiErrorMessage pattern).
    The model id is required so consecutive fallback failures remain distinguishable.
    """
    raw_text = str(exc)
    if len(raw_text) > _PROVIDER_ERROR_MAX_CHARS:
        raw_text = raw_text[:_PROVIDER_ERROR_MAX_CHARS] + "…(truncated)"
    model_id = model.strip() if isinstance(model, str) and model.strip() else "unknown"
    content = f"⚠️ 模型调用失败（{model_id}）:{raw_text}"
    return Message(
        message_id=make_message_id(),
        parent_message_id=parent_message_id,
        role="assistant",
        content=content,
        metadata={"is_provider_error": True},
    )


def _build_compaction_error_message(*, parent_message_id: str | None = None) -> Message:
    """Build the non-persisted assistant notice for automatic compaction failure."""

    return Message(
        message_id=make_message_id(),
        parent_message_id=parent_message_id,
        role="assistant",
        content=_COMPACTION_FAILURE_TEXT,
        metadata={"is_compaction_error": True},
    )


# _message_from_turn_entry and _read_file_slice migrated to break loop->runtime cycle.
# See session/entries.py and tools/session_file_state.py respectively.
