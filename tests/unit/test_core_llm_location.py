"""Verify core/llm is the canonical home for shared LLM abstractions."""

from nano_multiagent.core.llm import (
    DEFAULT_PROVIDER,
    LLMClient,
    LLMFactoryConfig,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
    ModelMetadata,
    create_llm_client,
    get_default_base_url,
    get_default_model,
    list_provider_models,
    list_supported_providers,
    resolve_model_metadata,
)
from nano_multiagent.core.llm.factory import LLMFactoryConfig as CoreLLMFactoryConfig
from nano_multiagent.core.llm.factory import create_llm_client as CoreCreateLLMClient
from nano_multiagent.core.llm.interfaces import LLMClient as CoreLLMClient
from nano_multiagent.core.llm.interfaces import LLMGenerateRequest as CoreLLMGenerateRequest
from nano_multiagent.core.llm.interfaces import LLMGenerateResponse as CoreLLMGenerateResponse
from nano_multiagent.core.llm.interfaces import LLMMessage as CoreLLMMessage
from nano_multiagent.core.llm.interfaces import LLMToolCall as CoreLLMToolCall
from nano_multiagent.core.llm.model_registry import DEFAULT_PROVIDER as CoreDefaultProvider
from nano_multiagent.core.llm.model_registry import ModelMetadata as CoreModelMetadata
from nano_multiagent.core.llm.model_registry import get_default_base_url as CoreGetDefaultBaseUrl
from nano_multiagent.core.llm.model_registry import get_default_model as CoreGetDefaultModel
from nano_multiagent.core.llm.model_registry import list_provider_models as CoreListProviderModels
from nano_multiagent.core.llm.model_registry import list_supported_providers as CoreListSupportedProviders
from nano_multiagent.core.llm.model_registry import resolve_model_metadata as CoreResolveModelMetadata
from nano_multiagent.llm.factory import LLMFactoryConfig as LegacyLLMFactoryConfig
from nano_multiagent.llm.factory import create_llm_client as LegacyCreateLLMClient
from nano_multiagent.llm.interfaces import LLMClient as LegacyLLMClient
from nano_multiagent.llm.interfaces import LLMGenerateRequest as LegacyLLMGenerateRequest
from nano_multiagent.llm.interfaces import LLMGenerateResponse as LegacyLLMGenerateResponse
from nano_multiagent.llm.interfaces import LLMMessage as LegacyLLMMessage
from nano_multiagent.llm.interfaces import LLMToolCall as LegacyLLMToolCall
from nano_multiagent.llm.model_registry import DEFAULT_PROVIDER as LegacyDefaultProvider
from nano_multiagent.llm.model_registry import ModelMetadata as LegacyModelMetadata
from nano_multiagent.llm.model_registry import get_default_base_url as LegacyGetDefaultBaseUrl
from nano_multiagent.llm.model_registry import get_default_model as LegacyGetDefaultModel
from nano_multiagent.llm.model_registry import list_provider_models as LegacyListProviderModels
from nano_multiagent.llm.model_registry import list_supported_providers as LegacyListSupportedProviders
from nano_multiagent.llm.model_registry import resolve_model_metadata as LegacyResolveModelMetadata


def test_core_llm_is_canonical_home() -> None:
    """Core llm exports must originate from core-owned modules."""
    assert LLMClient is CoreLLMClient
    assert LLMGenerateRequest is CoreLLMGenerateRequest
    assert LLMGenerateResponse is CoreLLMGenerateResponse
    assert LLMMessage is CoreLLMMessage
    assert LLMToolCall is CoreLLMToolCall
    assert LLMFactoryConfig is CoreLLMFactoryConfig
    assert ModelMetadata is CoreModelMetadata
    assert create_llm_client is CoreCreateLLMClient
    assert get_default_model is CoreGetDefaultModel
    assert get_default_base_url is CoreGetDefaultBaseUrl
    assert list_supported_providers is CoreListSupportedProviders
    assert list_provider_models is CoreListProviderModels
    assert resolve_model_metadata is CoreResolveModelMetadata
    assert DEFAULT_PROVIDER == CoreDefaultProvider

    assert LLMClient.__module__ == "nano_multiagent.core.llm.interfaces"
    assert LLMGenerateRequest.__module__ == "nano_multiagent.core.llm.interfaces"
    assert LLMGenerateResponse.__module__ == "nano_multiagent.core.llm.interfaces"
    assert LLMMessage.__module__ == "nano_multiagent.core.llm.interfaces"
    assert LLMToolCall.__module__ == "nano_multiagent.core.llm.interfaces"
    assert LLMFactoryConfig.__module__ == "nano_multiagent.core.llm.factory"
    assert ModelMetadata.__module__ == "nano_multiagent.core.llm.model_registry"
    assert create_llm_client.__module__ == "nano_multiagent.core.llm.factory"
    assert get_default_model.__module__ == "nano_multiagent.core.llm.model_registry"
    assert get_default_base_url.__module__ == "nano_multiagent.core.llm.model_registry"
    assert list_supported_providers.__module__ == "nano_multiagent.core.llm.model_registry"
    assert list_provider_models.__module__ == "nano_multiagent.core.llm.model_registry"
    assert resolve_model_metadata.__module__ == "nano_multiagent.core.llm.model_registry"


def test_old_llm_paths_are_compat_shims() -> None:
    """Legacy llm modules must re-export canonical core llm objects."""
    assert LegacyLLMClient is CoreLLMClient
    assert LegacyLLMGenerateRequest is CoreLLMGenerateRequest
    assert LegacyLLMGenerateResponse is CoreLLMGenerateResponse
    assert LegacyLLMMessage is CoreLLMMessage
    assert LegacyLLMToolCall is CoreLLMToolCall
    assert LegacyLLMFactoryConfig is CoreLLMFactoryConfig
    assert LegacyModelMetadata is CoreModelMetadata
    assert LegacyCreateLLMClient is CoreCreateLLMClient
    assert LegacyGetDefaultModel is CoreGetDefaultModel
    assert LegacyGetDefaultBaseUrl is CoreGetDefaultBaseUrl
    assert LegacyListSupportedProviders is CoreListSupportedProviders
    assert LegacyListProviderModels is CoreListProviderModels
    assert LegacyResolveModelMetadata is CoreResolveModelMetadata
    assert LegacyDefaultProvider == CoreDefaultProvider
