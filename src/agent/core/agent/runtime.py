"""High-level runtime orchestration over sessions, hooks, loop, and compaction."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

from agent.core.errors import ModelError
from agent.core.ids import make_message_id, make_turn_id
from agent.core.types import Message, ToolCall, ToolResult, ToolSpec, TurnResult
from agent.core.hooks.context import HookContext, HookModelCall, HookModelResult
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
from agent.core.session.entries import SessionEntry
from agent.core.session.manager import SessionManager
from agent.core.session.models import Session
from agent.core.skills import SkillMetadata, resolve_available_skills
from agent.core.skills.discovery import SkillRootResolver
from agent.core.tools.session_file_state import SessionFileState

from .compaction.applier import CompactionApplier
from .compaction.planner import CompactionPlanner
from .compaction.policy import should_compact
from .compaction.summarizer import CompactionSummarizer
from .compaction.types import CompactionReason, CompactionResult, CompactionSettings
from .loop import AgentLoop, ToolRegistryLike
from .policies import AgentPolicies
from .run_control import RunController
from .prompting import build_system_prompt
from .skill_commands import rewrite_skill_command
from .state import AgentState, InputPart, parse_input_parts, render_user_text

if TYPE_CHECKING:
    from agent.core.hooks.registry import HookRegistry


class ConfigResolverLike(SkillRootResolver, Protocol):
    def user_tool_roots(self) -> tuple[Path, ...]:
        ...

    def user_hook_roots(self) -> tuple[Path, ...]:
        ...


class AgentRuntime:
    """Coordinate one runtime instance for session-based agent execution."""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        llm_client: LLMClient | None = None,
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
    ) -> None:
        env_llm_config = LLMFactoryConfig.from_env()
        self._llm_config = LLMFactoryConfig(
            provider=env_llm_config.provider,
            model=model or env_llm_config.model,
            base_url=env_llm_config.base_url,
            api_key=env_llm_config.api_key,
            timeout_seconds=env_llm_config.timeout_seconds,
        )
        active_llm_client = llm_client or create_llm_client(config=self._llm_config)
        self._llm_client = active_llm_client
        self._hook_runner = hook_runner
        self._repo_root = (repo_root or Path.cwd()).expanduser().resolve()
        self._config_resolver = config_resolver
        self._compaction_settings = compaction_settings or CompactionSettings()
        resolved_skills = (
            tuple(available_skills)
            if available_skills is not None
            else ()
        )
        self._session_manager = session_manager
        # Product default tool ids used when no per-session tool_allowlist is set.
        # None means "all tools in registry" (platform default behavior).
        self._default_tool_ids = default_tool_ids
        self._session_file_states: dict[str, SessionFileState] = {}
        self._loop = AgentLoop(
            llm_client=active_llm_client,
            model=self._llm_config.model,
            policies=policies,
            hook_runner=hook_runner,
            available_skills=resolved_skills,
            tool_registry=tool_registry,
            current_working_directory=self._repo_root,
            system_prompt=system_prompt,
        )
        summary_model = self._compaction_settings.summary_model or self._llm_config.model
        self._compaction_planner = CompactionPlanner(
            min_kept_messages=self._compaction_settings.min_kept_messages
        )
        self._compaction_summarizer = CompactionSummarizer(
            llm_client=active_llm_client,
            model=summary_model,
        )
        self._compaction_applier = CompactionApplier(session_manager=session_manager)

    async def run(
        self,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
        run_id: str | None = None,
        controller: RunController | None = None,
    ) -> TurnResult:
        """Execute one turn for an existing session.

        Args:
            session_id: Target session id.
            parts: Structured input parts (`text` or `image`).
            stream: Reserved compatibility flag (currently ignored).
            llm_session_id: Optional provider session id override.

        Returns:
            Turn result containing assistant output, tool calls/results, and stop reason.

        Raises:
            ValueError: If session is missing or resolved user text is empty.
            ModelError: If provider call fails and overflow recovery cannot recover.

        Side Effects:
            Persists turn events/messages and dispatches hook events.
        """

        del stream  # M4 minimal runtime only supports non-stream flow.

        session = self._session_manager.get_session(session_id)
        if session is None:
            raise ValueError(f"session does not exist: {session_id}")
        session_created_at = session.created_at
        session_workspace_root = session.workspace_root
        session_available_skills = self._resolve_session_available_skills(session)
        session_available_tools = self._resolve_session_available_tools(session)
        frozen_system_prompt = session.system_prompt

        input_parts = parse_input_parts(parts)
        user_text = render_user_text(input_parts)
        if not user_text:
            raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        # Seed hook_metadata from session metadata so hooks (e.g. before_agent_start)
        # can read conversation_type, participant_agent_ids, agent_id, etc.
        # Runtime-injected keys (cwd, run_id) are applied after and always take priority.
        hook_metadata: dict[str, Any] = dict(session.metadata) if isinstance(session.metadata, Mapping) else {}
        hook_metadata["cwd"] = str(session_workspace_root)
        if isinstance(run_id, str) and run_id.strip():
            hook_metadata["run_id"] = run_id.strip()
        hook_ctx = self._build_hook_context(session_id=session_id, turn_id=turn_id, metadata=hook_metadata)

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
        system_prompt_override = before_payload.get("system_prompt")
        use_frozen_system_prompt = False
        if isinstance(system_prompt_override, str):
            system_prompt_override = system_prompt_override.strip()
            if not system_prompt_override:
                system_prompt_override = None
        else:
            system_prompt_override = None
        if system_prompt_override is None:
            system_prompt_override = frozen_system_prompt
            use_frozen_system_prompt = frozen_system_prompt is not None

        await self._dispatch_observe(
            "agent_start",
            {"session_id": session_id, "turn_id": turn_id},
            hook_ctx,
        )

        history = self._session_manager.list_turn_messages(session_id)
        turn_count = sum(1 for message in history if message.role == "user")
        user_message_id = make_message_id()

        self._session_manager.append_turn_message(
            session_id,
            turn_id=turn_id,
            role="user",
            content=user_text,
            message_id=user_message_id,
            parts=_serialize_input_parts(input_parts),
        )
        history_with_current_user = self._session_manager.list_turn_messages(session_id)
        await self._preflight_compaction(
            session_id=session_id,
            history=history_with_current_user,
        )
        history = self._history_without_message(
            session_id=session_id,
            message_id=user_message_id,
        )

        # Multi-part expansion (M246): when the gateway sends N buffered messages as N parts,
        # each part must appear as an independent user message in the LLM history rather than
        # being \n-joined into a single message.  Parts 0..N-2 are injected into history;
        # the last part becomes the current user_text consumed by the loop.
        # Single-part paths (N=1) are unchanged — backward compatible.
        effective_user_text = user_text
        effective_input_parts = input_parts
        if len(input_parts) > 1:
            extra_parts = input_parts[:-1]
            last_part = input_parts[-1:]
            extra_messages = tuple(
                Message(
                    message_id=make_message_id(),
                    role="user",
                    content=render_user_text([part]),
                )
                for part in extra_parts
                if render_user_text([part])
            )
            history = history + extra_messages
            effective_user_text = render_user_text(last_part)
            effective_input_parts = last_part

        try:
            turn_result = await self._execute_loop(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history=history,
                input_parts=effective_input_parts,
                user_text=effective_user_text,
                hook_ctx=hook_ctx,
                system_prompt_override=system_prompt_override,
                llm_session_id=llm_session_id,
                session_created_at=session_created_at,
                current_working_directory_override=session_workspace_root,
                available_skills_override=() if use_frozen_system_prompt else session_available_skills,
                available_tools_override=session_available_tools,
                controller=controller,
            )
        except ModelError as exc:
            # Retry boundary: only context-overflow-like failures trigger one
            # compaction attempt plus one replay; all other model errors bubble up.
            if not await self._post_turn_check_overflow(session_id=session_id, error=exc):
                raise
            base_retry_history = self._history_without_message(
                session_id=session_id,
                message_id=user_message_id,
            )
            # Re-apply multi-part expansion on the compaction-adjusted retry history.
            retry_history = base_retry_history + (history[len(base_retry_history):] if len(input_parts) > 1 else ())
            turn_result = await self._execute_loop(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history=retry_history,
                input_parts=effective_input_parts,
                user_text=effective_user_text,
                hook_ctx=hook_ctx,
                system_prompt_override=system_prompt_override,
                llm_session_id=llm_session_id,
                session_created_at=session_created_at,
                current_working_directory_override=session_workspace_root,
                available_skills_override=() if use_frozen_system_prompt else session_available_skills,
                available_tools_override=session_available_tools,
                controller=controller,
            )

        self._append_turn_events(session_id=session_id, turn_id=turn_id, turn_result=turn_result)
        await self._dispatch_observe(
            "agent_end",
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "completed": turn_result.completed,
                "stop_reason": turn_result.stop_reason,
            },
            hook_ctx,
        )
        return turn_result

    async def compact(self, session_id: str) -> CompactionResult | None:
        """Run manual session compaction.

        Args:
            session_id: Target session id.

        Returns:
            Compaction result, or `None` when planner decides compaction is unnecessary.

        Raises:
            ValueError: If session does not exist.
        """

        if self._session_manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        return await self._compact_session(session_id=session_id, reason=CompactionReason.MANUAL)

    async def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        """Request another assistant step by submitting synthetic `continue` input."""

        return await self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
        )

    def get_session(self, session_id: str) -> Session | None:
        """Return session model by id, or `None` when absent."""

        return self._session_manager.get_session(session_id)

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
            timeout_seconds=timeout_seconds if timeout_seconds is not None else self._llm_config.timeout_seconds,
        )

        active_llm_client = create_llm_client(config=next_config)
        self._llm_config = next_config
        self._llm_client = active_llm_client
        self._loop.bind_llm_client(
            llm_client=active_llm_client,
            model=next_config.model,
        )
        self._compaction_summarizer = CompactionSummarizer(
            llm_client=active_llm_client,
            model=self._compaction_settings.summary_model or next_config.model,
        )
        return self._llm_config

    def bind_tool_registry(self, tool_registry: ToolRegistryLike | None) -> None:
        """Bind or unbind runtime tool registry."""

        self._loop.bind_tool_registry(tool_registry)

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

    async def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        """Create a session and emit `session_start` observe hook."""

        session = self._session_manager.create_session(
            workspace_root=workspace_root,
            title=title,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=metadata,
        )
        hook_ctx = self._build_hook_context(session_id=session.session_id)
        await self._dispatch_observe(
            "session_start",
            {"session_id": session.session_id},
            hook_ctx,
        )
        return session

    def _resolve_session_available_skills(self, session: Session) -> tuple[SkillMetadata, ...]:
        if session.skills is None:
            return self._loop.available_skills
        if not session.skills:
            return ()
        return resolve_available_skills(
            workspace_root=session.workspace_root,
            include_names=session.skills,
            config_resolver=self._config_resolver,
        )

    def _resolve_session_available_tools(self, session: Session) -> tuple[ToolSpec, ...]:
        if session.tool_allowlist is None:
            # No per-session allowlist: apply product default_tool_ids gate when present.
            # When default_tool_ids is None the platform default (all registry tools) is used.
            all_specs = self._loop.active_tool_specs()
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(session.tool_allowlist)
        return tuple(tool for tool in self._loop.active_tool_specs() if tool.name in requested)

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
            hook_ctx.logger.warn("hook intercept dispatch failed", event=event, error=str(exc))
            return dict(payload), False
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=dispatch_result.diagnostics)
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
            hook_ctx.logger.warn("hook observe dispatch failed", event=event, error=str(exc))
            return
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=diagnostics)

    @staticmethod
    def _log_hook_diagnostics(
        hook_ctx: HookContext,
        *,
        event: str,
        diagnostics: tuple[HookExecution, ...],
    ) -> None:
        for item in diagnostics:
            if item.status == "ok":
                continue
            hook_ctx.logger.warn(
                "hook execution isolated",
                event=event,
                hook_id=item.hook_id,
                status=item.status,
                duration_ms=item.duration_ms,
                error=item.error,
            )

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
        return HookContext(
            session_id=session_id,
            turn_id=turn_id,
            repo_root=self._repo_root,
            metadata=dict(metadata or {}),
            model_caller=self._call_hook_model,
            session_event_publisher=session_event_publisher,
        )

    def _call_hook_model(self, call: HookModelCall) -> HookModelResult:
        """Execute one hook-initiated model call under runtime configuration."""

        normalized_session = call.session_id.strip()
        if not normalized_session:
            raise ValueError("session_id is required")
        model = (call.model or self._llm_config.model).strip()
        if not model:
            raise ValueError("model is required")
        response = self._llm_client.generate(
            LLMGenerateRequest(
                session_id=normalized_session,
                model=model,
                stream=False,
                messages=(
                    LLMMessage(role="system", content=call.system_prompt),
                    LLMMessage(role="user", content=call.user_prompt),
                ),
                metadata=dict(call.metadata),
            )
        )
        return HookModelResult(
            model=response.model,
            content=response.message.content,
            raw=response.raw,
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
        hook_ctx: HookContext,
        system_prompt_override: str | None,
        available_skills_override: tuple[SkillMetadata, ...] | None,
        available_tools_override: tuple[ToolSpec, ...] | None,
        llm_session_id: str | None,
        session_created_at: str,
        current_working_directory_override: Path | None,
        controller: RunController | None = None,
    ) -> TurnResult:
        session_file_state = self._session_file_states.setdefault(session_id, SessionFileState())
        return await self._loop.run(
            AgentState(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history_messages=history,
                input_parts=input_parts,
                user_text=user_text,
            ),
            controller=controller,
            hook_ctx=hook_ctx,
            system_prompt_override=system_prompt_override,
            available_skills_override=available_skills_override,
            available_tools_override=available_tools_override,
            llm_session_id=llm_session_id,
            session_created_at=session_created_at,
            current_working_directory_override=current_working_directory_override,
            session_file_state=session_file_state,
        )

    async def _preflight_compaction(
        self,
        *,
        session_id: str,
        history: tuple[Message, ...],
    ) -> CompactionResult | None:
        if not self._compaction_settings.enabled:
            return None
        estimated_tokens = _estimate_context_tokens(history=history)
        decision = should_compact(
            context_tokens=estimated_tokens,
            context_window=self._compaction_settings.context_window,
            reserve_tokens=self._compaction_settings.reserve_tokens,
        )
        if decision is None:
            return None
        return await self._compact_session(session_id=session_id, reason=decision.reason)

    async def _post_turn_check_overflow(self, *, session_id: str, error: ModelError) -> bool:
        if not self._compaction_settings.enabled:
            return False
        if not _is_context_overflow_error(error):
            return False
        result = await self._compact_session(session_id=session_id, reason=CompactionReason.OVERFLOW)
        return result is not None

    async def _compact_session(
        self,
        *,
        session_id: str,
        reason: CompactionReason,
    ) -> CompactionResult | None:
        entries = self._session_manager.list_entries(session_id)
        plan = self._compaction_planner.plan(events=entries, reason=reason)
        if plan is None:
            return None

        session = self._session_manager.get_session(session_id)
        rendered_system_prompt: str | None = None
        if session is not None:
            active_skills = self._resolve_session_available_skills(session)
            active_tools = self._resolve_session_available_tools(session)
            rendered_system_prompt = build_system_prompt(
                system_prompt=session.system_prompt or self._loop._system_prompt,
                available_skills=active_skills,
                available_tools=active_tools,
                current_working_directory=session.workspace_root,
            )

        dropped_messages = tuple(_message_from_turn_entry(entry) for entry in plan.dropped_events)
        summary = self._compaction_summarizer.summarize(
            session_id=session_id,
            system_prompt=rendered_system_prompt,
            dropped_messages=dropped_messages,
        )

        # Post-compact file restore: read up to 5 most recently accessed files.
        file_state = self._session_file_states.get(session_id)
        restored_files: list[str] = []
        if file_state is not None:
            for state in reversed(file_state._states.values()):
                content = _read_file_slice(
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
        messages = list(self._session_manager.list_turn_messages(session_id))
        if messages and messages[-1].message_id == message_id:
            messages.pop()
        return tuple(messages)

    def _append_turn_events(self, *, session_id: str, turn_id: str, turn_result: TurnResult) -> None:
        call_by_id = {item.call_id: item for item in turn_result.tool_calls}
        result_by_id = {item.call_id: item for item in turn_result.tool_results}
        emitted_call_ids: set[str] = set()
        emitted_result_ids: set[str] = set()

        for assistant_message in turn_result.messages:
            tool_call_ids = _extract_tool_call_ids(assistant_message.metadata)
            if not tool_call_ids:
                self._session_manager.append_turn_message(
                    session_id,
                    turn_id=turn_id,
                    role=assistant_message.role,
                    content=assistant_message.content,
                    message_id=assistant_message.message_id,
                    metadata=assistant_message.metadata,
                )
                continue

            if assistant_message.content:
                self._session_manager.append_turn_message(
                    session_id,
                    turn_id=turn_id,
                    role=assistant_message.role,
                    content=assistant_message.content,
                    message_id=assistant_message.message_id,
                    metadata=_without_tool_calls_metadata(assistant_message.metadata),
                )

            for call_id in tool_call_ids:
                tool_call = call_by_id.get(call_id)
                if tool_call is None:
                    continue
                self._append_tool_call_event(session_id=session_id, turn_id=turn_id, tool_call=tool_call)
                emitted_call_ids.add(call_id)
                tool_result = result_by_id.get(call_id)
                if tool_result is None:
                    continue
                self._append_tool_result_event(session_id=session_id, turn_id=turn_id, tool_result=tool_result)
                emitted_result_ids.add(call_id)

        for tool_call in turn_result.tool_calls:
            if tool_call.call_id in emitted_call_ids:
                continue
            self._append_tool_call_event(session_id=session_id, turn_id=turn_id, tool_call=tool_call)
            emitted_call_ids.add(tool_call.call_id)
            tool_result = result_by_id.get(tool_call.call_id)
            if tool_result is None or tool_result.call_id in emitted_result_ids:
                continue
            self._append_tool_result_event(session_id=session_id, turn_id=turn_id, tool_result=tool_result)
            emitted_result_ids.add(tool_result.call_id)

        for tool_result in turn_result.tool_results:
            if tool_result.call_id in emitted_result_ids:
                continue
            self._append_tool_result_event(session_id=session_id, turn_id=turn_id, tool_result=tool_result)
            emitted_result_ids.add(tool_result.call_id)

    def _append_tool_call_event(self, *, session_id: str, turn_id: str, tool_call: ToolCall) -> None:
        self._session_manager.append_turn_message(
            session_id,
            turn_id=turn_id,
            role="assistant",
            content="",
            message_id=make_message_id(),
            metadata={
                "tool_phase": "call",
                "tool_call_id": tool_call.call_id,
                "tool_calls": [
                    {
                        "call_id": tool_call.call_id,
                        "name": tool_call.name,
                        "arguments": dict(tool_call.arguments),
                    }
                ],
            },
        )

    def _append_tool_result_event(self, *, session_id: str, turn_id: str, tool_result: ToolResult) -> None:
        content = tool_result.content if tool_result.content is not None else ""
        self._session_manager.append_turn_message(
            session_id,
            turn_id=turn_id,
            role="tool",
            content=content,
            message_id=make_message_id(),
            metadata={
                "tool_phase": "result",
                "tool_call_id": tool_result.call_id,
            },
        )


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


def _message_from_turn_entry(entry: SessionEntry) -> Message:
    return Message(
        message_id=str(entry.data.get("message_id", "")),
        role=str(entry.data.get("role", "")),
        content=str(entry.data.get("content", "")),
    )


def _extract_tool_call_ids(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    raw_calls = metadata.get("tool_calls")
    if not isinstance(raw_calls, list):
        return ()
    call_ids: list[str] = []
    for item in raw_calls:
        if not isinstance(item, Mapping):
            continue
        call_id = item.get("call_id")
        if isinstance(call_id, str) and call_id:
            call_ids.append(call_id)
    return tuple(call_ids)


def _without_tool_calls_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(metadata)
    copied.pop("tool_calls", None)
    return copied


def _read_file_slice(
    file_path: str,
    offset: int | None,
    limit: int | None,
) -> str | None:
    """Read a file or a slice of it (offset/limit are 1-indexed line numbers)."""
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if offset is None or limit is None:
            return text
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        return "\n".join(lines[start:end])
    except (OSError, ValueError):
        return None


