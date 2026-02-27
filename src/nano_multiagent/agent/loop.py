import asyncio
from typing import Any, Mapping

from nano_multiagent.core.ids import make_message_id
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.runner import HookExecution, HookRunner
from nano_multiagent.llm.interfaces import LLMClient, LLMGenerateRequest
from nano_multiagent.skills.registry import SkillMetadata

from .policies import AgentPolicies
from .prompting import DEFAULT_SYSTEM_PROMPT, build_prompt_messages
from .state import AgentState


class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        policies: AgentPolicies | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        hook_runner: HookRunner | None = None,
        available_skills: tuple[SkillMetadata, ...] = (),
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._policies = policies or AgentPolicies()
        self._system_prompt = system_prompt
        self._hook_runner = hook_runner
        self._available_skills = available_skills

    def run(
        self,
        state: AgentState,
        *,
        hook_ctx: HookContext | None = None,
        system_prompt_override: str | None = None,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        active_hook_ctx = hook_ctx or HookContext(session_id=state.session_id, turn_id=state.turn_id)
        self._dispatch_observe(
            "turn_start",
            {"session_id": state.session_id, "turn_id": state.turn_id, "turn_count": state.turn_count},
            active_hook_ctx,
        )

        stop_reason = "error"
        completed = False
        self._policies.ensure_turn_allowed(turn_count=state.turn_count)
        history = self._policies.truncate_history(state.history_messages)
        prompt_messages = build_prompt_messages(
            history_messages=history,
            user_text=state.user_text,
            system_prompt=system_prompt_override or self._system_prompt,
            available_skills=self._available_skills,
        )

        try:
            response = self._llm_client.generate(
                LLMGenerateRequest(
                    session_id=llm_session_id or state.session_id,
                    model=self._model,
                    messages=prompt_messages,
                    stream=False,
                )
            )

            assistant_message = Message(
                message_id=make_message_id(),
                role=response.message.role,
                content=response.message.content,
                name=response.message.name,
            )

            self._dispatch_observe(
                "message_start",
                {
                    "session_id": state.session_id,
                    "turn_id": state.turn_id,
                    "message_id": assistant_message.message_id,
                    "role": assistant_message.role,
                },
                active_hook_ctx,
            )
            self._dispatch_observe(
                "message_update",
                {
                    "session_id": state.session_id,
                    "turn_id": state.turn_id,
                    "message_id": assistant_message.message_id,
                    "delta": assistant_message.content,
                },
                active_hook_ctx,
            )
            self._dispatch_observe(
                "message_end",
                {
                    "session_id": state.session_id,
                    "turn_id": state.turn_id,
                    "message_id": assistant_message.message_id,
                    "content": assistant_message.content,
                    "role": assistant_message.role,
                },
                active_hook_ctx,
            )

            completed = True
            stop_reason = response.finish_reason or "completed"
            return TurnResult(
                session_id=state.session_id,
                turn_id=state.turn_id,
                messages=(assistant_message,),
                completed=completed,
                stop_reason=stop_reason,
            )
        finally:
            self._dispatch_observe(
                "turn_end",
                {
                    "session_id": state.session_id,
                    "turn_id": state.turn_id,
                    "completed": completed,
                    "stop_reason": stop_reason,
                },
                active_hook_ctx,
            )

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
