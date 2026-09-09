"""Output publication and history when newer input invalidates a model round."""

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.run_control import RunController
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin


async def test_stale_body_is_withheld_before_exact_consumption_and_same_run_continues():
    controller = RunController(revalidate_output=True)
    events = []
    requests = []
    pending_ids = []

    class Client:
        async def generate(self, request):
            requests.append(request)
            if len(requests) == 1:
                yield LLMMessage(role="assistant", content="old ")
                pending_ids.append(
                    controller.enqueue_pending_message(
                        LLMMessage(role="user", content="new facts"), RunOrigin.USER
                    )
                )
                yield LLMMessage(role="assistant", content="answer")
            else:
                yield LLMMessage(role="assistant", content="revised answer")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    hooks = HookRegistry()

    async def failed_observer(event, context):
        raise RuntimeError("observer unavailable")

    hooks.on("message_end", failed_observer)
    hooks.on("pending_injection_consumed", failed_observer)
    loop = AgentLoop(
        llm_client=Client(),
        model="model-x",
        policies=AgentPolicies(max_turns=3),
        hook_runner=HookRunner(registry=hooks),
    )
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
        metadata={"run_id": "run"},
        session_event_publisher=lambda event, data: events.append((event, data)),
    )
    messages = [
        m async for m in loop.run(state, controller=controller, hook_ctx=context)
    ]
    assert [
        (event, data.get("content", data.get("text")))
        for event, data in events
        if event in {"draft_withheld", "assistant_message"}
    ] == [("draft_withheld", "old answer"), ("assistant_message", "revised answer")]
    draft_index = next(
        i for i, (event, _) in enumerate(events) if event == "draft_withheld"
    )
    consumed_index = next(
        i for i, (event, _) in enumerate(events) if event == "injection_consumed"
    )
    assert draft_index < consumed_index
    assert events[consumed_index][1]["pending_ids"] == pending_ids
    assert events[consumed_index][1]["context_revision"] == 1
    assert all(data["run_id"] == "run" for _, data in events if "run_id" in data)
    assert "NOT SENT" in str(requests[1].messages)
    assert "new facts" in str(requests[1].messages)
    assert [
        m.content for m in build_turn_result("session", "turn", messages).messages
    ] == ["revised answer"]


async def test_round_limit_withholds_body_and_leaves_unconsumed_input_for_recovery():
    controller = RunController(revalidate_output=True)
    events = []

    class Client:
        async def generate(self, request):
            controller.enqueue_message(
                LLMMessage(role="user", content="update"), RunOrigin.USER
            )
            yield LLMMessage(role="assistant", content="outdated")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    loop = AgentLoop(
        llm_client=Client(), model="model-x", policies=AgentPolicies(max_turns=1)
    )
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
        metadata={"run_id": "run"},
        session_event_publisher=lambda event, data: events.append((event, data)),
    )
    messages = [
        m
        async for m in loop.run(
            state, controller=controller, hook_ctx=context, max_turns=1
        )
    ]
    assert not any(
        event in {"assistant_message", "injection_consumed"} for event, _ in events
    )
    assert [p.message.content for p in controller.drain_pending()] == ["update"]
    result = build_turn_result("session", "turn", messages)
    assert result.stop_reason == "max_turns_reached"
    assert result.messages == ()

    # Reload/compact consume the real transcript including its durable status note.
    from agent.core.agent.prompting import build_chat_messages

    history = tuple(m for m in messages if m.role != "turn_meta")
    replay = build_chat_messages(history_messages=history, user_text="continue")
    assert "outdated" in str(replay)
    assert "NOT SENT" in str(replay)


