"""Complete model-round facts follow all chunks and tool results."""

import asyncio

import pytest

from agent.core.agent.loop import AgentLoop
from agent.core.agent.run_control import RunController
from agent.core.agent.state import AgentState, InputPart
from agent.core.hooks.context import HookContext
from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from tests.unit.test_agent_loop import FakeToolRegistry


def state():
    return AgentState(
        session_id="session",
        turn_id="turn",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="question"),),
        user_text="question",
    )


async def test_round_fact_waits_for_interleaved_tool_and_complete_text():
    events = []
    requests = []
    tool_done = False

    class Registry(FakeToolRegistry):
        async def execute(self, name, args, **kwargs):
            nonlocal tool_done
            await asyncio.sleep(0)
            assert not any(e == "model_round_end" for e, _ in events)
            result = await super().execute(name, args, **kwargs)
            tool_done = True
            return result

    class Client:
        async def generate(self, request):
            requests.append(request)
            if len(requests) == 1:
                yield LLMMessage(
                    role="assistant",
                    content="before",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call", name="echo", arguments={"text": "result"}
                        ),
                    ),
                )
                yield LLMMessage(role="assistant", content="after")
            else:
                assert tool_done
                assert len([e for e, _ in events if e == "model_round_end"]) == 1
                assert "result" in str(request.messages)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    loop = AgentLoop(llm_client=Client(), model="model", tool_registry=Registry())
    context = HookContext(
        session_id="session",
        turn_id="turn",
        metadata={"run_id": "run"},
        session_event_publisher=lambda e, d: events.append((e, d)),
    )
    messages = [m async for m in loop.run(state(), hook_ctx=context)]
    rounds = [d for e, d in events if e == "model_round_end"]
    assert len(rounds) == 2
    assert [r["context_revision"] for r in rounds] == [0, 0]
    assert all(r["group_id"] for r in rounds)
    assert rounds[0]["group_id"] != rounds[1]["group_id"]
    chunks = [m for m in messages if m.role == "assistant" and m.content]
    assert [m.content for m in chunks] == ["before", "after"]
    assert {m.group_id for m in chunks} == {rounds[0]["group_id"]}
    assert all(
        r["completed"] and r["turn_id"] == "turn" and r["run_id"] == "run"
        for r in rounds
    )


@pytest.mark.parametrize("ending", ["failure", "cancel", "abort"])
async def test_unfinished_round_never_reports_completion(ending):
    events = []
    controller = RunController()

    class Client:
        async def generate(self, request):
            yield LLMMessage(role="assistant", content="unfinished")
            if ending == "failure":
                raise RuntimeError("stream disconnected")
            if ending == "cancel":
                raise asyncio.CancelledError()
            controller.abort()
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    loop = AgentLoop(llm_client=Client(), model="model")
    context = HookContext(
        session_id="session", session_event_publisher=lambda e, d: events.append((e, d))
    )
    try:
        _ = [
            m async for m in loop.run(state(), hook_ctx=context, controller=controller)
        ]
    except (RuntimeError, asyncio.CancelledError):
        pass
    assert not any(e == "model_round_end" for e, _ in events)
