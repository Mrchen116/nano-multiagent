"""Agent turn loop that mediates model calls, tools, and hooks."""

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Mapping, Protocol

from agent.core.ids import make_message_id, make_tool_call_id
from agent.core.types import Message, TokenUsage, ToolCall, ToolResult, ToolSpec, TurnResult
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookExecution, HookRunner
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.core.observability.tracing import span
from agent.core.skills.registry import SkillMetadata
from agent.core.tools.result_budget import DEFAULT_MAX_RESULT_SIZE_CHARS, ToolResultCompressor
from agent.core.tools.session_file_state import SessionFileState

from .policies import AgentPolicies
from .prompting import build_prompt_messages
from .run_control import RunController
from .state import AgentState
from .tool_executor import StreamingToolExecutor


class ToolRegistryLike(Protocol):
    def list_specs(self) -> tuple[ToolSpec, ...]:
        ...

    def get(self, name: str) -> Any | None:
        ...

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: HookContext | None = None,
        session_file_state: SessionFileState | None = None,
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
        system_prompt: str = "",
        hook_runner: HookRunner | None = None,
        available_skills: tuple[SkillMetadata, ...] = (),
        available_tools: tuple[ToolSpec, ...] | None = None,
        tool_registry: ToolRegistryLike | None = None,
        current_working_directory: Path | None = None,
        tool_result_compressor: Any | None = None,
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
        self._tool_result_compressor = tool_result_compressor
        self._active_session_id: str | None = None

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
        session_file_state: SessionFileState | None = None,
        max_turns: int | None = None,
    ) -> AsyncIterator[Message]:
        """Stream one user turn until completion or terminal stop reason.

        Yields:
            Message objects as they are produced:
            - role="assistant": assistant text or tool-use blocks
            - role="tool": completed tool results
            - role="turn_meta": final turn metadata (stop_reason, usage)
        """

        self._active_session_id = state.session_id
        active_hook_ctx = hook_ctx or HookContext(session_id=state.session_id, turn_id=state.turn_id)
        run_id = _resolve_hook_run_id(active_hook_ctx)
        await self._dispatch_observe_async(
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

        all_tool_calls: list[ToolCall] = []
        all_tool_results: list[ToolResult] = []
        turn_usage: TokenUsage | None = None
        last_parent_id = state.user_message_id or (
            state.history_messages[-1].message_id if state.history_messages else None
        )

        try:
            with span("AgentLoop.run", session_id=state.session_id, turn_id=state.turn_id):
                api_round_count = 0
                while True:
                    api_round_count += 1
                    if max_turns is not None and api_round_count > max_turns:
                        stop_reason = "max_turns_reached"
                        yield Message(
                            message_id=make_message_id(),
                            role="turn_meta",
                            content="",
                            metadata={
                                "stop_reason": stop_reason,
                                "usage": turn_usage,
                                "completed": False,
                            },
                        )
                        return

                    if controller is not None:
                        for pending_msg in controller.drain_pending():
                            llm_messages.append(pending_msg)
                        if controller.is_aborted:
                            stop_reason = "aborted"
                            yield Message(
                                message_id=make_message_id(),
                                role="turn_meta",
                                content="",
                                metadata={
                                    "stop_reason": stop_reason,
                                    "usage": turn_usage,
                                    "completed": False,
                                },
                            )
                            return

                    executor = StreamingToolExecutor(
                        self._tool_registry,
                        hook_context=active_hook_ctx,
                        session_file_state=session_file_state,
                    ) if self._tool_registry is not None else None
                    iteration_tool_calls: list[ToolCall] = []
                    finish_reason: str | None = None
                    latest_usage: TokenUsage | None = None

                    stream = self._llm_client.generate(
                        LLMGenerateRequest(
                            session_id=llm_session_id or state.session_id,
                            model=self._model,
                            messages=tuple(llm_messages),
                            tools=active_tools,
                        )
                    )

                    last_assistant_msg_id: str | None = None
                    async for llm_msg in stream:
                        # Terminal metadata message: empty content with finish_reason
                        if llm_msg.content == "" and llm_msg.finish_reason is not None:
                            finish_reason = llm_msg.finish_reason
                            latest_usage = llm_msg.usage
                            continue

                        normalized_calls = tuple(
                            _normalize_tool_call(tc) for tc in (llm_msg.tool_calls or ())
                        )

                        assistant_msg_id = make_message_id()
                        assistant_msg = Message(
                            message_id=assistant_msg_id,
                            parent_message_id=last_parent_id,
                            role="assistant",
                            content=llm_msg.content or "",
                            group_id=assistant_msg_id,
                            metadata=_assistant_metadata_from_tool_calls(normalized_calls),
                        )
                        last_assistant_msg_id = assistant_msg.message_id
                        last_parent_id = assistant_msg.message_id

                        await self._dispatch_message_hooks(assistant_msg, active_hook_ctx, run_id)
                        yield assistant_msg

                        _append_llm_message(
                            llm_messages,
                            LLMMessage(
                                role=llm_msg.role,
                                content=llm_msg.content,
                                tool_calls=_as_llm_tool_calls(normalized_calls),
                            ),
                        )

                        if normalized_calls:
                            for tc in normalized_calls:
                                iteration_tool_calls.append(tc)
                                all_tool_calls.append(tc)
                                tool_hook_ctx = HookContext(
                                    session_id=active_hook_ctx.session_id,
                                    turn_id=active_hook_ctx.turn_id,
                                    repo_root=active_hook_ctx.repo_root,
                                    metadata={**dict(active_hook_ctx.metadata), "tool_call_id": tc.call_id},
                                    model_caller=active_hook_ctx.model_caller,
                                    session_event_publisher=active_hook_ctx.session_event_publisher,
                                )
                                if executor is not None:
                                    executor.add_tool(tc, hook_context=tool_hook_ctx)
                                await self._dispatch_tool_call_hook(tc, active_hook_ctx, run_id)

                            # Yield completed results non-blocking
                            if executor is not None:
                                for result in executor.get_completed_results():
                                    all_tool_results.append(result)
                                    tool_msg = self._build_tool_result_message(result, parent_message_id=last_assistant_msg_id, group_id=last_assistant_msg_id)
                                    last_parent_id = tool_msg.message_id
                                    yield tool_msg
                                    _append_llm_message(
                                        llm_messages,
                                        self._build_llm_tool_result_message(result),
                                    )
                                    await self._dispatch_tool_result_hook(result, active_hook_ctx, run_id)

                    # After stream ends, wait for remaining tools and yield
                    if executor is not None:
                        async for result in executor.get_remaining_results():
                            all_tool_results.append(result)
                            tool_msg = self._build_tool_result_message(result, parent_message_id=last_assistant_msg_id, group_id=last_assistant_msg_id)
                            last_parent_id = tool_msg.message_id
                            yield tool_msg
                            _append_llm_message(
                                llm_messages,
                                self._build_llm_tool_result_message(result),
                            )
                            await self._dispatch_tool_result_hook(result, active_hook_ctx, run_id)

                    turn_usage = _accumulate_usage(turn_usage, latest_usage)

                    if not iteration_tool_calls:
                        stop_reason = finish_reason or "completed"
                        yield Message(
                            message_id=make_message_id(),
                            role="turn_meta",
                            content="",
                            metadata={
                                "stop_reason": stop_reason,
                                "usage": turn_usage,
                                "completed": True,
                            },
                        )
                        break

                    if self._tool_registry is None:
                        stop_reason = "tool_registry_unavailable"
                        yield Message(
                            message_id=make_message_id(),
                            role="turn_meta",
                            content="",
                            metadata={
                                "stop_reason": stop_reason,
                                "usage": turn_usage,
                                "completed": True,
                            },
                        )
                        break

                    self._policies.ensure_tool_calls_allowed(tool_call_count=len(all_tool_calls))
        finally:
            turn_end_payload: dict[str, Any] = {
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "completed": True,
            }
            if run_id is not None:
                turn_end_payload["run_id"] = run_id
            if turn_usage is not None:
                turn_end_payload["usage"] = {
                    "prompt_tokens": turn_usage.prompt_tokens,
                    "completion_tokens": turn_usage.completion_tokens,
                    "total_tokens": turn_usage.total_tokens,
                }
            await self._dispatch_observe_async(
                "turn_end",
                turn_end_payload,
                active_hook_ctx,
            )

    async def _dispatch_message_hooks(
        self,
        msg: Message,
        hook_ctx: HookContext,
        run_id: str | None,
    ) -> None:
        await self._dispatch_observe_async(
            "message_start",
            _with_optional_run_id(
                {
                    "session_id": hook_ctx.session_id,
                    "turn_id": hook_ctx.turn_id,
                    "message_id": msg.message_id,
                    "role": msg.role,
                },
                run_id=run_id,
            ),
            hook_ctx,
        )
        await self._dispatch_observe_async(
            "message_update",
            _with_optional_run_id(
                {
                    "session_id": hook_ctx.session_id,
                    "turn_id": hook_ctx.turn_id,
                    "message_id": msg.message_id,
                    "delta": msg.content,
                },
                run_id=run_id,
            ),
            hook_ctx,
        )
        await self._dispatch_observe_async(
            "message_end",
            _with_optional_run_id(
                {
                    "session_id": hook_ctx.session_id,
                    "turn_id": hook_ctx.turn_id,
                    "message_id": msg.message_id,
                    "content": msg.content,
                    "role": msg.role,
                },
                run_id=run_id,
            ),
            hook_ctx,
        )

    async def _dispatch_tool_call_hook(
        self,
        tool_call: ToolCall,
        hook_ctx: HookContext,
        run_id: str | None,
    ) -> None:
        tool_hook_ctx = HookContext(
            session_id=hook_ctx.session_id,
            turn_id=hook_ctx.turn_id,
            repo_root=hook_ctx.repo_root,
            metadata={**dict(hook_ctx.metadata), "tool_call_id": tool_call.call_id},
            model_caller=hook_ctx.model_caller,
            session_event_publisher=hook_ctx.session_event_publisher,
        )
        await self._dispatch_observe_async(
            "tool_call",
            _with_optional_run_id(
                {
                    "session_id": hook_ctx.session_id,
                    "turn_id": hook_ctx.turn_id,
                    "call_id": tool_call.call_id,
                    "name": tool_call.name,
                    "arguments": dict(tool_call.arguments),
                },
                run_id=run_id,
            ),
            tool_hook_ctx,
        )

    async def _dispatch_tool_result_hook(
        self,
        result: ToolResult,
        hook_ctx: HookContext,
        run_id: str | None,
    ) -> None:
        tool_hook_ctx = HookContext(
            session_id=hook_ctx.session_id,
            turn_id=hook_ctx.turn_id,
            repo_root=hook_ctx.repo_root,
            metadata={**dict(hook_ctx.metadata), "tool_call_id": result.call_id},
            model_caller=hook_ctx.model_caller,
            session_event_publisher=hook_ctx.session_event_publisher,
        )
        await self._dispatch_observe_async(
            "tool_result",
            _with_optional_run_id(
                {
                    "session_id": hook_ctx.session_id,
                    "turn_id": hook_ctx.turn_id,
                    "call_id": result.call_id,
                    "name": result.name,
                    "output": result.output,
                    "error": result.error,
                },
                run_id=run_id,
            ),
            tool_hook_ctx,
        )

    async def _dispatch_observe_async(
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

    def active_tool_specs(self) -> tuple[ToolSpec, ...]:
        if self._tool_registry is not None:
            return self._tool_registry.list_specs()
        if self._available_tools is not None:
            return self._available_tools
        return ()

    def _active_tool_specs(self) -> tuple[ToolSpec, ...]:
        if self._tool_registry is not None:
            return self._tool_registry.list_specs()
        if self._available_tools is not None:
            return self._available_tools
        return ()

    def _serialize_tool_result(self, result: ToolResult) -> str:
        """Serialize tool result via tool adapter, then apply budget compression."""

        tool = self._tool_registry.get(result.name) if self._tool_registry is not None else None
        if tool is not None and hasattr(tool, "serialize_result"):
            try:
                raw_content = tool.serialize_result(result.output, result.error)
            except Exception:  # pragma: no cover - defensive fallback.
                raw_content = _serialize_tool_result_content(result)
        else:
            raw_content = _serialize_tool_result_content(result)

        compressor = self._tool_result_compressor
        if (
            compressor is not None
            and result.call_id
            and self._active_session_id is not None
        ):
            max_size = getattr(tool, "max_result_size_chars", DEFAULT_MAX_RESULT_SIZE_CHARS)
            raw_content = compressor.maybe_compress(
                raw_content,
                tool_name=result.name,
                tool_call_id=result.call_id,
                session_id=self._active_session_id,
                max_size_chars=max_size,
            )

        return raw_content

    def _build_llm_tool_result_message(self, result: ToolResult) -> LLMMessage:
        """Build an LLMMessage for appending to the live prompt."""

        return LLMMessage(
            role="tool",
            content=self._serialize_tool_result(result),
            tool_call_id=result.call_id,
        )

    def _build_tool_result_message(self, result: ToolResult, *, parent_message_id: str | None = None, group_id: str | None = None) -> Message:
        """Build a Message for yielding a completed tool result."""

        return Message(
            message_id=make_message_id(),
            parent_message_id=parent_message_id,
            group_id=group_id,
            role="tool",
            content=self._serialize_tool_result(result),
            tool_call_id=result.call_id,
            metadata={
                "tool_phase": "result",
                "tool_call_id": result.call_id,
                "tool_name": result.name,
                "tool_output": result.output,
                "tool_error": result.error,
                "tool_result": result,
            },
        )

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


def _append_llm_message(messages: list[LLMMessage], msg: LLMMessage) -> None:
    """Append an LLMMessage, merging with previous assistant when adjacent."""

    if msg.role == "assistant" and messages and messages[-1].role == "assistant":
        prev = messages[-1]
        merged_content = (prev.content or "") + (msg.content or "")
        merged_tool_calls = list(prev.tool_calls) + list(msg.tool_calls)
        messages[-1] = LLMMessage(
            role="assistant",
            content=merged_content,
            tool_calls=tuple(merged_tool_calls),
        )
    else:
        messages.append(msg)


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


def _loop_sleep(seconds: float) -> None:
    """Sleep for the given duration; extracted for test monkeypatching."""
    time.sleep(seconds)