async def test_tools_finish_before_body_commit_and_keep_real_results_on_revalidation():
    from agent.core.llm.interfaces import LLMToolCall
    from agent.core.types import TokenUsage
    from tests.unit.test_agent_loop import FakeToolRegistry

    controller = RunController(revalidate_output=True)
    events = []
    requests = []
    tool_contexts = []

    class Registry(FakeToolRegistry):
        async def execute(self, name, args, **kwargs):
            tool_contexts.append(kwargs["hook_context"].metadata)
            assert not any(event == "assistant_message" for event, _ in events)
            controller.enqueue_message(
                LLMMessage(role="user", content="changed"), RunOrigin.USER
            )
            return await super().execute(name, args, **kwargs)

    class Client:
        async def generate(self, request):
            requests.append(request)
            if len(requests) == 1:
                yield LLMMessage(
                    role="assistant",
                    content="candidate",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call",
                            name="echo",
                            arguments={"text": "real result"},
                        ),
                    ),
                )
            else:
                yield LLMMessage(role="assistant", content="new answer")
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=10, completion_tokens=5, total_tokens=15
                ),
            )

    loop = AgentLoop(llm_client=Client(), model="model-x", tool_registry=Registry())
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
        metadata={"run_id": "run"},
        session_event_publisher=lambda event, data: events.append((event, data)),
    )
    messages = [
        m
        async for m in loop.run(
            state, controller=controller, hook_ctx=context, max_turns=3
        )
    ]
    result = build_turn_result("session", "turn", messages)
    assert result.tool_results[0].error is None
    assert "real result" in str(requests[1].messages)
    assert result.usage.completion_tokens == 10
    assert tool_contexts[0]["run_id"] == "run"
    assert tool_contexts[0]["context_revision"] == 0
    assert tool_contexts[0]["revalidate_output"] is True
    assert [
        data["content"] for event, data in events if event == "assistant_message"
    ] == ["new answer"]


async def test_identical_committed_and_withheld_candidates_keep_distinct_durable_states(
    tmp_path,
):
    from dataclasses import replace
    from agent.core.agent.prompting import build_chat_messages
    from agent.core.session.transcript import JsonlTranscript
    from tests.unit.agent.session.test_jsonl_transcript import _build_transcript

    requests = []
    controller = RunController(revalidate_output=True)

    class Client:
        async def generate(self, request):
            requests.append(request)
            if len(requests) == 2:
                controller.enqueue_message(
                    LLMMessage(role="user", content="C: 3"), RunOrigin.USER
                )
            yield LLMMessage(
                role="assistant", content="1" if len(requests) < 3 else "4"
            )
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

    loop = AgentLoop(llm_client=Client(), model="model-x")
    state = AgentState(
        session_id="session",
        turn_id="turn-1",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="count"),),
        user_text="count",
    )
    first = [
        m
        async for m in loop.run(
            state, controller=RunController(revalidate_output=True), max_turns=3
        )
    ]
    first_status = next((m for m in first if m.metadata.get("output_status")), None)
    assert first_status is not None, (
        "A committed candidate needs its own durable delivery-state record"
    )
    second_state = replace(
        state,
        turn_id="turn-2",
        history_messages=tuple(m for m in first if m.role != "turn_meta"),
        input_parts=(InputPart(type="text", text="B: 2"),),
        user_text="B: 2",
    )
    second = [
        m async for m in loop.run(second_state, controller=controller, max_turns=3)
    ]
    status_messages = [m for m in first + second if m.metadata.get("output_status")]
    statuses = [m.metadata["output_status"] for m in status_messages]
    assert [s["state"] for s in statuses] == [
        "committed_for_delivery",
        "withheld",
        "committed_for_delivery",
    ]
    assert len({s["candidate_id"] for s in statuses}) == 3
    assert statuses[0]["message_ids"] != statuses[1]["message_ids"]
    next_context = str(requests[2].messages)
    assert all(s["candidate_id"] not in next_context for s in statuses)
    assert all(
        m.content.startswith("<system-reminder>\n")
        and m.content.endswith("\n</system-reminder>")
        for m in status_messages
    )
    assert "COMMITTED FOR DELIVERY" in next_context
    assert "NOT SENT" in next_context
    assert "even if their text is identical" in next_context

    transcript, files, writer, ref = _build_transcript(tmp_path)
    try:
        body = [m for m in first + second if m.role != "turn_meta"]
        transcript.append_messages(body, durable=True)
        reloaded = JsonlTranscript(ref=ref, files=files, writer=writer).load().messages
        assert [
            m.metadata["output_status"]
            for m in reloaded
            if "output_status" in m.metadata
        ] == statuses
        # Replay/compaction context retains both decisions; rejecting the later '1'
        # must not erase the earlier same-valued public candidate.
        replay = build_chat_messages(
            history_messages=tuple(reloaded), user_text="continue"
        )
        assert "COMMITTED FOR DELIVERY" in str(replay)
        assert "NOT SENT" in str(replay)
        assert [
            m.content
            for m in build_turn_result("session", "turn", list(reloaded)).messages
        ] == ["1", "4"]
    finally:
        writer.close()
