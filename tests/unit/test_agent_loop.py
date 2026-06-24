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
    def __init__(
        self, responses: tuple[LLMGenerateResponse, ...] | None = None
    ) -> None:
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
    def __init__(self, *, fail: bool = False, hook_runner=None) -> None:  # noqa: ANN001
        self.calls: list[tuple[str, dict[str, object], str | None]] = []
        self._fail = fail
        # bugfix-367: tool_call observe hook 现在由 registry.execute 触发(以前由
        # loop.py 触发,会在 auto_mode_gate park 前就把 tool_start SSE 发出去)。
        # Fake registry 同步该责任,使涉及 hook 的测试反映新链路。
        self._hook_runner = hook_runner

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
        if self._hook_runner is not None and hook_context is not None:
            await self._hook_runner.dispatch_intercept(
                "tool_call",
                {
                    "name": name,
                    "args": dict(args),
                    "arguments": dict(args),
                    "call_id": tool_call_id,
                    "block": False,
                    "reason": None,
                },
                hook_context,
            )
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
    loop = AgentLoop(
        llm_client=client, model="model-x", policies=AgentPolicies(max_turns=3)
    )
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
                    tool_calls=(
                        LLMToolCall(
                            call_id="", name="echo", arguments={"text": "ping"}
                        ),
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
    assert [msg.role for msg in client.requests[1].messages] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
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
                    tool_calls=(
                        LLMToolCall(
                            call_id="", name="echo", arguments={"text": "ping"}
                        ),
                    ),
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
                    tool_calls=(
                        LLMToolCall(
                            call_id="", name="echo", arguments={"text": "ping"}
                        ),
                    ),
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
                    tool_calls=(
                        LLMToolCall(
                            call_id="", name="echo", arguments={"text": "ping"}
                        ),
                    ),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(
                    prompt_tokens=100, completion_tokens=10, total_tokens=110
                ),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="done"),
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=80, completion_tokens=12, total_tokens=92
                ),
            ),
        )
    )
    loop = AgentLoop(
        llm_client=client, model="model-x", tool_registry=FakeToolRegistry()
    )

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
                    tool_calls=(
                        LLMToolCall(call_id="c1", name="echo", arguments={"text": "a"}),
                    ),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(
                    prompt_tokens=200, completion_tokens=5, total_tokens=205
                ),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(call_id="c2", name="echo", arguments={"text": "b"}),
                    ),
                ),
                finish_reason="tool_calls",
                usage=TokenUsage(
                    prompt_tokens=210, completion_tokens=6, total_tokens=216
                ),
            ),
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="finished"),
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=220, completion_tokens=8, total_tokens=228
                ),
            ),
        )
    )
    loop = AgentLoop(
        llm_client=client, model="model-x", tool_registry=FakeToolRegistry()
    )

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
                    tool_calls=(
                        LLMToolCall(
                            call_id="", name="echo", arguments={"text": "ping"}
                        ),
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
    hook_runner = HookRunner(registry=hooks)
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=3),
        tool_registry=FakeToolRegistry(hook_runner=hook_runner),
        hook_runner=hook_runner,
    )

    result = await _run_loop(
        loop,
        _base_state(),
        hook_ctx=HookContext(
            session_id="sess_agent",
            turn_id="turn_1",
            session_event_publisher=lambda event, data: published.append(
                (event, str(data.get("call_id", "")))
            ),
        ),
    )

    assert len(result.tool_calls) == 1
    assert published == [("tool_start", result.tool_calls[0].call_id)]


