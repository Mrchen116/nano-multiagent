"""Compatibility shim re-exporting canonical core LLM interfaces."""

from nano_multiagent.core.llm.interfaces import (
    LLMClient,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)

__all__ = [
    "LLMClient",
    "LLMGenerateRequest",
    "LLMGenerateResponse",
    "LLMMessage",
    "LLMToolCall",
]
