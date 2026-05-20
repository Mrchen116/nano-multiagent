"""Tests for AgentLoop: basic execution, tool calls, usage accumulation, history, hooks.

Parallel tool calls and result compression are in separate files:
- test_agent_loop_parallel_budget.py
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.types import TokenUsage, ToolSpec
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)


class FakeLLMClient:
    def __init__(self, responses: tuple[LLMGenerateResponse, ...] | None = None) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._responses = list(
            responses
            or (
                LLMGenerateResponse(
                    model="model-x",
                    message=LLMMessage(role="assistant", content="pong"),
                    finish_reason="stop",
                ),
            )
        )

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("unexpected llm call")
        response = self._responses.pop(0)
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


class FakeToolRegistry:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object], str | None]] = []
        self._fail = fail

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="echo",
                description="echo text",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            ),
        )

    def get(self, name: str):  # noqa: ANN201
        return self.get_tool(name)

    def get_tool(self, name: str):  # noqa: ANN201
        return None

    async def execute(self, name, args, *, hook_context=None, session_file_state=None):  # noqa: ANN201
        tool_call_id = None
        if hook_context is not None:
            tool_call_id = hook_context.metadata.get("tool_call_id")
        self.calls.append((name, dict(args), tool_call_id))
        if self._fail:
            raise RuntimeError("tool boom")
        return {"echoed": args["text"]}


def _base_state() -> AgentState:
    return AgentState(
        session_id="sess_agent",
        turn_id="turn_1",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="ping"),),
        user_text="ping",
    )


async def _run_loop(loop: AgentLoop, state: AgentState, **kwargs):
    """Consume AgentLoop async generator and build TurnResult."""
    messages = []
    async for msg in loop.run(state, **kwargs):
        messages.append(msg)
    return build_turn_result(state.session_id, state.turn_id, messages)


async def test_loop_builds_context_and_returns_turn_result() -> None:
    client = FakeLLMClient()
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_turns=3))
    state = _base_state()

    result = await _run_loop(loop, state)

    assert result.session_id == "sess_agent"
    assert result.turn_id == "turn_1"
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "pong"
    assert client.requests[0].session_id == "sess_agent"
    assert client.requests[0].model == "model-x"
    assert [msg.role for msg in client.requests[0].messages] == ["system", "user"]


async def test_loop_executes_tool_call_until_final_assistant_message() -> None:
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="", name="echo", arguments={"text": "ping"}),),
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="done"),
                finish_reason="stop",
            ),
        )
    )
    registry = FakeToolRegistry()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=3),
        tool_registry=registry,
    )

    result = await _run_loop(loop, _base_state())

    assert len(result.messages) == 2
    assert result.messages[0].metadata["tool_calls"][0]["name"] == "echo"
    assert result.messages[1].content == "done"
    assert len(result.tool_calls) == 1
    assert len(result.tool_results) == 1
    assert result.tool_calls[0].name == "echo"
    assert result.tool_results[0].name == "echo"
    assert result.tool_results[0].output == {"echoed": "ping"}
    call_id = result.tool_calls[0].call_id
    assert call_id.startswith("call_")
    assert result.messages[0].metadata["tool_calls"][0]["call_id"] == call_id
    assert result.tool_results[0].call_id == call_id
    assert registry.calls == [("echo", {"text": "ping"}, call_id)]

    assert len(client.requests) == 2
    assert [msg.role for msg in client.requests[1].messages] == ["system", "user", "assistant", "tool"]
    assert client.requests[1].messages[2].tool_calls[0].call_id == call_id
    assert client.requests[1].messages[3].tool_call_id == call_id
    assert '"output":{"echoed":"ping"}' in client.requests[1].messages[3].content


async def test_loop_records_tool_calls_when_registry_is_unavailable() -> None:
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="", name="echo", arguments={"text": "ping"}),),
                ),
                finish_reason="tool_calls",
            ),
        )
    )
    loop = AgentLoop(llm_client=client, model="model-x")

    result = await _run_loop(loop, _base_state())

    assert result.stop_reason == "tool_registry_unavailable"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "echo"
    assert result.tool_calls[0].call_id.startswith("call_")
    assert result.tool_results == ()


async def test_loop_fail_open_on_tool_error_and_continue_generation() -> None:
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="", name="echo", arguments={"text": "ping"}),),
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="recovered"),
                finish_reason="stop",
            ),
        )
    )
    registry = FakeToolRegistry(fail=True)
    loop = AgentLoop(llm_client=client, model="model-x", tool_registry=registry)

    result = await _run_loop(loop, _base_state())

    assert result.messages[-1].content == "recovered"
    assert len(result.tool_results) == 1
    assert result.tool_results[0].error == "tool boom"
    assert result.tool_results[0].output is None
    assert "tool boom" in client.requests[1].messages[-1].content


async def test_loop_accumulates_usage_across_multiple_model_calls() -> None:
    # prompt_tokens should be the LAST round-trip value (context snapshot), not a sum.
    # completion_tokens are summed because each round-trip produces distinct new tokens.
    # total_tokens must equal last_prompt_tokens + sum_completion_tokens.
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="", name="echo", arguments={"text": "ping"}),),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="done"),
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=80, completion_tokens=12, total_tokens=92),
            ),
        )
    )
    loop = AgentLoop(llm_client=client, model="model-x", tool_registry=FakeToolRegistry())

    result = await _run_loop(loop, _base_state())

    assert result.usage is not None
    # prompt_tokens = last round-trip only (80), NOT accumulated sum (100+80=180)
    assert result.usage.prompt_tokens == 80
    assert result.usage.completion_tokens == 22
    # total = last_prompt(80) + sum_completion(10+12=22) = 102, NOT raw total sum (110+92=202)
    assert result.usage.total_tokens == 102


async def test_loop_prompt_tokens_tracks_last_roundtrip_not_sum() -> None:
    # Regression: multi-roundtrip turns with tool calls must NOT accumulate prompt_tokens.
    # The prompt represents the context snapshot sent to LLM; summing repeated sends of
    # the same context across N roundtrips produces a physically meaningless value N×context.
    # Three roundtrips: first two use tool calls, third is final response.
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="c1", name="echo", arguments={"text": "a"}),),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=5, total_tokens=205),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="c2", name="echo", arguments={"text": "b"}),),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(prompt_tokens=210, completion_tokens=6, total_tokens=216),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="finished"),
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=220, completion_tokens=8, total_tokens=228),
            ),
        )
    )
    loop = AgentLoop(llm_client=client, model="model-x", tool_registry=FakeToolRegistry())

    result = await _run_loop(loop, _base_state())

    assert result.usage is not None
    # prompt_tokens must equal LAST roundtrip value (220), not accumulated 200+210+220=630
    assert result.usage.prompt_tokens == 220
    # completion_tokens must be accumulated sum: 5+6+8=19
    assert result.usage.completion_tokens == 19
    # total = last_prompt + sum_completion
    assert result.usage.total_tokens == 239


async def test_loop_propagates_session_event_publisher_to_tool_hook_context() -> None:
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="", name="echo", arguments={"text": "ping"}),),
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="done"),
                finish_reason="stop",
            ),
        )
    )
    published: list[tuple[str, str]] = []
    hooks = HookRegistry()

    async def on_tool_call(event, ctx):  # noqa: ANN001
        ctx.publish_session_event(
            event="tool_start",
            data={
                "call_id": event.get("call_id"),
            },
        )

    hooks.on("tool_call", on_tool_call)
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=3),
        tool_registry=FakeToolRegistry(),
        hook_runner=HookRunner(registry=hooks),
    )

    result = await _run_loop(
        loop,
        _base_state(),
        hook_ctx=HookContext(
            session_id="sess_agent",
            turn_id="turn_1",
            session_event_publisher=lambda event, data: published.append((event, str(data.get("call_id", "")))),
        ),
    )

    assert len(result.tool_calls) == 1
    assert published == [("tool_start", result.tool_calls[0].call_id)]