async def test_loop_preserves_reasoning_content_in_tool_call_roundtrip() -> None:
    """开 thinking 后 assistant tool-call 轮的 reasoning_content 必须 round-trip 回传。

    kimi K2.6 等带 thinking 的模型要求：历史里每条带 tool_call 的 assistant 消息
    必须携带 reasoning_content，否则第二轮请求被拒。
    """
    thinking_text = "Let me think about this step by step..."
    client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="kimi-k2",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_r1", name="echo", arguments={"text": "hi"}
                        ),
                    ),
                    reasoning_content=thinking_text,
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="kimi-k2",
                message=LLMMessage(role="assistant", content="done"),
                finish_reason="stop",
            ),
        )
    )
    registry = FakeToolRegistry()
    loop = AgentLoop(
        llm_client=client,
        model="kimi-k2",
        policies=AgentPolicies(max_turns=3),
        tool_registry=registry,
    )

    await _run_loop(loop, _base_state())

    assert len(client.requests) == 2
    second_round_messages = client.requests[1].messages
    # messages: [system, user, assistant(tool_call), tool(result)]
    assistant_msg = second_round_messages[2]
    assert assistant_msg.role == "assistant"
    assert assistant_msg.tool_calls, "assistant 消息必须有 tool_calls"
    # reasoning_content 必须 round-trip 回传
    assert assistant_msg.reasoning_content == thinking_text, (
        f"reasoning_content 丢失: 期望 {thinking_text!r}, 实际 {assistant_msg.reasoning_content!r}"
    )


# ---------------------------------------------------------------------------
# W1 (feat-385-M2): AgentLoop on_compaction callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_accepts_on_compaction_callback_in_init() -> None:
    """AgentLoop.__init__ must accept on_compaction parameter without error."""
    called: list[str] = []

    def _cb(session_id: str) -> None:
        called.append(session_id)

    client = FakeLLMClient()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        on_compaction=_cb,
    )
    assert loop is not None


@pytest.mark.asyncio
async def test_loop_on_compaction_callback_not_called_without_compaction() -> None:
    """on_compaction callback must NOT be called during a normal (non-compaction) turn."""
    called: list[str] = []

    def _cb(session_id: str) -> None:
        called.append(session_id)

    client = FakeLLMClient()
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        on_compaction=_cb,
    )
    await _run_loop(loop, _base_state())
    assert called == [], "on_compaction must not fire when no compaction occurred"


# ---------------------------------------------------------------------------
# bugfix-426-M4 决策5/6: terminal re-drain continues the SAME run; consume-point
# signal lets the gateway roll the bubble. #140 closes the stranded-continuation
# window at the loop's terminal decision.
# ---------------------------------------------------------------------------


class _SteerOnTerminalLLMClient:
    """LLM client that injects a steer into the controller as it produces its
    terminal (no-tool-call) reply — i.e. exactly in the #140 window between the
    round-boundary drain and the loop's decision to break.

    The first generate() yields a final assistant message AND (as a side effect)
    enqueues a steer into the controller. A pre-decision-5 loop would break and
    strand the steer; the decision-5 loop must re-drain at terminal and continue
    the same run, consuming the steer on the next round.
    """

    def __init__(self, controller, steer_text: str) -> None:
        from agent.core.llm.interfaces import LLMMessage as _LM

        self._controller = controller
        self._steer_text = steer_text
        self._LM = _LM
        self.requests = []
        self._round = 0

    async def generate(self, request):  # noqa: ANN001
        self.requests.append(request)
        self._round += 1
        if self._round == 1:
            # Produce the terminal reply for the original message, and in the same
            # breath the user steers (lands after this round's drain already ran).
            from agent.core.runs.origin import RunOrigin

            self._controller.enqueue_message(
                self._LM(role="user", content=self._steer_text),
                origin=RunOrigin.USER,
            )
            yield self._LM(role="assistant", content="answer-to-first")
            yield self._LM(role="assistant", content="", finish_reason="stop")
        else:
            # Second round: the steer must have been drained into context.
            yield self._LM(role="assistant", content="answer-to-steer")
            yield self._LM(role="assistant", content="", finish_reason="stop")


