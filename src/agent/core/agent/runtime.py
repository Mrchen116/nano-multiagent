"""High-level runtime orchestration over sessions, hooks, loop, and compaction."""

import asyncio
import contextlib
import logging
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol, Sequence

from agent.core.agent.liveness import (
    _broker_publish_adapter,
    _emit_liveness_heartbeats,
)
from agent.core.errors import ModelError
from agent.core.ids import make_message_id, make_turn_id
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
from agent.core.session.jsonl_store import (
    USER_INTERRUPT_RECOVERY_CONTENT,
    SessionConfig,
)
from agent.core.session.manager import SessionManager
from agent.core.session.models import Session
from agent.core.skills import SkillMetadata, resolve_available_skills
from agent.core.skills.discovery import SkillRootResolver
from agent.core.tools.result_budget import ToolResultCompressor
from agent.core.tools.session_file_state import SessionFileState, read_file_slice
from agent.core.utils.time import utc_now_iso as _utc_now_iso

from .compaction.applier import CompactionApplier
from .compaction.planner import CompactionPlanner
from .compaction.summarizer import CompactionSummarizer
from .compaction.types import CompactionReason, CompactionResult, CompactionSettings
from .context_fork import AgentContextFork
from .loop import AgentLoop, ToolRegistryLike
from .policies import AgentPolicies
from .run_control import RunController
from .prompting import build_system_prompt
from .skill_commands import rewrite_skill_command
from .state import AgentState, InputPart, parse_input_parts, render_user_text
from agent.core.session.entries import message_from_turn_entry
from agent.core.agent.prompt_sections.base import (
    PromptSection,
    resolve_effective_prompt,
)
from agent.core.agent.prompt_sections.wiring import (
    build_prompt_context_from_metadata,
    resolve_flags_from_metadata,
)
from agent.core.memory.path import derive_memory_root
from agent.core.memory.store import MemoryStore
from typing import TypedDict

logger = logging.getLogger(__name__)


class MemorySnapshot(TypedDict):
    """Lazy-frozen memory snapshot for one session.

    Frozen on the first turn and held for the session's lifetime so the
    stable prefix in the system prompt does not change between turns (which
    would bust provider prefix-cache hits).  Invalidated on compaction so
    the next turn re-reads updated memory from disk.

    M4 Decision 17: memory_content / user_profile_content hold pure data (no banner);
    memory_pct / user_pct hold usage percentages for banner rendering by core segments.
    """

    memory_content: "str | None"
    memory_pct: int
    user_profile_content: "str | None"
    user_pct: int


if TYPE_CHECKING:
    from agent.core.hooks.registry import HookRegistry


class ConfigResolverLike(SkillRootResolver, Protocol):
    def user_tool_roots(self) -> tuple[Path, ...]: ...

    def user_hook_roots(self) -> tuple[Path, ...]: ...


