"""High-level runtime orchestration over sessions, hooks, loop, and compaction."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

from agent.core.errors import ModelError
from agent.core.ids import make_message_id, make_turn_id
from agent.core.types import Message, TokenUsage, ToolCall, ToolResult, ToolSpec, TurnResult
from agent.core.hooks.context import HookContext, HookModelCall, HookModelResult
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage
from agent.core.session.entries import SessionEntry
from agent.core.session.jsonl_store import SessionConfig
from agent.core.session.manager import SessionManager
from agent.core.session.models import Session
from agent.core.skills import SkillMetadata, resolve_available_skills
from agent.core.skills.discovery import SkillRootResolver
from agent.core.tools.result_budget import ToolResultCompressor
from agent.core.tools.session_file_state import SessionFileState, read_file_slice

from .compaction.applier import CompactionApplier
from .compaction.planner import CompactionPlanner
from .compaction.policy import should_compact
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
        self._tool_registry = tool_registry
        self._session_file_states: dict[str, SessionFileState] = {}
        # In-memory session state: primary data source during normal operation.
        self._session_histories: dict[str, list[Message]] = {}
        self._session_configs: dict[str, SessionConfig] = {}
        self._session_paths: dict[str, Path] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
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
        self._compaction_summarizer = CompactionSummarizer(
            fork=self._context_fork,
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
        )

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
    ) -> TurnResult:
        """Execute one turn for an existing session.

        Args:
            session_id: Target session id.
            parts: Structured input parts (`text` or `image`).
            stream: Reserved compatibility flag (currently ignored).
            llm_session_id: Optional provider session id override.
            parent_session_id: Optional parent session id for subagent path resolution.

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
    ) -> TurnResult:
        """Internal run implementation (assumes session lock is held)."""

        # --- Cache-first load: miss reads JSONL once, hit uses memory ---
        if session_id not in self._session_histories:
            path = self._session_manager.store.resolve_path(
                session_id, parent_session_id=parent_session_id
            )
            try:
                result = self._session_manager.load(session_id, parent_session_id=parent_session_id)
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
        session_available_skills = self._resolve_session_available_skills_from_config(config)
        session_available_tools = self._resolve_session_available_tools_from_config(config)
        frozen_system_prompt = config.system_prompt

        input_parts = parse_input_parts(parts)
        user_text = render_user_text(input_parts)
        if not user_text:
            raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        hook_metadata: dict[str, Any] = dict(config.metadata) if isinstance(config.metadata, Mapping) else {}
        hook_metadata["cwd"] = str(session_workspace_root)
        hook_metadata["context_window"] = self._compaction_settings.context_window
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

        turn_count = sum(1 for message in history if message.role == "user")
        user_message_id = make_message_id()

        user_msg = Message(
            message_id=user_message_id,
            parent_message_id=history[-1].message_id if history else None,
            role="user",
            content=user_text,
        )
        history.append(user_msg)
        self._session_manager.writer.enqueue(path, _message_to_entry(user_msg, session_id))
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
                    parent_message_id=loop_history[-1].message_id if loop_history else None,
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
                llm_session_id=llm_session_id,
                session_created_at=session_created_at,
                current_working_directory_override=session_workspace_root,
                available_skills_override=() if use_frozen_system_prompt else session_available_skills,
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
                    self._session_manager.writer.enqueue(path, {
                        "type": "compact_boundary",
                        "session_id": session_id,
                        "timestamp": _utc_now_iso(),
                        "summary_uuid": msg.message_id,
                        "data": {
                            "reason": msg.metadata.get("compact_reason", "threshold"),
                            "restored_files": msg.metadata.get("restored_files", []),
                        },
                    })
                entry = _message_to_entry(msg, session_id)
                if msg.role == "tool":
                    self._session_manager.writer.enqueue(path, entry)
                    await self._session_manager.writer.flush_async()
                else:
                    self._session_manager.writer.enqueue(path, entry)
            await self._session_manager.writer.flush_async()
        except ModelError:
            await self._session_manager.writer.flush_async()
            raise

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
            background_registrations = self._hook_runner.registry.background_handlers_for("agent_end")
            if background_registrations:
                from agent.core.agent.context_fork import make_fork_conversation

                # Build fork_conversation using the current session's rendered state.
                # We resolve the fork tools and system prompt from the session config.
                fork_system_prompt: str | None = None
                fork_active_tools: tuple[ToolSpec, ...] = ()
                if session_id in self._session_configs:
                    fork_config = self._session_configs[session_id]
                    fork_active_skills = self._resolve_session_available_skills_from_config(fork_config)
                    fork_active_tools = self._resolve_session_available_tools_from_config(fork_config)
                    fork_system_prompt = build_system_prompt(
                        system_prompt=fork_config.system_prompt or self._loop._system_prompt,
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
                )

                background_hook_ctx = HookContext(
                    session_id=hook_ctx.session_id,
                    turn_id=hook_ctx.turn_id,
                    repo_root=hook_ctx.repo_root,
                    metadata=dict(hook_ctx.metadata),
                    model_caller=hook_ctx.model_caller,
                    session_event_publisher=hook_ctx.session_event_publisher,
                    fork_conversation=fork_fn,
                )
                self._hook_runner.dispatch_background("agent_end", agent_end_payload, background_hook_ctx)

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
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
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
        """
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

    async def fork_session(self, source_session_id: str) -> Session:
        """Fork a session: create a new session with an independent copy of source history.

        The fork copies the linear conversation chain from the source session,
        re-stamping all message UUIDs and recalculating parent_uuid links.
        The new session has its own JSONL file and in-memory history.
        """

        # Ensure source is loaded into memory
        if source_session_id not in self._session_histories:
            result = self._session_manager.load(source_session_id)
            self._session_histories[source_session_id] = list(result.messages)
            self._session_configs[source_session_id] = result.config
            self._session_paths[source_session_id] = self._session_manager.store.resolve_path(source_session_id)

        source_config = self._session_configs[source_session_id]
        source_history = self._session_histories[source_session_id]

        # Acquire source lock to prevent concurrent modification during fork
        source_lock = self._session_locks.get(source_session_id)
        if source_lock:
            async with source_lock:
                return await self._fork_locked(source_session_id, source_config, list(source_history))
        return await self._fork_locked(source_session_id, source_config, list(source_history))

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
        new_path = self._session_manager.store.resolve_path(new_session_id)

        # Re-stamp messages: new UUIDs, recalculated parent chain
        if source_history:
            old_to_new_uuid: dict[str, str] = {}
            new_history: list[Message] = []

            for msg in source_history:
                new_uuid = make_message_id()
                old_to_new_uuid[msg.message_id] = new_uuid

                old_parent = msg.parent_message_id
                new_parent = old_to_new_uuid.get(old_parent) if old_parent else None

                new_msg = Message(
                    message_id=new_uuid,
                    role=msg.role,
                    content=msg.content,
                    parent_message_id=new_parent,
                    group_id=old_to_new_uuid.get(msg.group_id) if msg.group_id else None,
                    tool_call_id=msg.tool_call_id,
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

    def _resolve_session_available_skills_from_config(self, config: SessionConfig) -> tuple[SkillMetadata, ...]:
        if config.skills is None:
            return self._loop.available_skills
        if not config.skills:
            return ()
        return resolve_available_skills(
            workspace_root=config.workspace_root,
            include_names=config.skills,
            config_resolver=self._config_resolver,
        )

    def _resolve_session_available_tools(self, session: Session) -> tuple[ToolSpec, ...]:
        if session.tool_allowlist is None:
            all_specs = self._loop.active_tool_specs()
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(session.tool_allowlist)
        return tuple(tool for tool in self._loop.active_tool_specs() if tool.name in requested)

    def _resolve_session_available_tools_from_config(self, config: SessionConfig) -> tuple[ToolSpec, ...]:
        if config.tool_allowlist is None:
            all_specs = self._loop.active_tool_specs()
            default_ids = self._default_tool_ids
            if default_ids is None:
                return all_specs
            allowed_set = set(default_ids)
            return tuple(spec for spec in all_specs if spec.name in allowed_set)
        requested = set(config.tool_allowlist)
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
                metadata=dict(call.metadata),
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
        available_skills_override: tuple[SkillMetadata, ...] | None,
        available_tools_override: tuple[ToolSpec, ...] | None,
        llm_session_id: str | None,
        session_created_at: str,
        current_working_directory_override: Path | None,
        controller: RunController | None = None,
    ):
        session_file_state = self._session_file_states.setdefault(session_id, SessionFileState())
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
            available_skills_override=available_skills_override,
            available_tools_override=available_tools_override,
            llm_session_id=llm_session_id,
            session_created_at=session_created_at,
            current_working_directory_override=current_working_directory_override,
            session_file_state=session_file_state,
        ):
            yield msg

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

        config = self._session_configs.get(session_id)
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

        dropped_messages = tuple(message_from_turn_entry(entry) for entry in plan.dropped_events)
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
            self._session_manager.writer.enqueue(path, _message_to_entry(summary_msg, session_id))

            self._session_manager.writer.enqueue(path, {
                "type": "compact_boundary",
                "session_id": session_id,
                "timestamp": _utc_now_iso(),
                "summary_uuid": summary_msg.message_id,
                "data": {"reason": reason.value, "restored_files": list(restored_files)},
            })
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


def build_turn_result(session_id: str, turn_id: str, messages: list[Message]) -> TurnResult:
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
    return entry


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# _message_from_turn_entry and _read_file_slice migrated to break loop->runtime cycle.
# See session/entries.py and tools/session_file_state.py respectively.