async def test_loop_redrains_at_terminal_and_continues_same_run() -> None:
    """决策5: a steer that lands in the terminal window is consumed by the SAME run.

    The loop must re-drain at its terminal decision; finding the steer, it appends
    it to context and runs another round instead of breaking (which would strand it
    into a continuation run with a new run_id — the #140 carrier of dropped events).
    """
    from agent.core.agent.run_control import RunController

    controller = RunController()
    client = _SteerOnTerminalLLMClient(controller, steer_text="actually do X")
    loop = AgentLoop(
        llm_client=client, model="model-x", policies=AgentPolicies(max_turns=5)
    )

    result = await _run_loop(loop, _base_state(), controller=controller)

    # Two LLM rounds: the original terminal reply, then the steer-driven round.
    assert len(client.requests) == 2
    # The steer reached the model's context on the second round.
    second_round_user_texts = [
        m.content for m in client.requests[1].messages if m.role == "user"
    ]
    assert "actually do X" in second_round_user_texts
    # The final reply is the answer to the steer (same run continued, not stranded).
    assert result.messages[-1].content == "answer-to-steer"
    # Terminal committed only once the queue was truly empty.
    assert controller.is_terminal_committed is True
    assert controller.drain_pending() == []


async def test_loop_emits_injection_consumed_signal_at_consume_point() -> None:
    """bugfix-426-M4 决策6: the loop emits pending_injection_consumed when it actually
    consumes injected messages into context.

    The gateway needs the consume-point (not the enqueue moment) to roll the IM
    bubble: only the loop knows the round boundary where the steer enters context.
    """
    from agent.core.agent.run_control import RunController

    controller = RunController()
    client = _SteerOnTerminalLLMClient(controller, steer_text="steer-text")

    consumed_events: list[dict] = []
    hooks = HookRegistry()

    async def on_injection_consumed(event, ctx):  # noqa: ANN001
        consumed_events.append(dict(event))

    hooks.on("pending_injection_consumed", on_injection_consumed)
    hook_runner = HookRunner(registry=hooks)

    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=5),
        hook_runner=hook_runner,
    )

    await _run_loop(
        loop,
        _base_state(),
        controller=controller,
        hook_ctx=HookContext(
            session_id="sess_agent",
            turn_id="turn_1",
            metadata={"run_id": "run_abc"},
        ),
    )

    # Exactly one consume event, carrying the run_id, fired when the steer entered
    # context (the terminal re-drain round).
    assert len(consumed_events) == 1
    assert consumed_events[0].get("run_id") == "run_abc"


class _SteerThenToolCallClient:
    """Round 1: enqueue a steer, then return a tool_call so the loop wants another
    round. The next round's terminal exit (max_turns / tool_unavailable) then fires
    with the steer still pending — the bugfix-426-M4 V1 window."""

    def __init__(self, controller, steer_text: str) -> None:
        from agent.core.llm.interfaces import LLMMessage as _LM, LLMToolCall as _TC

        self._controller = controller
        self._steer_text = steer_text
        self._LM = _LM
        self._TC = _TC
        self.requests = []

    async def generate(self, request):  # noqa: ANN001
        self.requests.append(request)
        from agent.core.runs.origin import RunOrigin

        self._controller.enqueue_message(
            self._LM(role="user", content=self._steer_text), origin=RunOrigin.USER
        )
        yield self._LM(
            role="assistant",
            content="",
            tool_calls=(self._TC(call_id="", name="echo", arguments={"text": "x"}),),
        )
        yield self._LM(role="assistant", content="", finish_reason="tool_calls")


