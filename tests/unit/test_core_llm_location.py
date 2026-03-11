"""Verify core/llm is the canonical home for shared LLM abstractions."""

from importlib.util import find_spec

from agent.core.llm import (
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
from agent.core.llm.factory import LLMFactoryConfig as CoreLLMFactoryConfig
from agent.core.llm.factory import create_llm_client as CoreCreateLLMClient
from agent.core.llm.interfaces import LLMClient as CoreLLMClient
from agent.core.llm.interfaces import LLMGenerateRequest as CoreLLMGenerateRequest
from agent.core.llm.interfaces import LLMGenerateResponse as CoreLLMGenerateResponse
from agent.core.llm.interfaces import LLMMessage as CoreLLMMessage
from agent.core.llm.interfaces import LLMToolCall as CoreLLMToolCall
from agent.core.llm.model_registry import DEFAULT_PROVIDER as CoreDefaultProvider
from agent.core.llm.model_registry import ModelMetadata as CoreModelMetadata
from agent.core.llm.model_registry import get_default_base_url as CoreGetDefaultBaseUrl
from agent.core.llm.model_registry import get_default_model as CoreGetDefaultModel
from agent.core.llm.model_registry import list_provider_models as CoreListProviderModels
from agent.core.llm.model_registry import list_supported_providers as CoreListSupportedProviders
from agent.core.llm.model_registry import resolve_model_metadata as CoreResolveModelMetadata



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

    assert LLMClient.__module__ == "agent.core.llm.interfaces"
    assert LLMGenerateRequest.__module__ == "agent.core.llm.interfaces"
    assert LLMGenerateResponse.__module__ == "agent.core.llm.interfaces"
    assert LLMMessage.__module__ == "agent.core.llm.interfaces"
    assert LLMToolCall.__module__ == "agent.core.llm.interfaces"
    assert LLMFactoryConfig.__module__ == "agent.core.llm.factory"
    assert ModelMetadata.__module__ == "agent.core.llm.model_registry"
    assert create_llm_client.__module__ == "agent.core.llm.factory"
    assert get_default_model.__module__ == "agent.core.llm.model_registry"
    assert get_default_base_url.__module__ == "agent.core.llm.model_registry"
    assert list_supported_providers.__module__ == "agent.core.llm.model_registry"
    assert list_provider_models.__module__ == "agent.core.llm.model_registry"
    assert resolve_model_metadata.__module__ == "agent.core.llm.model_registry"



def test_legacy_llm_root_is_removed() -> None:
    assert find_spec("agent.llm") is None
