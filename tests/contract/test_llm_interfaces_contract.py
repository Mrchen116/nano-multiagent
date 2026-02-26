from dataclasses import fields, is_dataclass

from nano_multiagent.llm.interfaces import (
    LLMClient,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)


def test_llm_message_contract() -> None:
    assert is_dataclass(LLMMessage)
    assert [field.name for field in fields(LLMMessage)] == ["role", "content", "name"]


def test_llm_generate_request_contract() -> None:
    assert is_dataclass(LLMGenerateRequest)
    assert [field.name for field in fields(LLMGenerateRequest)] == [
        "session_id",
        "model",
        "messages",
        "stream",
        "temperature",
        "max_tokens",
        "metadata",
    ]


def test_llm_generate_response_contract() -> None:
    assert is_dataclass(LLMGenerateResponse)
    assert [field.name for field in fields(LLMGenerateResponse)] == [
        "model",
        "message",
        "finish_reason",
        "raw",
    ]


def test_llm_client_protocol_exposes_generate() -> None:
    assert hasattr(LLMClient, "generate")
