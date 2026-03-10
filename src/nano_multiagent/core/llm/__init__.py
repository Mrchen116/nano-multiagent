"""Canonical shared LLM package with lazy top-level exports."""

from importlib import import_module
from typing import Any

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


_FACTORY_EXPORTS = {"LLMFactoryConfig", "create_llm_client"}
_INTERFACE_EXPORTS = {
    "LLMClient",
    "LLMGenerateRequest",
    "LLMGenerateResponse",
    "LLMMessage",
    "LLMToolCall",
}
_MODEL_REGISTRY_EXPORTS = {
    "DEFAULT_PROVIDER",
    "ModelMetadata",
    "get_default_base_url",
    "get_default_model",
    "list_provider_models",
    "list_supported_providers",
    "resolve_model_metadata",
}


def __getattr__(name: str) -> Any:
    if name in _FACTORY_EXPORTS:
        return getattr(import_module("nano_multiagent.core.llm.factory"), name)
    if name in _INTERFACE_EXPORTS:
        return getattr(import_module("nano_multiagent.core.llm.interfaces"), name)
    if name in _MODEL_REGISTRY_EXPORTS:
        return getattr(import_module("nano_multiagent.core.llm.model_registry"), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(__all__)
