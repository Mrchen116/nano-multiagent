from dataclasses import fields, is_dataclass

from agent.core.types import ToolSpec
from agent.core.llm.interfaces import (
    LLMClient,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)


def test_llm_tool_call_contract() -> None:
    assert is_dataclass(LLMToolCall)
    assert [field.name for field in fields(LLMToolCall)] == ["call_id", "name", "arguments"]


def test_llm_message_contract() -> None:
    assert is_dataclass(LLMMessage)
    assert [field.name for field in fields(LLMMessage)] == [
        "role",
        "content",
        "name",
        "tool_call_id",
        "tool_calls",
        "finish_reason",
        "usage",
        "reasoning_content",
        "reasoning_signature",
    ]


def test_llm_generate_request_contract() -> None:
    assert is_dataclass(LLMGenerateRequest)
    assert [field.name for field in fields(LLMGenerateRequest)] == [
        "session_id",
        "model",
        "messages",
        "temperature",
        "max_tokens",
        "stop_sequences",
        "tools",
        "metadata",
        "extra_body",
    ]


def test_llm_generate_response_contract() -> None:
    assert is_dataclass(LLMGenerateResponse)
    assert [field.name for field in fields(LLMGenerateResponse)] == [
        "model",
        "message",
        "finish_reason",
        "usage",
        "raw",
    ]


def test_llm_client_protocol_exposes_generate() -> None:
    assert hasattr(LLMClient, "generate")


def test_llm_defaults_preserve_text_only_path() -> None:
    message = LLMMessage(role="user", content="hello")
    assert message.name is None
    assert message.tool_call_id is None
    assert message.tool_calls == ()

    request = LLMGenerateRequest(
        session_id="sess_contract",
        model="test-model",
        messages=(message,),
    )
    assert request.tools == ()
    assert request.metadata == {}


def test_llm_generate_request_accepts_tools() -> None:
    message = LLMMessage(role="user", content="ping")
    request = LLMGenerateRequest(
        session_id="sess_contract",
        model="test-model",
        messages=(message,),
        tools=(
            ToolSpec(
                name="read",
                description="Read file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
        ),
    )
    assert len(request.tools) == 1
    assert request.tools[0].name == "read"
