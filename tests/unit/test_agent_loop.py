from nano_multiagent.agent.loop import AgentLoop
from nano_multiagent.agent.policies import AgentPolicies
from nano_multiagent.agent.state import AgentState, InputPart
from nano_multiagent.core.types import TokenUsage, ToolSpec
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.llm.interfaces import (
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

    def execute(self, name, args, *, hook_context=None):  # noqa: ANN001, ANN201
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


def test_loop_builds_context_and_returns_turn_result() -> None:
    client = FakeLLMClient()
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_turns=3))
    state = _base_state()

    result = loop.run(state)

    assert result.session_id == "sess_agent"
    assert result.turn_id == "turn_1"
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "pong"
    assert client.requests[0].session_id == "sess_agent"
    assert client.requests[0].model == "model-x"
    assert [msg.role for msg in client.requests[0].messages] == ["system", "user"]


def test_loop_executes_tool_call_until_final_assistant_message() -> None:
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

    result = loop.run(_base_state())

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


def test_loop_records_tool_calls_when_registry_is_unavailable() -> None:
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

    result = loop.run(_base_state())

    assert result.stop_reason == "tool_registry_unavailable"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "echo"
    assert result.tool_calls[0].call_id.startswith("call_")
    assert result.tool_results == ()


def test_loop_fail_open_on_tool_error_and_continue_generation() -> None:
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

    result = loop.run(_base_state())

    assert result.messages[-1].content == "recovered"
    assert len(result.tool_results) == 1
    assert result.tool_results[0].error == "tool boom"
    assert result.tool_results[0].output is None
    assert '"error":"tool boom"' in client.requests[1].messages[-1].content


def test_loop_accumulates_usage_across_multiple_model_calls() -> None:
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

    result = loop.run(_base_state())

    assert result.usage is not None
    assert result.usage.prompt_tokens == 180
    assert result.usage.completion_tokens == 22
    assert result.usage.total_tokens == 202


def test_loop_propagates_session_event_publisher_to_tool_hook_context() -> None:
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

    result = loop.run(
        _base_state(),
        hook_ctx=HookContext(
            session_id="sess_agent",
            turn_id="turn_1",
            session_event_publisher=lambda event, data: published.append((event, str(data.get("call_id", "")))),
        ),
    )

    assert len(result.tool_calls) == 1
    assert published == [("tool_start", result.tool_calls[0].call_id)]