class AgentRuntime:
    """Coordinate one runtime instance for session-based agent execution."""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        llm_client: LLMClient | None = None,
        llm_client_factory: Callable[[LLMFactoryConfig], LLMClient] | None = None,
        model: str | None = None,
        policies: AgentPolicies | None = None,
        hook_runner: HookRunner | None = None,
        repo_root: Path | None = None,
        available_skills: Sequence[SkillMetadata] | None = None,
        compaction_settings: CompactionSettings | None = None,
        tool_registry: ToolRegistryLike | None = None,
        system_prompt: str | None = None,
        config_resolver: ConfigResolverLike | None = None,
        default_tool_ids: list[str] | None = None,
        permission_broker: Any | None = None,
        prompt_sections: Sequence[PromptSection] | None = None,
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
                "AgentRuntime requires either llm_client or llm_client_factory; "
                "pass llm_client for unit tests, llm_client_factory for production wiring"
            )
        self._llm_client_factory = llm_client_factory
        self._llm_client = active_llm_client
        self._hook_runner = hook_runner
        self._repo_root = (repo_root or Path.cwd()).expanduser().resolve()
        self._config_resolver = config_resolver
        self._compaction_settings = compaction_settings or CompactionSettings()
        resolved_skills = (
            tuple(available_skills) if available_skills is not None else ()
        )
        self._session_manager = session_manager
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
        self._session_file_states: dict[str, SessionFileState] = {}
        # In-memory session state: primary data source during normal operation.
        self._session_histories: dict[str, list[Message]] = {}
        self._session_configs: dict[str, SessionConfig] = {}
        self._session_paths: dict[str, Path] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        # Per-session memory snapshot cache: lazy freeze on first turn, invalidated on compaction.
        self._memory_snapshots: dict[str, MemorySnapshot] = {}
        # Prompt sections for segment-based assembly; empty list = no sections registered (legacy path).
        self._prompt_sections: list[PromptSection] = (
            list(prompt_sections) if prompt_sections else []
        )
        # Per-session product PromptSlots (refactor-406 决策 8): the consumer's
        # create_session(prompt=PromptSlots) registers slots here; _run_locked
        # threads them into the PromptContext so the kernel skeleton places the
        # product's head/body/custom/tail text. SDK-owned object read structurally
        # (no core→sdk import); not persisted to JSONL (it can't round-trip JSON
        # and is rebuilt per process by the consumer factory on session open).
        self._session_prompt_slots: dict[str, object] = {}
        tool_results_dir = self._repo_root / ".nano" / "tool-results"
        self._tool_result_compressor = ToolResultCompressor(tool_results_dir)
        self._context_fork = AgentContextFork(
            llm_client=active_llm_client,
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
        self._compaction_summarizer = CompactionSummarizer(
            fork=_summary_fork,
        )
        self._compaction_applier = CompactionApplier(session_manager=session_manager)
        self._loop = AgentLoop(
            llm_client=active_llm_client,
            model=self._llm_config.model,
            policies=policies,
            hook_runner=hook_runner,
            available_skills=resolved_skills,
            tool_registry=tool_registry,
            current_working_directory=self._repo_root,
            system_prompt=system_prompt,
            tool_result_compressor=self._tool_result_compressor,
            session_manager=session_manager,
            compaction_planner=self._compaction_planner,
            compaction_summarizer=self._compaction_summarizer,
            compaction_settings=self._compaction_settings,
            on_compaction=self._invalidate_memory_snapshot,
        )

    def register_session_prompt_slots(self, session_id: str, slots: object) -> None:
        """Register per-session product PromptSlots (refactor-406 决策 8).

        Called by the kernel on create_session(prompt=PromptSlots). The slots are
        threaded into the PromptContext at turn time so the kernel skeleton places
        the product's head/body/custom/tail text. Storing None or omitting a session
        leaves the slots empty (skeleton renders kernel segments only).

        Args:
            session_id: Session the slots apply to.
            slots: SDK-owned PromptSlots (read structurally; no import here).
        """
        if slots is not None:
            self._session_prompt_slots[session_id] = slots

    async def run(
        self,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
        run_id: str | None = None,
        controller: RunController | None = None,
        parent_session_id: str | None = None,
        workspace_root: Path | None = None,
        origin: Any = None,
    ) -> TurnResult:
        """Execute one turn for an existing session.

        Args:
            session_id: Target session id.
            parts: Structured input parts (`text` or `image`).
            stream: Reserved compatibility flag (currently ignored).
            llm_session_id: Optional provider session id override.
            parent_session_id: Optional parent session id for subagent path resolution.
            workspace_root: Session's workspace root. Required (in production) to
                locate the session JSONL on the first load of this process
                lifetime; once the session is cached its config carries the
                workspace_root for subsequent writes.
            origin: RunOrigin enum value (or None) passed from RunsRegistry;
                written into hook_metadata["run_origin"] so auto_mode_gate can
                detect unattended contexts (heartbeat/cron) without re-importing
                RunOrigin in core hooks.

        Returns:
            Turn result containing assistant output, tool calls/results, and stop reason.

        Raises:
            ValueError: If session is missing or resolved user text is empty.
            ModelError: If provider call fails and overflow recovery cannot recover.

        Side Effects:
            Persists turn events/messages and dispatches hook events.
        """

        del stream  # M4 minimal runtime only supports non-stream flow.

        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self._run_locked(
                session_id=session_id,
                parts=parts,
                llm_session_id=llm_session_id,
                run_id=run_id,
                controller=controller,
                parent_session_id=parent_session_id,
                workspace_root=workspace_root,
                origin=origin,
            )

    async def _run_locked(
        self,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        *,
        llm_session_id: str | None = None,
        run_id: str | None = None,
        controller: RunController | None = None,
        parent_session_id: str | None = None,
        workspace_root: Path | None = None,
        origin: Any = None,
    ) -> TurnResult:
        """Internal run implementation (assumes session lock is held)."""

        # --- Cache-first load: miss reads JSONL once, hit uses memory ---
        if session_id not in self._session_histories:
            path = self._session_manager.store.resolve_path(
                session_id,
                workspace_root=workspace_root,
                parent_session_id=parent_session_id,
            )
            # Repair any orphaned tool_calls from a previous interrupted run before
            # loading history into the in-process cache.  This ensures the LLM never
            # sees a transcript with unclosed tool_calls (which most providers reject).
            # Only necessary on the first load of this session in this process; on
            # cache-hit the history is already known-good in memory.
            self._session_manager.prepare_transcript_for_run(
                session_id,
                reason="orphaned",
                workspace_root=workspace_root,
                parent_session_id=parent_session_id,
            )
            try:
                result = self._session_manager.load(
                    session_id,
                    workspace_root=workspace_root,
                    parent_session_id=parent_session_id,
                )
            except Exception as exc:
                raise ValueError(f"session does not exist: {session_id}") from exc
            self._session_histories[session_id] = list(result.messages)
            self._session_configs[session_id] = result.config
            self._session_paths[session_id] = path

        history = self._session_histories[session_id]
        config = self._session_configs[session_id]
        path = self._session_paths[session_id]

        session_created_at = config.created_at
        session_workspace_root = config.workspace_root
        session_available_skills = self._resolve_session_available_skills_from_config(
            config
        )
        session_available_tools = self._resolve_session_available_tools_from_config(
            config
        )
        frozen_system_prompt = config.system_prompt

        input_parts = parse_input_parts(parts)
        user_text = render_user_text(input_parts)
        if not user_text:
            raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        hook_metadata: dict[str, Any] = (
            dict(config.metadata) if isinstance(config.metadata, Mapping) else {}
        )
        hook_metadata["cwd"] = str(session_workspace_root)
        hook_metadata["context_window"] = self._compaction_settings.context_window
        # Thread workspace_root per-turn so MemoryTool + _ensure_memory_snapshot share
        # the same derivation path (both use derive_memory_root for isolation).
        if session_workspace_root is not None:
            hook_metadata["workspace_root"] = str(session_workspace_root)
        if isinstance(run_id, str) and run_id.strip():
            hook_metadata["run_id"] = run_id.strip()
        # Thread RunRecord.origin through to hook_metadata so auto_mode_gate can
        # detect unattended contexts (RunOrigin.HEARTBEAT etc.) without importing
        # RunOrigin in core hooks. Use .value (string) for decoupling.
        if origin is not None:
            hook_metadata["run_origin"] = getattr(origin, "value", str(origin))
        hook_ctx = self._build_hook_context(
            session_id=session_id, turn_id=turn_id, metadata=hook_metadata
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
        if not user_text:
            raise ValueError("empty input parts are not allowed")
        user_text = rewrite_skill_command(user_text)

        before_payload, _ = await self._dispatch_intercept(
            "before_agent_start",
            {"message": user_text, "system_prompt": None},
            hook_ctx,
        )
        message_override = before_payload.get("message")
        if isinstance(message_override, str):
            user_text = message_override
        if not user_text:
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
                render_mode=RenderMode.RUNTIME,
                flags=flags,
                vars={
                    "custom_prompt": str(hook_metadata.get("custom_prompt", "")),
                    # feat-394-M9: heartbeat/cron gates moved to ctx.flags via
                    # FEATURE_REGISTRY (decision D).  vars injection retired.
                },
                # refactor-406 决策 8: thread the consumer's per-session PromptSlots
                # so the kernel skeleton's slot sections render product text.
                prompt_slots=self._session_prompt_slots.get(session_id),
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
        user_message_id = make_message_id()

        user_msg = Message(
            message_id=user_message_id,
            parent_message_id=history[-1].message_id if history else None,
            role="user",
            content=user_text,
        )
        history.append(user_msg)
        self._session_manager.writer.enqueue(
            path, _message_to_entry(user_msg, session_id)
        )
        await self._session_manager.writer.flush_async()

        # Remove the user message we just added from history passed to loop.
        loop_history = tuple(history[:-1])

        # Multi-part expansion (M246)
        effective_user_text = user_text
        effective_input_parts = input_parts
        if len(input_parts) > 1:
            extra_parts = input_parts[:-1]
            last_part = input_parts[-1:]
            extra_messages = tuple(
                Message(
                    message_id=make_message_id(),
                    parent_message_id=loop_history[-1].message_id
                    if loop_history
                    else None,
                    role="user",
                    content=render_user_text([part]),
                )
                for part in extra_parts
                if render_user_text([part])
            )
            loop_history = loop_history + extra_messages
            effective_user_text = render_user_text(last_part)
            effective_input_parts = last_part

        all_messages: list[Message] = [user_msg]
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
                available_skills_override=()
                if use_frozen_system_prompt
                else session_available_skills,
                available_tools_override=session_available_tools,
                controller=controller,
            ):
                if msg.role == "turn_meta":
                    all_messages.append(msg)
                    continue
                history.append(msg)
                all_messages.append(msg)
                # Detect compact summary: write compact_boundary before the summary turn
                if msg.metadata.get("is_compact_summary"):
                    self._session_manager.writer.enqueue(
                        path,
                        {
                            "type": "compact_boundary",
                            "session_id": session_id,
                            "timestamp": _utc_now_iso(),
                            "summary_uuid": msg.message_id,
                            "data": {
                                "reason": msg.metadata.get(
                                    "compact_reason", "threshold"
                                ),
                                "restored_files": msg.metadata.get(
                                    "restored_files", []
                                ),
                            },
                        },
                    )
                entry = _message_to_entry(msg, session_id)
                if msg.role == "tool":
                    self._session_manager.writer.enqueue(path, entry)
                    await self._session_manager.writer.flush_async()
                else:
                    self._session_manager.writer.enqueue(path, entry)
            await self._session_manager.writer.flush_async()
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
        except ModelError as exc:
            await self._session_manager.writer.flush_async()
            # Attempt overflow recovery: compact then retry once.
            if (
                not _overflow_retried
                and _is_context_overflow_error(exc)
                and self._compaction_settings.enabled
            ):
                _overflow_retried = True
                compact_result = await self._compact_session(
                    session_id=session_id, reason=CompactionReason.OVERFLOW
                )
                if compact_result is not None:
                    # Rebuild history from session store after compaction.
                    reloaded = self._session_manager.list_turn_messages(session_id)
                    history.clear()
                    history.extend(reloaded)
                    # user_msg was written before the overflow; it's in the reloaded history.
                    # Rebuild loop_history excluding it, then re-run.
                    retry_history = tuple(
                        m for m in history if m.message_id != user_msg.message_id
                    )
                    all_messages = [user_msg]
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
                        available_skills_override=()
                        if use_frozen_system_prompt
                        else session_available_skills,
                        available_tools_override=session_available_tools,
                        controller=controller,
                    ):
                        if msg.role == "turn_meta":
                            all_messages.append(msg)
                            continue
                        history.append(msg)
                        all_messages.append(msg)
                        if msg.metadata.get("is_compact_summary"):
                            self._session_manager.writer.enqueue(
                                path,
                                {
                                    "type": "compact_boundary",
                                    "session_id": session_id,
                                    "timestamp": _utc_now_iso(),
                                    "summary_uuid": msg.message_id,
                                    "data": {
                                        "reason": msg.metadata.get(
                                            "compact_reason", "threshold"
                                        ),
                                        "restored_files": msg.metadata.get(
                                            "restored_files", []
                                        ),
                                    },
                                },
                            )
                        entry = _message_to_entry(msg, session_id)
                        if msg.role == "tool":
                            self._session_manager.writer.enqueue(path, entry)
                            await self._session_manager.writer.flush_async()
                        else:
                            self._session_manager.writer.enqueue(path, entry)
                    await self._session_manager.writer.flush_async()
                else:
                    raise
            else:
                # bugfix-380: synthesize a user-visible error assistant message before re-raising.
                # This surfaces the upstream error in IM/CLI without changing the existing
                # run_status=failed telemetry path (registry._mark_failed_async is triggered
                # by the re-raised ModelError as before).
                error_msg = _build_provider_error_message(
                    exc,
                    parent_message_id=user_msg.message_id,
                )
                history.append(error_msg)
                self._session_manager.writer.enqueue(
                    path, _message_to_entry(error_msg, session_id)
                )
                await self._session_manager.writer.flush_async()
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
        if self._hook_runner is not None:
            background_registrations = (
                self._hook_runner.registry.background_handlers_for("agent_end")
            )
            if background_registrations:
                from agent.core.agent.context_fork import make_fork_conversation

                # Build fork_conversation using the current session's rendered state.
                # We resolve the fork tools and system prompt from the session config.
                fork_system_prompt: str | None = None
                fork_active_tools: tuple[ToolSpec, ...] = ()
                if session_id in self._session_configs:
                    fork_config = self._session_configs[session_id]
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
                )

                # replace() derives from the turn's hook_ctx, preserving every field
                # (model_caller / permission_requester / message_history) and only
                # attaching fork_conversation. The hand-listed rebuild had been
                # dropping permission_requester + message_history.
                background_hook_ctx = replace(hook_ctx, fork_conversation=fork_fn)
                self._hook_runner.dispatch_background(
                    "agent_end", agent_end_payload, background_hook_ctx
                )

        return turn_result

    async def compact(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> CompactionResult | None:
        """Run manual session compaction.

        Args:
            session_id: Target session id.
            workspace_root: Session's workspace root, used to locate the JSONL
                when the session is not already cached in this runtime.

        Returns:
            Compaction result, or `None` when planner decides compaction is unnecessary.

        Raises:
            ValueError: If session does not exist.
        """

        if self.get_session(session_id, workspace_root=workspace_root) is None:
            raise ValueError(f"session does not exist: {session_id}")
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self._compact_session(
                session_id=session_id, reason=CompactionReason.MANUAL
            )

    async def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
        workspace_root: Path | None = None,
    ) -> TurnResult:
        """Request another assistant step by submitting synthetic `continue` input."""

        return await self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
            workspace_root=workspace_root,
        )

    def get_session(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> Session | None:
        """Return session model by id, or `None` when absent.

        When the session is already cached in this runtime, its known
        workspace_root is used so callers need not re-supply it; otherwise the
        caller-provided ``workspace_root`` locates the JSONL.
        """

        cached_config = self._session_configs.get(session_id)
        if cached_config is not None:
            return self._session_manager.get_session(
                session_id, workspace_root=cached_config.workspace_root
            )
        return self._session_manager.get_session(
            session_id, workspace_root=workspace_root
        )

    def get_llm_config(self) -> LLMFactoryConfig:
        """Return active LLM configuration used by the runtime."""

        return self._llm_config

    def reconfigure_llm(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        api_key: str | None = None,
        update_api_key: bool = False,
    ) -> LLMFactoryConfig:
        """Reconfigure provider/model connection without recreating runtime.

        Notes:
            Provider adaptation details stay encapsulated in `llm.factory` and
            `llm.protocols.*`; runtime continues to depend on `LLMClient` only.

        Raises:
            ValueError: If no effective config field is provided.
        """

        if (
            provider is None
            and model is None
            and base_url is None
            and timeout_seconds is None
            and not update_api_key
        ):
            raise ValueError("at least one llm config field is required")

        next_config = LLMFactoryConfig(
            provider=provider if provider is not None else self._llm_config.provider,
            model=model if model is not None else self._llm_config.model,
            base_url=base_url if base_url is not None else self._llm_config.base_url,
            api_key=api_key if update_api_key else self._llm_config.api_key,
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else self._llm_config.timeout_seconds,
        )

        if self._llm_client_factory is None:
            raise ValueError(
                "reconfigure_llm requires llm_client_factory; "
                "runtime was constructed without a factory (unit test path)"
            )
        active_llm_client = self._llm_client_factory(next_config)
        self._llm_config = next_config
        self._llm_client = active_llm_client
        self._loop.bind_llm_client(
            llm_client=active_llm_client,
            model=next_config.model,
        )
        self._context_fork = AgentContextFork(
            llm_client=active_llm_client,
            model=next_config.model,
            system_prompt=self._loop._system_prompt,
            available_skills=self._loop.available_skills,
            tool_registry=self._tool_registry,
            current_working_directory=self._repo_root,
        )
        self._compaction_summarizer = CompactionSummarizer(
            fork=self._context_fork,
        )
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

    @property
    def hook_runner(self) -> HookRunner | None:
        """Expose active hook runner."""

        return self._hook_runner

    @property
    def config_resolver(self) -> ConfigResolverLike | None:
        """Expose the resolver used for product-owned workspace/global paths."""

        return self._config_resolver

    @property
    def hook_registry(self) -> "HookRegistry | None":
        """Expose active hook registry when runner is configured."""

        if self._hook_runner is None:
            return None
        return self._hook_runner.registry

    def active_session_ids(self) -> tuple[str, ...]:
        """Return ids of sessions currently loaded in this runtime's memory.

        These are the sessions this process actually ran (loaded via ``run``);
        the stateless kernel has no global on-disk registry, and firing
        ``session_shutdown`` only for sessions this process touched is also the
        semantically correct scope.
        """

        return tuple(self._session_configs.keys())

    def session_workspace_root(self, session_id: str) -> Path | None:
        """Return the cached workspace_root of a loaded session, or ``None``.

        Tools running inside a turn (e.g. the ``agent`` tool resolving a
        subagent) use this to obtain the parent session's workspace_root —
        which the parent turn already loaded — so the stateless store can
        locate subagent JSONL files under the parent's workspace.
        """

        config = self._session_configs.get(session_id)
        return config.workspace_root if config is not None else None

    async def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
        parent_session_id: str | None = None,
    ) -> Session:
        """Create a session and emit `session_start` observe hook."""

        session = self._session_manager.create_session(
            workspace_root=workspace_root,
            title=title,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=metadata,
            parent_session_id=parent_session_id,
        )
        hook_ctx = self._build_hook_context(session_id=session.session_id)
        await self._dispatch_observe(
            "session_start",
            {"session_id": session.session_id},
            hook_ctx,
        )
        return session

    async def close_session(self, session_id: str) -> None:
        """Close a session: cancel active run, flush JSONL, evict memory."""

        # Cancel active run if any (runs registry handles this externally).
        # Flush + evict under lock.
        lock = self._session_locks.get(session_id)
        if lock:
            async with lock:
                await self._session_manager.writer.flush_async()
                self._session_histories.pop(session_id, None)
                self._session_configs.pop(session_id, None)
                self._session_paths.pop(session_id, None)
        else:
            await self._session_manager.writer.flush_async()

        self._session_file_states.pop(session_id, None)
        self._session_locks.pop(session_id, None)
        self._memory_snapshots.pop(session_id, None)
        # refactor-406-M3fix #7: drop per-session PromptSlots registered via
        # register_session_prompt_slots (refactor-406 新增 per-session 系统提示槽).
        # Without this, _session_prompt_slots grows unboundedly across a long-running
        # gateway's session churn (memory leak introduced by this unit's PromptSlots).
        self._session_prompt_slots.pop(session_id, None)

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

        Two steps with **unequal protection levels** (do not reorder):

        1. ``invalidate_session_cache`` is the load-bearing self-heal: dropping
           the dirty in-memory history forces the next turn to re-read JSONL
           (cache-miss → ``prepare_transcript_for_run`` rebuilds). It is a
           synchronous atomic dict pop with no ``await`` point, so we run it
           *first*, before any I/O — it always completes even while a
           ``CancelledError`` is propagating, no shield needed. If it were
           skipped, a cache-hit next turn would reuse the orphan and brick the
           session until process restart (#82 reopen).
        2. ``append_tool_call_recovery`` + flush is out-of-band acceleration
           (lets the LLM side close immediately rather than waiting for the next
           ``prepare``). It performs I/O, so during cancel-driven unwinding it is
           wrapped in ``asyncio.shield`` and treated best-effort; failure here
           still self-heals via the next ``prepare`` (the synthetic result is
           reconstructed from the orphaned assistant turn already on disk). Its
           UI badge terminal state is independently reconciled by M4.

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

        # Step 1 — load-bearing, synchronous, must run before any await.
        self.invalidate_session_cache(session_id)

        # Step 2 — best-effort out-of-band write; shielded against re-cancel.
        async def _write_recovery() -> None:
            for cid, name in orphans:
                self._session_manager.append_tool_call_recovery(
                    session_id,
                    tool_call_id=cid,
                    tool_name=name,
                    reason=reason,
                    content=content,
                    workspace_root=workspace_root,
                    parent_session_id=parent_session_id,
                )
            await self._session_manager.writer.flush_async()

        if cancelled:
            try:
                await asyncio.shield(_write_recovery())
            except asyncio.CancelledError:
                # Re-cancel during the shielded write: the cache is already
                # invalidated (step 1), so the next prepare() still self-heals.
                raise
        else:
            await _write_recovery()

    def invalidate_session_cache(self, session_id: str) -> None:
        """Drop cached in-memory history/config/path for one session.

        Called after an out-of-band JSONL append (see ``Kernel.append_message``)
        so the next turn re-reads the transcript instead of serving the stale
        cache populated by an earlier run. Without this, a message appended
        between turns (e.g. cron awareness injection) is written to JSONL but
        never seen by the model, which reads ``_session_histories`` cache-first.

        Plain dict pops: atomic in CPython and therefore safe to call from sync
        code without the asyncio session lock. An in-flight turn holds its own
        local reference to the history list, so dropping the cache key cannot
        corrupt it — the turn finishes and persists normally, and the following
        turn reloads from JSONL (which by then contains both sets of messages).
        """

        self._session_histories.pop(session_id, None)
        self._session_configs.pop(session_id, None)
        self._session_paths.pop(session_id, None)

    async def fork_session(
        self, source_session_id: str, *, workspace_root: Path | None = None
    ) -> Session:
        """Fork a session: create a new session with an independent copy of source history.

        The fork copies the linear conversation chain from the source session,
        re-stamping all message UUIDs and recalculating parent_uuid links.
        The new session has its own JSONL file and in-memory history.

        ``workspace_root`` locates the source session JSONL when it is not
        already cached in this runtime; the fork inherits the source's
        workspace_root.
        """

        # Ensure source is loaded into memory
        if source_session_id not in self._session_histories:
            result = self._session_manager.load(
                source_session_id, workspace_root=workspace_root
            )
            self._session_histories[source_session_id] = list(result.messages)
            self._session_configs[source_session_id] = result.config
            self._session_paths[source_session_id] = (
                self._session_manager.store.resolve_path(
                    source_session_id, workspace_root=result.config.workspace_root
                )
            )

        source_config = self._session_configs[source_session_id]
        source_history = self._session_histories[source_session_id]

        # Acquire source lock to prevent concurrent modification during fork
        source_lock = self._session_locks.get(source_session_id)
        if source_lock:
            async with source_lock:
                return await self._fork_locked(
                    source_session_id, source_config, list(source_history)
                )
        return await self._fork_locked(
            source_session_id, source_config, list(source_history)
        )

    async def _fork_locked(
        self,
        source_session_id: str,
        source_config: SessionConfig,
        source_history: list[Message],
    ) -> Session:
        """Internal fork implementation (source lock held if applicable)."""

        new_metadata = dict(source_config.metadata)
        new_metadata["forked_from"] = source_session_id

        new_session = self._session_manager.create_session(
            workspace_root=source_config.workspace_root,
            system_prompt=source_config.system_prompt,
            skills=source_config.skills,
            tool_allowlist=source_config.tool_allowlist,
            metadata=new_metadata,
        )
        new_session_id = new_session.session_id
        new_path = self._session_manager.store.resolve_path(
            new_session_id, workspace_root=source_config.workspace_root
        )

        # Re-stamp messages: new UUIDs, recalculated parent chain
        if source_history:
            old_to_new_uuid: dict[str, str] = {}
            new_history: list[Message] = []

            for msg in source_history:
                new_uuid = make_message_id()
                old_to_new_uuid[msg.message_id] = new_uuid

                old_parent = msg.parent_message_id
                new_parent = old_to_new_uuid.get(old_parent) if old_parent else None

                # replace() re-stamps only the fork-specific fields (new ids /
                # parent chain / metadata) and preserves every other field —
                # notably reasoning_content / reasoning_signature. A hand-listed
                # Message(...) rebuild had been dropping the reasoning fields, so a
                # forked thinking-enabled session lost its <thinking> blocks and the
                # next turn was rejected upstream with "reasoning_content is missing"
                # (same brittle pattern fixed in _strip_fork_conversation).
                new_msg = replace(
                    msg,
                    message_id=new_uuid,
                    parent_message_id=new_parent,
                    group_id=old_to_new_uuid.get(msg.group_id)
                    if msg.group_id
                    else None,
                    metadata=dict(msg.metadata),
                )
                new_history.append(new_msg)

                entry = _message_to_entry(new_msg, new_session_id)
                self._session_manager.store.writer.enqueue(new_path, entry)

            await self._session_manager.store.writer.flush_async()
            self._session_histories[new_session_id] = new_history
        else:
            self._session_histories[new_session_id] = []

        self._session_configs[new_session_id] = SessionConfig(
            session_id=new_session_id,
            created_at=new_session.created_at,
            workspace_root=source_config.workspace_root,
            system_prompt=source_config.system_prompt,
            skills=source_config.skills,
            tool_allowlist=source_config.tool_allowlist,
            metadata=new_metadata,
        )
        self._session_paths[new_session_id] = new_path
        self._session_locks[new_session_id] = asyncio.Lock()

        return new_session

    def _resolve_session_available_skills(
        self, session: Session
    ) -> tuple[SkillMetadata, ...]:
        if session.skills is None:
            return self._loop.available_skills
        if not session.skills:
            return ()
        return resolve_available_skills(
            workspace_root=session.workspace_root,
            include_names=session.skills,
            config_resolver=self._config_resolver,
        )

    def _resolve_session_available_skills_from_config(
        self, config: SessionConfig
    ) -> tuple[SkillMetadata, ...]:
        if config.skills is None:
            return self._loop.available_skills
        if not config.skills:
            return ()
        return resolve_available_skills(
            workspace_root=config.workspace_root,
            include_names=config.skills,
            config_resolver=self._config_resolver,
        )

    def _resolve_session_available_tools(
        self, session: Session
    ) -> tuple[ToolSpec, ...]:
        if session.tool_allowlist is None:
            all_specs = self._loop.active_tool_specs()
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(session.tool_allowlist)
        return tuple(
            tool for tool in self._loop.active_tool_specs() if tool.name in requested
        )

    def _resolve_session_available_tools_from_config(
        self, config: SessionConfig
    ) -> tuple[ToolSpec, ...]:
        if config.tool_allowlist is None:
            all_specs = self._loop.active_tool_specs()
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(config.tool_allowlist)
        return tuple(
            tool for tool in self._loop.active_tool_specs() if tool.name in requested
        )

    async def _dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> tuple[dict[str, Any], bool]:
        if self._hook_runner is None:
            return dict(payload), False
        try:
            dispatch_result = await self._hook_runner.dispatch_intercept(
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
        if self._hook_runner is None:
            return
        try:
            diagnostics = await self._hook_runner.dispatch_observe(
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
    ) -> HookContext:
        session_event_publisher = None
        if self._hook_runner is not None:
            session_event_publisher = _resolve_session_event_publisher(
                registry=self._hook_runner.registry,
                session_id=session_id,
            )

        # Build permission_requester closure when broker is available.
        # The closure captures the broker and session_event_publisher so
        # auto_mode_gate can park (register future + emit SSE) without knowing
        # whether the product is CLI or PA — the publisher routes to the right channel.
        permission_requester = None
        broker = self._permission_broker
        resolved_metadata = dict(metadata or {})
        if broker is not None:
            run_id_for_broker = resolved_metadata.get("run_id")
            publisher_for_broker = session_event_publisher

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
                    if can_use_tool is not None:
                        # Race can_use_tool callback against broker future.
                        # CLI products supply can_use_tool for interactive prompts;
                        # PA leaves it None and resolves via submit_permission_decision.
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
                            behavior = getattr(raw_decision, "behavior", "deny")
                            reason = getattr(raw_decision, "reason", "")
                            response = type(
                                "_R",
                                (),
                                {
                                    "decision": "deny"
                                    if behavior == "deny"
                                    else "allow_once",
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
        if self._tool_registry is not None:
            resolved_metadata["tool_registry"] = self._tool_registry

        return HookContext(
            session_id=session_id,
            turn_id=turn_id,
            repo_root=self._repo_root,
            metadata=resolved_metadata,
            model_caller=self._call_hook_model,
            session_event_publisher=session_event_publisher,
            permission_requester=permission_requester,
        )

    async def _call_hook_model(self, call: HookModelCall) -> HookModelResult:
        """Execute one hook-initiated model call under runtime configuration."""

        normalized_session = call.session_id.strip()
        if not normalized_session:
            raise ValueError("session_id is required")
        model = (call.model or self._llm_config.model).strip()
        if not model:
            raise ValueError("model is required")

        stream = self._llm_client.generate(
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
        controller: RunController | None = None,
    ):
        session_file_state = self._session_file_states.setdefault(
            session_id, SessionFileState()
        )
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
            session_file_state=session_file_state,
        ):
            yield msg

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
        if session_id in self._memory_snapshots:
            return self._memory_snapshots[session_id]

        flags = resolve_flags_from_metadata(metadata=metadata)
        if not flags.get("memory_curation", True):
            snapshot: MemorySnapshot = {
                "memory_content": None,
                "memory_pct": 0,
                "user_profile_content": None,
                "user_pct": 0,
            }
            self._memory_snapshots[session_id] = snapshot
            return snapshot

        workspace_root_raw = metadata.get("workspace_root")
        dirname = metadata.get("workspace_config_dirname")
        if not workspace_root_raw or not dirname:
            snapshot = {
                "memory_content": None,
                "memory_pct": 0,
                "user_profile_content": None,
                "user_pct": 0,
            }
            self._memory_snapshots[session_id] = snapshot
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
        }
        self._memory_snapshots[session_id] = snapshot
        return snapshot

    def _invalidate_memory_snapshot(self, session_id: str) -> None:
        """Remove cached snapshot so next turn triggers a fresh disk read (called after compaction)."""
        self._memory_snapshots.pop(session_id, None)

    async def _compact_session(
        self,
        *,
        session_id: str,
        reason: CompactionReason,
    ) -> CompactionResult | None:
        # Compaction always runs on a session that has been loaded by a prior
        # run(), so its config (and thus workspace_root) is cached here.
        config = self._session_configs.get(session_id)
        compaction_workspace_root = (
            config.workspace_root if config is not None else None
        )
        entries = self._session_manager.list_entries(
            session_id, workspace_root=compaction_workspace_root
        )
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
        summary = await self._compaction_summarizer.summarize(
            session_id=session_id,
            system_prompt=rendered_system_prompt,
            dropped_messages=dropped_messages,
        )

        # Post-compact file restore: read up to 5 most recently accessed files.
        file_state = self._session_file_states.get(session_id)
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

        # Write compact_boundary + summary directly via JSONL writer and update memory.
        path = self._session_paths.get(session_id)
        if path is not None:
            # Generate summary message
            last_preserved_id = None
            history = self._session_histories.get(session_id, [])
            if history:
                last_preserved_id = history[-1].message_id

            summary_msg = Message(
                message_id=make_message_id(),
                parent_message_id=last_preserved_id,
                role="user",
                content=summary,
                metadata={"is_compact_summary": True, "is_meta": True},
            )
            self._session_histories[session_id] = [summary_msg]
            # compact_boundary must be written before summary turn so that
            # JsonlSessionStore.load() (which keeps only turns after the latest
            # compact_boundary) includes the summary turn in the replayed history.
            self._session_manager.writer.enqueue(
                path,
                {
                    "type": "compact_boundary",
                    "session_id": session_id,
                    "timestamp": _utc_now_iso(),
                    "summary_uuid": summary_msg.message_id,
                    "data": {
                        "reason": reason.value,
                        "restored_files": list(restored_files),
                    },
                },
            )
            self._session_manager.writer.enqueue(
                path, _message_to_entry(summary_msg, session_id)
            )
            await self._session_manager.writer.flush_async()

        # Use applier for backward-compatible result object.
        result = self._compaction_applier.apply(
            session_id=session_id,
            plan=plan,
            summary=summary,
            restored_files=restored_files,
        )
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
        # Clear file state after extracting restore info.
        self._session_file_states.pop(session_id, None)
        return result

    def _history_without_message(
        self,
        *,
        session_id: str,
        message_id: str,
    ) -> tuple[Message, ...]:
        history = self._session_histories.get(session_id, [])
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


def _message_to_entry(msg: Message, session_id: str) -> dict[str, Any]:
    """Convert a Message to a JSONL turn entry."""
    entry: dict[str, Any] = {
        "type": "turn",
        "uuid": msg.message_id,
        "parent_uuid": msg.parent_message_id,
        "session_id": session_id,
        "role": msg.role,
        "content": msg.content,
        "timestamp": _utc_now_iso(),
    }
    if msg.tool_call_id is not None:
        entry["tool_call_id"] = msg.tool_call_id
    if msg.group_id is not None:
        entry["group_id"] = msg.group_id
    meta = dict(msg.metadata)
    if meta.get("is_meta"):
        entry["is_meta"] = True
    if meta.get("is_compact_summary"):
        entry["is_compact_summary"] = True
    if meta.get("is_provider_error"):
        entry["is_provider_error"] = True
    if meta.get("entrypoint"):
        entry["entrypoint"] = meta["entrypoint"]
    if meta.get("tool_calls"):
        entry["tool_calls"] = meta["tool_calls"]
    if meta.get("tool_name"):
        entry["tool_name"] = meta["tool_name"]
    if meta.get("tool_error"):
        entry["tool_error"] = meta["tool_error"]
    if meta.get("tool_output") is not None:
        entry["tool_output"] = meta["tool_output"]
    if msg.reasoning_content is not None:
        entry["reasoning_content"] = msg.reasoning_content
    if msg.reasoning_signature is not None:
        entry["reasoning_signature"] = msg.reasoning_signature
    return entry


# bugfix-380: maximum length for provider error text embedded in the assistant message content.
_PROVIDER_ERROR_MAX_CHARS = 1024


def _build_provider_error_message(
    exc: ModelError,
    *,
    parent_message_id: str | None = None,
) -> Message:
    """Build a synthetic assistant Message that surfaces a provider error to the user.

    The message is persisted with is_provider_error=True so build_chat_messages can
    filter it out of the next LLM history (CC isSyntheticApiErrorMessage pattern).
    """
    raw_text = str(exc)
    if len(raw_text) > _PROVIDER_ERROR_MAX_CHARS:
        raw_text = raw_text[:_PROVIDER_ERROR_MAX_CHARS] + "…(truncated)"
    content = f"⚠️ 模型调用失败:{raw_text}"
    return Message(
        message_id=make_message_id(),
        parent_message_id=parent_message_id,
        role="assistant",
        content=content,
        metadata={"is_provider_error": True},
    )


# _message_from_turn_entry and _read_file_slice migrated to break loop->runtime cycle.
# See session/entries.py and tools/session_file_state.py respectively.
