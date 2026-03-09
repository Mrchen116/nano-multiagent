"""Canonical shared LLM abstractions and model configuration helpers."""

from .factory import LLMFactoryConfig, create_llm_client
from .interfaces import LLMClient, LLMGenerateRequest, LLMGenerateResponse, LLMMessage, LLMToolCall
from .model_registry import (
    DEFAULT_PROVIDER,
    ModelMetadata,
    get_default_base_url,
    get_default_model,
    list_provider_models,
    list_supported_providers,
    resolve_model_metadata,
)

__all__ = [
    "DEFAULT_PROVIDER",
    "LLMClient",
    "LLMFactoryConfig",
    "LLMGenerateRequest",
    "LLMGenerateResponse",
    "LLMMessage",
    "LLMToolCall",
    "ModelMetadata",
    "create_llm_client",
    "get_default_base_url",
    "get_default_model",
    "list_provider_models",
    "list_supported_providers",
    "resolve_model_metadata",
]
