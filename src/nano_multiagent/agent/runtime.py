import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.ids import make_message_id, make_turn_id
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.runner import HookExecution, HookRunner
from nano_multiagent.llm.factory import LLMFactoryConfig, create_llm_client
from nano_multiagent.llm.interfaces import LLMClient
from nano_multiagent.session.entries import SessionEntry
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.models import Session
from nano_multiagent.skills.registry import SkillMetadata
from nano_multiagent.skills.workspace import resolve_available_skills

from .compaction.applier import CompactionApplier
from .compaction.planner import CompactionPlanner
from .compaction.policy import should_compact
from .compaction.summarizer import CompactionSummarizer
from .compaction.types import CompactionReason, CompactionResult, CompactionSettings
from .loop import AgentLoop
from .policies import AgentPolicies
from .skill_commands import rewrite_skill_command
from .state import AgentState, InputPart, parse_input_parts, render_user_text

if TYPE_CHECKING:
    from nano_multiagent.hooks.registry import HookRegistry


class AgentRuntime:
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
    ) -> None:
        active_llm_client = llm_client or create_llm_client()
        self._hook_runner = hook_runner
        self._repo_root = (repo_root or Path.cwd()).expanduser().resolve()
        self._model = model or LLMFactoryConfig.from_env().model
        self._compaction_settings = compaction_settings or CompactionSettings()
        resolved_skills = (
            tuple(available_skills)
            if available_skills is not None
            else resolve_available_skills(workspace_root=self._repo_root)
        )
        self._session_manager = session_manager
        self._loop = AgentLoop(
            llm_client=active_llm_client,
            model=self._model,
            policies=policies,
            hook_runner=hook_runner,
            available_skills=resolved_skills,
            current_working_directory=self._repo_root,
        )
        summary_model = self._compaction_settings.summary_model or self._model
        self._compaction_planner = CompactionPlanner(
            min_kept_messages=self._compaction_settings.min_kept_messages
        )
        self._compaction_summarizer = CompactionSummarizer(
            llm_client=active_llm_client,
            model=summary_model,
        )
        self._compaction_applier = CompactionApplier(session_manager=session_manager)

    def run(
        self,
        session_id: str,
        parts: Sequence[Mapping[str, Any]],
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        del stream  # M4 minimal runtime only supports non-stream flow.

        if self._session_manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")

        input_parts = parse_input_parts(parts)
        user_text = render_user_text(input_parts)
        if not user_text:
            raise ValueError("empty input parts are not allowed")

        turn_id = make_turn_id()
        hook_ctx = HookContext(session_id=session_id, turn_id=turn_id, repo_root=self._repo_root)

        input_payload, handled = self._dispatch_intercept(
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

        before_payload, _ = self._dispatch_intercept(
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
        if not isinstance(system_prompt_override, str):
            system_prompt_override = None

        self._dispatch_observe(
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
        self._preflight_compaction(
            session_id=session_id,
            history=history_with_current_user,
        )
        history = self._history_without_message(
            session_id=session_id,
            message_id=user_message_id,
        )

        try:
            turn_result = self._execute_loop(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history=history,
                input_parts=input_parts,
                user_text=user_text,
                hook_ctx=hook_ctx,
                system_prompt_override=system_prompt_override,
                llm_session_id=llm_session_id,
            )
        except ModelError as exc:
            if not self._post_turn_check_overflow(session_id=session_id, error=exc):
                raise
            retry_history = self._history_without_message(
                session_id=session_id,
                message_id=user_message_id,
            )
            turn_result = self._execute_loop(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history=retry_history,
                input_parts=input_parts,
                user_text=user_text,
                hook_ctx=hook_ctx,
                system_prompt_override=system_prompt_override,
                llm_session_id=llm_session_id,
            )

        for assistant_message in turn_result.messages:
            self._session_manager.append_turn_message(
                session_id,
                turn_id=turn_id,
                role=assistant_message.role,
                content=assistant_message.content,
                message_id=assistant_message.message_id,
            )
        self._dispatch_observe(
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

    def compact(self, session_id: str) -> CompactionResult | None:
        if self._session_manager.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        return self._compact_session(session_id=session_id, reason=CompactionReason.MANUAL)

    def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        return self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
        )

    def get_session(self, session_id: str) -> Session | None:
        return self._session_manager.get_session(session_id)

    @property
    def hook_runner(self) -> HookRunner | None:
        return self._hook_runner

    @property
    def hook_registry(self) -> "HookRegistry | None":
        if self._hook_runner is None:
            return None
        return self._hook_runner.registry

    def create_session(self, *, title: str | None = None, metadata: Mapping[str, Any] | None = None) -> Session:
        session = self._session_manager.create_session(title=title, metadata=metadata)
        hook_ctx = HookContext(session_id=session.session_id, repo_root=self._repo_root)
        self._dispatch_observe(
            "session_start",
            {"session_id": session.session_id},
            hook_ctx,
        )
        return session

    def _dispatch_intercept(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> tuple[dict[str, Any], bool]:
        if self._hook_runner is None:
            return dict(payload), False
        try:
            dispatch_result = asyncio.run(
                self._hook_runner.dispatch_intercept(
                    event,
                    payload,
                    hook_ctx,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warn("hook intercept dispatch failed", event=event, error=str(exc))
            return dict(payload), False
        self._log_hook_diagnostics(hook_ctx, event=event, diagnostics=dispatch_result.diagnostics)
        return dispatch_result.payload, dispatch_result.stopped

    def _dispatch_observe(
        self,
        event: str,
        payload: Mapping[str, Any],
        hook_ctx: HookContext,
    ) -> None:
        if self._hook_runner is None:
            return
        try:
            diagnostics = asyncio.run(
                self._hook_runner.dispatch_observe(
                    event,
                    payload,
                    hook_ctx,
                )
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

    def _execute_loop(
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
        llm_session_id: str | None,
    ) -> TurnResult:
        return self._loop.run(
            AgentState(
                session_id=session_id,
                turn_id=turn_id,
                turn_count=turn_count,
                history_messages=history,
                input_parts=input_parts,
                user_text=user_text,
            ),
            hook_ctx=hook_ctx,
            system_prompt_override=system_prompt_override,
            llm_session_id=llm_session_id,
        )

    def _preflight_compaction(
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
        return self._compact_session(session_id=session_id, reason=decision.reason)

    def _post_turn_check_overflow(self, *, session_id: str, error: ModelError) -> bool:
        if not self._compaction_settings.enabled:
            return False
        if not _is_context_overflow_error(error):
            return False
        result = self._compact_session(session_id=session_id, reason=CompactionReason.OVERFLOW)
        return result is not None

    def _compact_session(
        self,
        *,
        session_id: str,
        reason: CompactionReason,
    ) -> CompactionResult | None:
        entries = self._session_manager.list_entries(session_id)
        plan = self._compaction_planner.plan(events=entries, reason=reason)
        if plan is None:
            return None
        dropped_messages = tuple(_message_from_turn_entry(entry) for entry in plan.dropped_events)
        summary = self._compaction_summarizer.summarize(
            session_id=session_id,
            reason=reason,
            dropped_messages=dropped_messages,
        )
        result = self._compaction_applier.apply(
            session_id=session_id,
            plan=plan,
            summary=summary,
        )
        self._dispatch_observe(
            "session_compact",
            {
                "session_id": session_id,
                "reason": reason.value,
                "entry_id": result.entry_id,
                "first_kept_event_id": result.first_kept_event_id,
                "dropped_event_ids": result.dropped_event_ids,
                "kept_event_ids": result.kept_event_ids,
            },
            HookContext(session_id=session_id, repo_root=self._repo_root),
        )
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
    response_text = str(error.details.get("response", "")).lower()
    message_text = error.message.lower()
    markers = (
        "maximum context length",
        "context length exceeded",
        "context overflow",
        "too many tokens",
        "token limit",
    )
    return status_code == 400 and any(marker in response_text or marker in message_text for marker in markers)


def _message_from_turn_entry(entry: SessionEntry) -> Message:
    return Message(
        message_id=str(entry.data.get("message_id", "")),
        role=str(entry.data.get("role", "")),
        content=str(entry.data.get("content", "")),
    )
