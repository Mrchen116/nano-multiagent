"""Tests for AgentLoop policy enforcement: turn_count and history truncation behavior (R2 regression).

R2: loop removed ensure_turn_allowed and truncate_history calls so these now pass through.
"""

from collections.abc import AsyncIterator

from agent.core.agent.loop import AgentLoop
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.runtime import build_turn_result
from agent.core.agent.state import AgentState, InputPart
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)


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


async def _run_loop(loop: AgentLoop, state: AgentState, **kwargs):
    """Consume AgentLoop async generator and build TurnResult."""
    messages = []
    async for msg in loop.run(state, **kwargs):
        messages.append(msg)
    return build_turn_result(state.session_id, state.turn_id, messages)


# R2: loop 不再调用 ensure_turn_allowed，不再因高 turn_count 抛异常
async def test_loop_does_not_raise_on_high_turn_count() -> None:
    """loop.run() 不应因 turn_count 超过 max_turns 而抛 PolicyViolation。"""
    from agent.core.errors import PolicyViolation

    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="pong"),
                finish_reason="stop",
            ),
        )
    )
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
    result = await _run_loop(loop, state)
    assert result.completed is True


# R2: loop 不再调用 truncate_history，history 完整传递给 LLM
async def test_loop_passes_full_history_to_llm() -> None:
    """loop.run() 应将完整的 history_messages 传给 LLM，不截断。"""
    client = _FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="model-x",
                message=LLMMessage(role="assistant", content="pong"),
                finish_reason="stop",
            ),
        )
    )
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

    await _run_loop(loop, state)

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
