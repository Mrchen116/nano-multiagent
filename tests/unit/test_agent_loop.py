from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
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

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("unexpected llm call")
        response = self._responses.pop(0)
        return LLMGenerateResponse(
            model=request.model,
            message=response.message,
            finish_reason=response.finish_reason,
            usage=response.usage,
            raw=response.raw,
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

    def get_tool(self, name: str):  # noqa: ANN001, ANN201
        return None

    def execute(self, name, args, *, hook_context=None, read_file_state=None):  # noqa: ANN001, ANN201
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


async def test_loop_builds_context_and_returns_turn_result() -> None:
    client = FakeLLMClient()
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_turns=3))
    state = _base_state()

    result = await loop.run(state)

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

    result = await loop.run(_base_state())

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

    result = await loop.run(_base_state())

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

    result = await loop.run(_base_state())

    assert result.messages[-1].content == "recovered"
    assert len(result.tool_results) == 1
    assert result.tool_results[0].error == "tool boom"
    assert result.tool_results[0].output is None
    assert "tool boom" in client.requests[1].messages[-1].content


async def test_loop_accumulates_usage_across_multiple_model_calls() -> None:
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

    result = await loop.run(_base_state())

    assert result.usage is not None
    assert result.usage.prompt_tokens == 180
    assert result.usage.completion_tokens == 22
    assert result.usage.total_tokens == 202


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

    result = await loop.run(
        _base_state(),
        hook_ctx=HookContext(
            session_id="sess_agent",
            turn_id="turn_1",
            session_event_publisher=lambda event, data: published.append((event, str(data.get("call_id", "")))),
        ),
    )

    assert len(result.tool_calls) == 1
    assert published == [("tool_start", result.tool_calls[0].call_id)]


# R2: loop 不再调用 ensure_turn_allowed，不再因高 turn_count 抛异常
async def test_loop_does_not_raise_on_high_turn_count() -> None:
    """loop.run() 不应因 turn_count 超过 max_turns 而抛 PolicyViolation。"""
    import pytest
    from agent.core.errors import PolicyViolation

    client = FakeLLMClient()
    # 设置极小的 max_turns，但 turn_count 远超此值
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_turns=1))
    state = AgentState(
        session_id="sess_agent",
        turn_id="turn_high",
        turn_count=9999,
        history_messages=(),
        input_parts=(InputPart(type="text", text="ping"),),
        user_text="ping",
    )

    # 不应抛出 PolicyViolation
    result = await loop.run(state)
    assert result.completed is True


# R2: loop 不再调用 truncate_history，history 完整传递给 LLM
async def test_loop_passes_full_history_to_llm() -> None:
    """loop.run() 应将完整的 history_messages 传给 LLM，不截断。"""
    client = FakeLLMClient()
    # 设置极小的 max_context_messages，但期望 history 不被截断
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_context_messages=1))

    from agent.core.types import Message
    history = tuple(
        Message(message_id=f"msg-{i}", role="user", content=f"msg {i}")
        for i in range(5)
    )
    state = AgentState(
        session_id="sess_agent",
        turn_id="turn_history",
        turn_count=0,
        history_messages=history,
        input_parts=(InputPart(type="text", text="ping"),),
        user_text="ping",
    )

    await loop.run(state)

    # LLM 收到的消息应包含全部 5 条历史消息（+ system + user = 7 条）
    # 而非被截断为 1 条（如果 truncate_history 仍在工作则只有 3 条: system+1history+user）
    llm_request = client.requests[0]
    # 计算历史消息数量：排除 system 消息和最后的 user 消息
    # build_prompt_messages 格式：system, [history...], user
    non_system_non_user = [m for m in llm_request.messages if m.role not in ("system",)]
    # 应包含 5 条历史 + 1 条 user = 6 条
    assert len(non_system_non_user) == 6, (
        f"期望 6 条（5 history + 1 user），实际 {len(non_system_non_user)} 条"
    )