async def test_loop_commits_terminal_at_max_turns_exit_with_pending_steer() -> None:
    """bugfix-426-M4 V1: a steer landing as the loop hits its max_turns hard stop must
    leave the terminal COMMITTED, so a later inject is rejected and routed to a fresh
    run (not stranded into a continuation whose events the relay would drop)."""
    from agent.core.agent.run_control import RunController
    from agent.core.runs.origin import RunOrigin

    controller = RunController()
    client = _SteerThenToolCallClient(controller, steer_text="steer at max_turns")
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=99),
        tool_registry=FakeToolRegistry(),
    )

    # max_turns=1 (loop round cap): round 1 runs, round 2's top check exits.
    result = await _run_loop(loop, _base_state(), controller=controller, max_turns=1)

    assert result.stop_reason == "max_turns_reached"
    # Hard stop committed the terminal → a later inject would be rejected.
    assert controller.is_terminal_committed is True
    assert (
        controller.enqueue_message(
            LLMMessage(role="user", content="after"), origin=RunOrigin.USER
        )
        is False
    )


async def test_loop_commits_terminal_at_tool_unavailable_exit_with_pending_steer() -> (
    None
):
    """bugfix-426-M4 V1: same guarantee at the tool_registry_unavailable hard stop —
    the loop cannot run another round, so the terminal is committed and a racing steer
    goes to a fresh run, not a stranded continuation."""
    from agent.core.agent.run_control import RunController
    from agent.core.runs.origin import RunOrigin

    controller = RunController()
    # No tool registry → a tool_call forces the tool_unavailable exit.
    client = _SteerThenToolCallClient(controller, steer_text="steer at tool-unavail")
    loop = AgentLoop(
        llm_client=client, model="model-x", policies=AgentPolicies(max_turns=99)
    )

    result = await _run_loop(loop, _base_state(), controller=controller)

    assert result.stop_reason == "tool_registry_unavailable"
    assert controller.is_terminal_committed is True
    assert (
        controller.enqueue_message(
            LLMMessage(role="user", content="after"), origin=RunOrigin.USER
        )
        is False
    )


class _SteerThenAbortClient:
    """Round 1: enqueue a steer, signal abort, then return a tool_call so the loop
    wants another round. Round 2's round-start abort check then fires with the steer
    having been drained — the bugfix-426-M4 V1 abort hard-stop window."""

    def __init__(self, controller, steer_text: str) -> None:
        from agent.core.llm.interfaces import LLMMessage as _LM, LLMToolCall as _TC

        self._controller = controller
        self._steer_text = steer_text
        self._LM = _LM
        self._TC = _TC
        self.requests = []

    async def generate(self, request):  # noqa: ANN001
        self.requests.append(request)
        from agent.core.runs.origin import RunOrigin

        self._controller.enqueue_message(
            self._LM(role="user", content=self._steer_text), origin=RunOrigin.USER
        )
        self._controller.abort(user_initiated=True)
        yield self._LM(
            role="assistant",
            content="",
            tool_calls=(self._TC(call_id="", name="echo", arguments={"text": "x"}),),
        )
        yield self._LM(role="assistant", content="", finish_reason="tool_calls")


async def test_loop_commits_terminal_at_abort_exit_with_pending_steer() -> None:
    """bugfix-426-M4 V1 (W4): symmetric to the max_turns / tool_unavailable hard stops —
    the abort exit must also commit the terminal, so a later inject is rejected and
    routed to a fresh run rather than left to strand. The abort exit does NOT rely on
    is_aborted alone for the inject guard; it explicitly commits the terminal."""
    from agent.core.agent.run_control import RunController
    from agent.core.runs.origin import RunOrigin

    controller = RunController()
    client = _SteerThenAbortClient(controller, steer_text="steer at abort")
    loop = AgentLoop(
        llm_client=client,
        model="model-x",
        policies=AgentPolicies(max_turns=99),
        tool_registry=FakeToolRegistry(),
    )

    result = await _run_loop(loop, _base_state(), controller=controller)

    assert result.stop_reason == "aborted"
    # The abort hard stop committed the terminal.
    assert controller.is_terminal_committed is True
    # A later inject is rejected by the committed terminal (not merely by is_aborted).
    assert (
        controller.enqueue_message(
            LLMMessage(role="user", content="after"), origin=RunOrigin.USER
        )
        is False
    )
