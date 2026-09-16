"""Product output callbacks preserve run state and actual delivery outcomes."""

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.run_control import RunController
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMMessage


async def test_product_withheld_output_continues_same_run_without_new_input():
    from agent.sdk.output import OutputResult, adapt_output_handler

    requests = []
    candidates = []
    events = []

    class Client:
        async def generate(self, request):
            requests.append(request)
            yield LLMMessage(
                role="assistant", content="broken " if len(requests) == 1 else "fixed"
            )
            if len(requests) == 1:
                yield LLMMessage(role="assistant", content="image")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    async def handler(candidate, control):
        candidates.append(candidate)
        if len(candidates) == 1:
            return OutputResult(
                state="withheld",
                reason_code="file_not_found",
                diagnostic="The image file is missing.",
                continuation="Correct the image source and continue.",
            )
        return OutputResult()

    loop = AgentLoop(
        llm_client=Client(), model="model-x", policies=AgentPolicies(max_turns=3)
    )
    loop._output_handler = adapt_output_handler(handler)
    state = AgentState(
        session_id="session",
        turn_id="turn",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="question"),),
        user_text="question",
    )
    context = HookContext(
        session_id="session",
        metadata={"run_id": "run", "output_handler_enabled": True},
        session_event_publisher=lambda event, data: events.append((event, data)),
    )
    messages = [
        m async for m in loop.run(state, controller=RunController(), hook_ctx=context)
    ]
    assert len(requests) == 2
    assert [c.text for c in candidates] == ["broken image", "fixed"]
    assert {c.run_id for c in candidates} == {"run"}
    assert "The image file is missing." in str(requests[1].messages)
    assert "withheld before publication" in str(requests[1].messages)
    assert [d["content"] for e, d in events if e == "assistant_message"] == ["fixed"]
    assert not any(e == "draft_withheld" for e, _ in events)
    assert [
        m.content for m in build_turn_result("session", "turn", messages).messages
    ] == ["fixed"]


async def test_product_pending_output_is_incomplete_without_false_unsent_reminder():
    from agent.sdk.output import OutputResult, adapt_output_handler

    requests = []

    class Client:
        async def generate(self, request):
            requests.append(request)
            yield LLMMessage(role="assistant", content="image reply")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    async def handler(candidate, control):
        return OutputResult(
            state="partial",
            diagnostic="IM received; external channel is pending.",
            delivery_id="delivery",
            channel_receipts=({"channel": "im", "state": "delivered"},),
        )

    loop = AgentLoop(llm_client=Client(), model="model-x")
    loop._output_handler = adapt_output_handler(handler)
    state = AgentState(
        session_id="session",
        turn_id="turn",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="question"),),
        user_text="question",
    )
    context = HookContext(
        session_id="session", metadata={"run_id": "run", "output_handler_enabled": True}
    )
    messages = [
        m async for m in loop.run(state, controller=RunController(), hook_ctx=context)
    ]
    assert len(requests) == 1
    assert messages[-1].metadata["completed"] is False
    assert messages[-1].metadata["stop_reason"] == "partial"
    status = next(m for m in messages if "output_status" in m.metadata)
    assert "never delivered" not in status.content
    assert status.metadata["output_status"]["delivery_id"] == "delivery"
    assert status.metadata["output_status"]["channel_receipts"] == [
        {"channel": "im", "state": "delivered"}
    ]


async def test_product_withheld_respects_round_budget_and_keeps_tool_results():
    from agent.core.llm.interfaces import LLMToolCall
    from agent.sdk.output import OutputResult, adapt_output_handler
    from tests.unit.test_agent_loop import FakeToolRegistry

    class Client:
        async def generate(self, request):
            yield LLMMessage(
                role="assistant",
                content="image reply",
                tool_calls=(
                    LLMToolCall(
                        call_id="call", name="echo", arguments={"text": "real result"}
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    async def handler(candidate, control):
        return OutputResult(state="withheld", diagnostic="The image is missing.")

    loop = AgentLoop(
        llm_client=Client(), model="model-x", tool_registry=FakeToolRegistry()
    )
    loop._output_handler = adapt_output_handler(handler)
    state = AgentState(
        session_id="session",
        turn_id="turn",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="question"),),
        user_text="question",
    )
    context = HookContext(
        session_id="session", metadata={"run_id": "run", "output_handler_enabled": True}
    )
    messages = [
        m
        async for m in loop.run(
            state, controller=RunController(), hook_ctx=context, max_turns=1
        )
    ]
    assert messages[-1].metadata["completed"] is False
    assert messages[-1].metadata["stop_reason"] == "max_turns_reached"
    result = build_turn_result("session", "turn", messages)
    assert len(result.tool_results) == 1
    assert result.tool_results[0].error is None
    assert "real result" in str(result.tool_results[0].output)
    assert not result.messages


async def test_output_runtime_feature_enables_delivery_and_excludes_subagents():
    from agent.sdk.output import OutputResult, adapt_output_handler

    called = []
    events = []

    class Client:
        async def generate(self, request):
            yield LLMMessage(role="assistant", content="image reply")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    async def handler(candidate, control):
        assert control.try_commit(lambda: called.append(candidate)) == "committed"
        return OutputResult(state="delivered", delivery_id="delivery")

    loop = AgentLoop(llm_client=Client(), model="model-x")
    loop._output_handler = adapt_output_handler(handler)
    state = AgentState(
        session_id="session",
        turn_id="turn",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="question"),),
        user_text="question",
    )
    for kind in ("main", "subagent"):
        context = HookContext(
            session_id="session",
            metadata={
                "run_id": "run",
                "kind": kind,
                "agent_features": {"output_handler_enabled": True},
            },
            session_event_publisher=lambda e, d: events.append((e, d)),
        )
        messages = [
            m
            async for m in loop.run(state, controller=RunController(), hook_ctx=context)
        ]
        assert messages[-1].metadata["completed"] is True
        if kind == "main":
            assert len(called) == 1
            assert not any(e == "assistant_message" for e, _ in events)
            assert (
                next(
                    m.metadata["output_status"]["state"]
                    for m in messages
                    if "output_status" in m.metadata
                )
                == "delivered"
            )
    assert len(called) == 1
