"""Tests for AgentLoop: policies, history passing, parallel tool calls, and result compression budget.

Basic execution, usage, and hooks are in test_agent_loop.py.
"""

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.types import ToolSpec
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)
from agent.core.tools.result_budget import ToolResultCompressor, PERSISTED_OUTPUT_TAG


class _FakeLLMClient:
    def __init__(self, responses: tuple[LLMGenerateResponse, ...]) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._responses = list(responses)

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


class _FakeToolRegistryConcurrent:
    """Tool registry with two concurrency-safe tools."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="echo",
                description="echo text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                is_concurrency_safe=True,
            ),
            ToolSpec(
                name="reverse",
                description="reverse text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                is_concurrency_safe=True,
            ),
        )

    def get(self, name: str):  # noqa: ANN201
        return self.get_tool(name)

    def get_tool(self, name: str):  # noqa: ANN201
        return None

    async def execute(self, name, args, *, hook_context=None, session_file_state=None):  # noqa: ANN201
        self.calls.append((name, dict(args)))
        return {"result": args["text"]}


async def test_loop_parallel_tool_calls_share_parent_and_group_id() -> None:
    """同一 assistant 发出的并发 tool_calls，其 tool result 的 parent_uuid 都指向该 assistant，且 group_id 相同。"""
    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(call_id="call_1", name="echo", arguments={"text": "hello"}),
                        LLMToolCall(call_id="call_2", name="reverse", arguments={"text": "world"}),
                    ),
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
    registry = _FakeToolRegistryConcurrent()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=3),
        tool_registry=registry,
    )

    # Collect raw yielded messages (includes tool messages)
    raw_messages: list = []
    async for msg in loop.run(_base_state()):
        raw_messages.append(msg)

    # Filter out turn_meta
    body = [m for m in raw_messages if m.role != "turn_meta"]
    # assistant (with tools) + tool1 + tool2 + assistant (done)
    assert len(body) == 4

    assistant_msg = body[0]
    tool_msg_1 = body[1]
    tool_msg_2 = body[2]
    assistant_done = body[3]

    assert assistant_msg.role == "assistant"
    assert tool_msg_1.role == "tool"
    assert tool_msg_2.role == "tool"
    assert assistant_done.role == "assistant"

    # Both tool results point to the assistant as parent
    assert tool_msg_1.parent_message_id == assistant_msg.message_id
    assert tool_msg_2.parent_message_id == assistant_msg.message_id

    # All share the same group_id (the assistant's message_id)
    assert assistant_msg.group_id == assistant_msg.message_id
    assert tool_msg_1.group_id == assistant_msg.message_id
    assert tool_msg_2.group_id == assistant_msg.message_id

    # Tool results are siblings, not a chain
    assert tool_msg_1.parent_message_id == tool_msg_2.parent_message_id

    # Second assistant's parent is the last tool result (linear chain resumes)
    assert assistant_done.parent_message_id == tool_msg_2.message_id


# ---------------------------------------------------------------------------
# Result compression budget tests
# ---------------------------------------------------------------------------


class _OversizedTool:
    name = "oversized"
    is_concurrency_safe = True
    max_result_size_chars = 100
    description = "returns large text"
    input_schema = {"type": "object", "properties": {"size": {"type": "integer"}}, "required": ["size"]}

    def run(self, args, ctx):  # noqa: ANN001
        return {"text": "x" * args["size"]}

    def serialize_result(self, output, error=None):  # noqa: ANN001
        if error:
            return error
        return output["text"]


class _UnlimitedTool:
    name = "unlimited"
    is_concurrency_safe = True
    max_result_size_chars = None
    description = "returns large text without limit"
    input_schema = {"type": "object", "properties": {"size": {"type": "integer"}}, "required": ["size"]}

    def run(self, args, ctx):  # noqa: ANN001
        return {"text": "x" * args["size"]}

    def serialize_result(self, output, error=None):  # noqa: ANN001
        if error:
            return error
        return output["text"]


class _BudgetToolRegistry:
    def __init__(self) -> None:
        self.oversized = _OversizedTool()
        self.unlimited = _UnlimitedTool()

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name=self.oversized.name,
                description=self.oversized.description,
                input_schema=self.oversized.input_schema,
                is_concurrency_safe=True,
                max_result_size_chars=100,
            ),
            ToolSpec(
                name=self.unlimited.name,
                description=self.unlimited.description,
                input_schema=self.unlimited.input_schema,
                is_concurrency_safe=True,
                max_result_size_chars=None,
            ),
        )

    def get(self, name: str):  # noqa: ANN201
        return self.get_tool(name)

    def get_tool(self, name: str):  # noqa: ANN201
        if name == self.oversized.name:
            return self.oversized
        if name == self.unlimited.name:
            return self.unlimited
        return None

    async def execute(self, name, args, *, hook_context=None, session_file_state=None):  # noqa: ANN201
        tool = self.get_tool(name)
        if tool is None:
            raise RuntimeError(f"unknown tool: {name}")
        return tool.run(args, None)


async def test_loop_compresses_oversized_tool_result() -> None:
    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="call_1", name="oversized", arguments={"size": 500}),),
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
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ToolResultCompressor(base_dir=Path(tmpdir))
        registry = _BudgetToolRegistry()
        loop = AgentLoop(
            llm_client=client,
            model="model-x",
            policies=AgentPolicies(max_turns=3),
            tool_registry=registry,
            tool_result_compressor=compressor,
        )

        result = await _run_loop(loop, _base_state())

        assert len(result.tool_results) == 1
        tr = result.tool_results[0]
        # metadata retains original structured output
        assert tr.output == {"text": "x" * 500}
        # content is compressed preview
        assert isinstance(tr.content, str)
        assert PERSISTED_OUTPUT_TAG in tr.content
        assert "Output too large" in tr.content

        # LLM received the compressed content
        llm_tool_msg = client.requests[1].messages[-1]
        assert llm_tool_msg.role == "tool"
        assert PERSISTED_OUTPUT_TAG in llm_tool_msg.content

        # File persisted
        filepath = Path(tmpdir) / "sess_agent" / "call_1.txt"
        assert filepath.exists()
        assert filepath.read_text() == "x" * 500


async def test_loop_skips_compression_for_unlimited_tool() -> None:
    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="call_2", name="unlimited", arguments={"size": 500}),),
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
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ToolResultCompressor(base_dir=Path(tmpdir))
        registry = _BudgetToolRegistry()
        loop = AgentLoop(
            llm_client=client,
            model="model-x",
            policies=AgentPolicies(max_turns=3),
            tool_registry=registry,
            tool_result_compressor=compressor,
        )

        result = await _run_loop(loop, _base_state())

        tr = result.tool_results[0]
        assert tr.content == "x" * 500
        assert PERSISTED_OUTPUT_TAG not in tr.content

        llm_tool_msg = client.requests[1].messages[-1]
        assert llm_tool_msg.content == "x" * 500

        assert not (Path(tmpdir) / "sess_agent" / "call_2.txt").exists()


async def test_loop_under_limit_no_compression() -> None:
    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(LLMToolCall(call_id="call_3", name="oversized", arguments={"size": 50}),),
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
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ToolResultCompressor(base_dir=Path(tmpdir))
        registry = _BudgetToolRegistry()
        loop = AgentLoop(
            llm_client=client,
            model="model-x",
            policies=AgentPolicies(max_turns=3),
            tool_registry=registry,
            tool_result_compressor=compressor,
        )

        result = await _run_loop(loop, _base_state())

        tr = result.tool_results[0]
        assert tr.content == "x" * 50
        assert PERSISTED_OUTPUT_TAG not in tr.content
