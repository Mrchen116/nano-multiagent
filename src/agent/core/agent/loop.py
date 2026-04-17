"""Agent turn loop that mediates model calls, tools, and hooks."""

import asyncio
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from agent.core.ids import make_message_id, make_tool_call_id
from agent.core.types import Message, TokenUsage, ToolCall, ToolResult, ToolSpec, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from agent.core.skills.registry import SkillMetadata

from .policies import AgentPolicies
from .prompting import build_prompt_messages
from .run_control import RunController
from .state import AgentState
from .tool_executor import ToolExecutor, partition_into_batches


class ToolRegistryLike(Protocol):
    def list_specs(self) -> tuple[ToolSpec, ...]:
        ...

    def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: HookContext | None = None,
    ) -> Mapping[str, Any]:
        ...


class AgentLoop:
    """Execute one turn with optional tool-calling iterations."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        policies: AgentPolicies | None = None,
        system_prompt: str | None = None,
        hook_runner: HookRunner | None = None,
        available_skills: tuple[SkillMetadata, ...] = (),
        available_tools: tuple[ToolSpec, ...] | None = None,
        tool_registry: ToolRegistryLike | None = None,
        current_working_directory: Path | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._policies = policies or AgentPolicies()
        self._system_prompt = system_prompt or ""
        self._hook_runner = hook_runner
        self._available_skills = available_skills
        self._available_tools = available_tools
        self._tool_registry = tool_registry
        self._current_working_directory = current_working_directory

    @property
    def available_skills(self) -> tuple[SkillMetadata, ...]:
        return self._available_skills

    def bind_tool_registry(self, tool_registry: ToolRegistryLike | None) -> None:
        """Hot-swap tool registry used by subsequent turns."""

        self._tool_registry = tool_registry

    def bind_llm_client(self, *, llm_client: LLMClient, model: str) -> None:
        """Hot-swap LLM client/model without rebuilding runtime."""

        self._llm_client = llm_client
        self._model = model

    async def run(
        self,
        state: AgentState,
        *,
        controller: RunController | None = None,
        hook_ctx: HookContext | None = None,
        system_prompt_override: str | None = None,
        available_skills_override: tuple[SkillMetadata, ...] | None = None,
        available_tools_override: tuple[ToolSpec, ...] | None = None,
        llm_session_id: str | None = None,
        session_created_at: str | None = None,
        current_working_directory_override: Path | None = None,
    ) -> TurnResult:
        """Run one user turn until completion or terminal stop reason.

        Args:
            state: Immutable per-turn state.
            hook_ctx: Hook execution context; derived from state when omitted.
            system_prompt_override: Optional system prompt override for this turn.
            llm_session_id: Optional provider session id override.
            session_created_at: Optional session-level timestamp used to keep
                system prompt time stable across turns in one session.

        Returns:
            Turn result containing assistant messages, tool calls/results, and stop reason.

        Raises:
            ModelError: Propagated from the LLM client when provider calls fail.
            PolicyViolation: When turn/tool-call policies are exceeded.
        """

        active_hook_ctx = hook_ctx or HookContext(session_id=state.session_id, turn_id=state.turn_id)
        run_id = _resolve_hook_run_id(active_hook_ctx)
        await self._dispatch_observe(
            "turn_start",
            _with_optional_run_id(
                {
                    "session_id": state.session_id,
                    "turn_id": state.turn_id,
                    "turn_count": state.turn_count,
                },
                run_id=run_id,
            ),
            active_hook_ctx,
        )

        stop_reason = "error"
        completed = False

        active_tools = self.active_tool_specs() if available_tools_override is None else available_tools_override
        active_skills = self._available_skills if available_skills_override is None else available_skills_override
        llm_messages = list(
            build_prompt_messages(
                history_messages=state.history_messages,
                user_text=state.user_text,
                system_prompt=system_prompt_override or self._system_prompt,
                available_skills=active_skills,
                available_tools=active_tools,
                current_datetime=session_created_at,
                current_working_directory=current_working_directory_override or self._current_working_directory,
            )
        )

        assistant_messages: list[Message] = []
        tool_calls: list[ToolCall] = []
        tool_results: list[ToolResult] = []
        turn_usage: TokenUsage | None = None
        latest_usage: TokenUsage | None = None
        tool_executor = ToolExecutor()

        # Build name → is_concurrency_safe lookup from the active tool specs.
        concurrency_map: dict[str, bool] = {
            spec.name: spec.is_concurrency_safe for spec in active_tools
        }

        try:
            # Runtime loop strategy:
            # 1) If model returns plain assistant text, finish current turn.
            # 2) If model returns tool calls, partition them into batches by
            #    concurrency safety, execute each batch, then continue.
            # 3) If tools are unavailable, stop with explicit terminal reason instead
            #    of silently dropping tool calls.
            # 4) Before each LLM call, drain any pending injected messages.
            # 5) After each tool batch, check for a force-interrupt signal.
            while True:
                # Drain pending messages injected via RunController (round-boundary injection).
                if controller is not None:
                    for pending_msg in controller.drain_pending():
                        llm_messages.append(pending_msg)

                response = self._llm_client.generate(
                    LLMGenerateRequest(
                        session_id=llm_session_id or state.session_id,
                        model=self._model,
                        messages=tuple(llm_messages),
                        stream=False,
                        tools=active_tools,
                    )
                )
                turn_usage = _accumulate_usage(turn_usage, response.usage)
                latest_usage = response.usage
                normalized_calls = tuple(_normalize_tool_call(item) for item in response.message.tool_calls)
                normalized_response_message = LLMMessage(
                    role=response.message.role,
                    content=response.message.content,
                    name=response.message.name,
                    tool_call_id=response.message.tool_call_id,
                    tool_calls=_as_llm_tool_calls(normalized_calls),
                )

                assistant_message = Message(
                    message_id=make_message_id(),
                    role=response.message.role,
                    content=response.message.content,
                    name=response.message.name,
                    metadata=_assistant_metadata_from_tool_calls(normalized_calls),
                )
                assistant_messages.append(assistant_message)
                llm_messages.append(normalized_response_message)

                await self._dispatch_observe(
                    "message_start",
                    _with_optional_run_id(
                        {
                            "session_id": state.session_id,
                            "turn_id": state.turn_id,
                            "message_id": assistant_message.message_id,
                            "role": assistant_message.role,
                        },
                        run_id=run_id,
                    ),
                    active_hook_ctx,
                )
                await self._dispatch_observe(
                    "message_update",
                    _with_optional_run_id(
                        {
                            "session_id": state.session_id,
                            "turn_id": state.turn_id,
                            "message_id": assistant_message.message_id,
                            "delta": assistant_message.content,
                        },
                        run_id=run_id,
                    ),
                    active_hook_ctx,
                )
                await self._dispatch_observe(
                    "message_end",
                    _with_optional_run_id(
                        {
                            "session_id": state.session_id,
                            "turn_id": state.turn_id,
                            "message_id": assistant_message.message_id,
                            "content": assistant_message.content,
                            "role": assistant_message.role,
                        },
                        run_id=run_id,
                    ),
                    active_hook_ctx,
                )

                if not normalized_calls:
                    completed = True
                    stop_reason = response.finish_reason or "completed"
                    return TurnResult(
                        session_id=state.session_id,
                        turn_id=state.turn_id,
                        messages=tuple(assistant_messages),
                        tool_calls=tuple(tool_calls),
                        tool_results=tuple(tool_results),
                        completed=completed,
                        stop_reason=stop_reason,
                        usage=turn_usage,
                    )

                for parsed_call in normalized_calls:
                    tool_calls.append(parsed_call)
                    self._policies.ensure_tool_calls_allowed(tool_call_count=len(tool_calls))

                if self._tool_registry is None:
                    completed = True
                    stop_reason = "tool_registry_unavailable"
                    return TurnResult(
                        session_id=state.session_id,
                        turn_id=state.turn_id,
                        messages=tuple(assistant_messages),
                        tool_calls=tuple(tool_calls),
                        tool_results=tuple(tool_results),
                        completed=completed,
                        stop_reason=stop_reason,
                        usage=turn_usage,
                    )

                async def _run_one_call(parsed_call: ToolCall) -> ToolResult:
                    tool_hook_ctx = HookContext(
                        session_id=active_hook_ctx.session_id,
                        turn_id=active_hook_ctx.turn_id,
                        repo_root=active_hook_ctx.repo_root,
                        metadata={**dict(active_hook_ctx.metadata), "tool_call_id": parsed_call.call_id},
                        model_caller=active_hook_ctx.model_caller,
                        session_event_publisher=active_hook_ctx.session_event_publisher,
                    )
                    await self._dispatch_observe(
                        "tool_call",
                        _with_optional_run_id(
                            {
                                "session_id": state.session_id,
                                "turn_id": state.turn_id,
                                "call_id": parsed_call.call_id,
                                "name": parsed_call.name,
                                "arguments": dict(parsed_call.arguments),
                            },
                            run_id=run_id,
                        ),
                        tool_hook_ctx,
                    )
                    result_payload, error_text = await self._execute_tool_call(
                        parsed_call,
                        hook_ctx=tool_hook_ctx,
                    )
                    result = ToolResult(
                        call_id=parsed_call.call_id,
                        name=parsed_call.name,
                        output=result_payload,
                        error=error_text,
                    )
                    await self._dispatch_observe(
                        "tool_result",
                        _with_optional_run_id(
                            {
                                "session_id": state.session_id,
                                "turn_id": state.turn_id,
                                "call_id": result.call_id,
                                "name": result.name,
                                "output": result.output,
                                "error": result.error,
                            },
                            run_id=run_id,
                        ),
                        tool_hook_ctx,
                    )
                    return result

                batches = partition_into_batches(normalized_calls, concurrency_map)
                interrupted = False
                executed_call_ids: set[str] = set()

                for batch in batches:
                    batch_results = await tool_executor.execute(batch, _run_one_call)
                    for result in batch_results:
                        tool_results.append(result)
                        executed_call_ids.add(result.call_id)
                        llm_messages.append(
                            LLMMessage(
                                role="tool",
                                content=_serialize_tool_result_content(result),
                                tool_call_id=result.call_id,
                            )
                        )

                    # After each batch, check for a force-interrupt signal.
                    if controller is not None and controller.is_aborted:
                        for remaining_call in normalized_calls:
                            if remaining_call.call_id not in executed_call_ids:
                                interrupted_result = ToolResult(
                                    call_id=remaining_call.call_id,
                                    name=remaining_call.name,
                                    error="interrupted",
                                )
                                tool_results.append(interrupted_result)
                                llm_messages.append(
                                    LLMMessage(
                                        role="tool",
                                        content=_serialize_tool_result_content(interrupted_result),
                                        tool_call_id=interrupted_result.call_id,
                                    )
                                )
                        stop_reason = "interrupted"
                        interrupted = True
                        break

                if interrupted:
                    break
        finally:
            turn_end_payload: dict[str, Any] = {
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "completed": completed,
                "stop_reason": stop_reason,
            }
            if run_id is not None:
                turn_end_payload["run_id"] = run_id
            if turn_usage is not None:
                turn_end_payload["usage"] = {
                    "prompt_tokens": turn_usage.prompt_tokens,
                    "completion_tokens": turn_usage.completion_tokens,
                    "total_tokens": turn_usage.total_tokens,
                }
            if latest_usage is not None:
                turn_end_payload["latest_usage"] = {
                    "prompt_tokens": latest_usage.prompt_tokens,
                    "completion_tokens": latest_usage.completion_tokens,
                    "total_tokens": latest_usage.total_tokens,
                }
            await self._dispatch_observe(
                "turn_end",
                turn_end_payload,
                active_hook_ctx,
            )

    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
        *,
        hook_ctx: HookContext,
    ) -> tuple[Any, str | None]:
        if self._tool_registry is None:
            return None, "tool registry is unavailable"
        try:
            output = await asyncio.to_thread(
                self._tool_registry.execute,
                tool_call.name,
                tool_call.arguments,
                hook_context=hook_ctx,
            )
            return output, None
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            return None, str(exc)

    def active_tool_specs(self) -> tuple[ToolSpec, ...]:
        if self._tool_registry is not None:
            return self._tool_registry.list_specs()
        if self._available_tools is not None:
            return self._available_tools
        return ()

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


def _normalize_tool_call(tool_call: LLMToolCall) -> ToolCall:
    """Normalize provider tool call payload into core tool call contract."""

    call_id = tool_call.call_id.strip() if isinstance(tool_call.call_id, str) else ""
    if not call_id:
        call_id = make_tool_call_id()
    return ToolCall(
        call_id=call_id,
        name=tool_call.name,
        arguments=dict(tool_call.arguments),
    )


def _assistant_metadata_from_tool_calls(tool_calls: tuple[ToolCall, ...]) -> Mapping[str, Any]:
    """Serialize tool calls into assistant metadata persisted in session history."""

    if not tool_calls:
        return {}
    return {
        "tool_calls": [
            {
                "call_id": tool_call.call_id,
                "name": tool_call.name,
                "arguments": dict(tool_call.arguments),
            }
            for tool_call in tool_calls
        ]
    }


def _as_llm_tool_calls(tool_calls: tuple[ToolCall, ...]) -> tuple[LLMToolCall, ...]:
    """Convert normalized tool calls back to LLM-layer tool call objects."""

    return tuple(
        LLMToolCall(
            call_id=tool_call.call_id,
            name=tool_call.name,
            arguments=dict(tool_call.arguments),
        )
        for tool_call in tool_calls
    )


def _serialize_tool_result_content(result: ToolResult) -> str:
    """Serialize tool result into tool-message content delivered back to model."""

    payload: dict[str, Any] = {
        "call_id": result.call_id,
        "name": result.name,
    }
    if result.error is not None:
        payload["error"] = result.error
    else:
        payload["output"] = result.output
    try:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(payload)


def _accumulate_usage(current: TokenUsage | None, update: TokenUsage | None) -> TokenUsage | None:
    if update is None:
        return current
    if current is None:
        return update
    return TokenUsage(
        prompt_tokens=current.prompt_tokens + update.prompt_tokens,
        completion_tokens=current.completion_tokens + update.completion_tokens,
        total_tokens=current.total_tokens + update.total_tokens,
    )


def _resolve_hook_run_id(hook_ctx: HookContext) -> str | None:
    run_id = hook_ctx.metadata.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _with_optional_run_id(payload: Mapping[str, Any], *, run_id: str | None) -> dict[str, Any]:
    resolved = dict(payload)
    if run_id is not None:
        resolved["run_id"] = run_id
    return resolved


