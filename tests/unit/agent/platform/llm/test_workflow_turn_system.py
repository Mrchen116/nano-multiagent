from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper
from agent.platform.llm.providers.openai_compat.mapper import OpenAICompatMapper


def _request() -> LLMGenerateRequest:
    return LLMGenerateRequest(
        session_id="sess",
        model="model",
        messages=(
            LLMMessage(role="system", content="leading"),
            LLMMessage(role="user", content="human input"),
            LLMMessage(role="turn_system", content="workflow reminder"),
        ),
    )


def test_anthropic_keeps_turn_system_after_current_human_message() -> None:
    payload = AnthropicMapper().map_generate_request(_request())

    assert payload["system"] == "leading"
    assert [item["role"] for item in payload["messages"]] == ["user", "system"]
    assert payload["messages"][-1]["content"] == [
        {"type": "text", "text": "workflow reminder"}
    ]


def test_openai_maps_turn_system_in_place() -> None:
    payload = OpenAICompatMapper().map_generate_request(_request())

    assert [item["role"] for item in payload["messages"]] == [
        "system",
        "user",
        "system",
    ]
    assert payload["messages"][-1]["content"] == "workflow reminder"
