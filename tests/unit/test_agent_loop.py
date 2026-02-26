from nano_multiagent.agent.loop import AgentLoop
from nano_multiagent.agent.policies import AgentPolicies
from nano_multiagent.agent.state import AgentState, InputPart
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage


class FakeLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="pong"),
            finish_reason="stop",
        )


def test_loop_builds_context_and_returns_turn_result() -> None:
    client = FakeLLMClient()
    loop = AgentLoop(llm_client=client, model="model-x", policies=AgentPolicies(max_turns=3))
    state = AgentState(
        session_id="sess_agent",
        turn_id="turn_1",
        turn_count=0,
        history_messages=(),
        input_parts=(InputPart(type="text", text="ping"),),
        user_text="ping",
    )

    result = loop.run(state)

    assert result.session_id == "sess_agent"
    assert result.turn_id == "turn_1"
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "pong"
    assert client.requests[0].session_id == "sess_agent"
    assert client.requests[0].model == "model-x"
    assert [msg.role for msg in client.requests[0].messages] == ["system", "user"]
