"""Compatibility shim re-exporting canonical core LLM model metadata."""

from nano_multiagent.core.llm.model_registry import (
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
    "ModelMetadata",
    "get_default_base_url",
    "get_default_model",
    "list_provider_models",
    "list_supported_providers",
    "resolve_model_metadata",
]
