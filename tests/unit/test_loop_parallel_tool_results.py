"""RC1 loop-level regression: parallel safe tool_results must arrive in enqueue order.

Locks in the invariant: "stream未结束时不写tool_result、结束后多个并行tool_use
合并成一条assistant、tool_result按序追加" (PR #44 code review request).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Mapping

import pytest

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMMessage,
    LLMToolCall,
)
from agent.core.tools.base import Tool, ToolContext
from agent.core.tools.registry import ToolRegistry
from agent.core.types import ToolSpec


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _SlowStreamLLMClient:
    """Yield two tool_use blocks with a tiny inter-block pause to simulate streaming.

    The pause is intentionally short (just enough to let the event loop tick)
    so tool A (delay=0.12s) is still executing when tool B (delay=0.02s) finishes.
    """

    def __init__(
        self,
        *,
        second_response: LLMMessage | None = None,
    ) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._call_count = 0
        self._second_response = second_response or LLMMessage(role="assistant", content="done")

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        self._call_count += 1

        if self._call_count == 1:
            # First call: emit two tool_use blocks as separate streaming messages,
            # separated by a small pause so tool execution overlaps.
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(LLMToolCall(call_id="tc-A", name="r1", arguments={"path": "/a"}),),
            )
            await asyncio.sleep(0.01)  # tiny pause: r2 becomes enqueued after r1 starts
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(LLMToolCall(call_id="tc-B", name="r2", arguments={"path": "/b"}),),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
        else:
            yield self._second_response
            yield LLMMessage(role="assistant", content="", finish_reason="stop")


class _FakeSafeTool(Tool):
    """Safe tool with configurable async delay."""

    def __init__(self, name: str, delay: float) -> None:
        self.name = name
        self.description = "fake safe"
        self.input_schema: Mapping[str, Any] = {"type": "object"}
        self.max_result_size_chars: int | None = None
        self._delay = delay
        self.is_concurrency_safe = True

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        raise NotImplementedError

    def serialize_result(self, output: Any, error: str | None = None) -> str | list[dict[str, Any]]:
        return str(output) if output else error or ""


class _FakeRegistry(ToolRegistry):
    def __init__(self) -> None:
        self._tools: dict[str, _FakeSafeTool] = {}
        self.execution_order: list[str] = []

    def register_tool(self, tool: _FakeSafeTool) -> None:
        self._tools[tool.name] = tool

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(
            ToolSpec(name=t.name, description=t.description, input_schema={})
            for t in self._tools.values()
        )

    def get(self, name: str) -> _FakeSafeTool | None:
        return self._tools.get(name)

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: Any = None,
        session_file_state: Any = None,
    ) -> Mapping[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise RuntimeError(f"unknown: {name}")
        self.execution_order.append(name)
        if tool._delay:
            await asyncio.sleep(tool._delay)
        return {"result": name}


def _state() -> AgentState:
    return AgentState(
        session_id="sess_loop_parallel",
        turn_id="turn_1",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="go"),),
        user_text="go",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_parallel_tool_results_sent_in_enqueue_order() -> None:
    """Two parallel safe tool_results must appear in assistant's tool_use order.

    Scenario (mirrors bugfix-376 upstream-req 21-43-10):
      - LLM yields tool_use A (r1, slow=0.12s) then tool_use B (r2, fast=0.02s)
      - mid-stream: r2 completes first but get_completed_results() must not skip A
      - second LLM request must see: assistant[A,B], tool_result[A], tool_result[B]
        in that order — NOT tool_result[B], tool_result[A]
    """
    registry = _FakeRegistry()
    registry.register_tool(_FakeSafeTool("r1", delay=0.12))
    registry.register_tool(_FakeSafeTool("r2", delay=0.02))

    client = _SlowStreamLLMClient()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=5),
        tool_registry=registry,
    )

    messages = []
    async for msg in loop.run(_state()):
        messages.append(msg)

    result = build_turn_result("sess_loop_parallel", "turn_1", messages)

    # Two tool calls, two tool results
    assert len(result.tool_calls) == 2
    assert len(result.tool_results) == 2
    assert [tc.name for tc in result.tool_calls] == ["r1", "r2"]
    assert [tr.name for tr in result.tool_results] == ["r1", "r2"]

    # Second LLM request must have messages in correct order:
    # [system, user, assistant(A+B), tool_result(A), tool_result(B)]
    assert len(client.requests) == 2
    second_req_messages = client.requests[1].messages
    roles = [m.role for m in second_req_messages]
    assert roles == ["system", "user", "assistant", "tool", "tool"], (
        f"expected [system, user, assistant, tool, tool], got {roles}"
    )

    # The single assistant message carries both tool_use blocks
    assistant_msg = second_req_messages[2]
    assert len(assistant_msg.tool_calls) == 2
    assert assistant_msg.tool_calls[0].call_id == "tc-A"
    assert assistant_msg.tool_calls[1].call_id == "tc-B"

    # tool_result order must match tool_use order (A then B)
    tool_result_a = second_req_messages[3]
    tool_result_b = second_req_messages[4]
    assert tool_result_a.tool_call_id == "tc-A", (
        f"expected tc-A first, got {tool_result_a.tool_call_id}"
    )
    assert tool_result_b.tool_call_id == "tc-B", (
        f"expected tc-B second, got {tool_result_b.tool_call_id}"
    )


@pytest.mark.asyncio
async def test_loop_defers_tool_result_to_llm_messages_until_stream_ends() -> None:
    """tool_result must not appear in llm_messages while the stream is still open.

    The loop collects early-completed results mid-stream (for UI yield) but must
    not write them to llm_messages until after the stream ends.  This test verifies
    the second LLM call sees exactly one assistant message (not two split ones) and
    the tool_results follow it.
    """
    registry = _FakeRegistry()
    # Both tools fast so they complete well before the stream ends
    registry.register_tool(_FakeSafeTool("r1", delay=0.0))
    registry.register_tool(_FakeSafeTool("r2", delay=0.0))

    client = _SlowStreamLLMClient()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=5),
        tool_registry=registry,
    )

    messages = []
    async for msg in loop.run(_state()):
        messages.append(msg)

    assert len(client.requests) == 2
    second_req_messages = client.requests[1].messages

    # Must be exactly one assistant message (not split)
    assistant_msgs = [m for m in second_req_messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1, (
        f"expected 1 assistant message in second request, got {len(assistant_msgs)}: "
        f"{[m.tool_calls for m in assistant_msgs]}"
    )

    # All tool_results come after the assistant message
    roles = [m.role for m in second_req_messages]
    assert roles == ["system", "user", "assistant", "tool", "tool"]
