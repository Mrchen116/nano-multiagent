"""Platform-level LLM client factory that wires provider implementations.

This module owns the concrete provider→class mapping and instantiation logic.
It is the composition root for LLM clients — agent.core.llm only holds the
LLMClient port and LLMFactoryConfig dataclass; the platform layer is the only
place that knows which class implements each provider.
"""

import httpx

from agent.core.llm.interfaces import LLMClient
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.model_registry import resolve_model_metadata
from agent.core.llm.retry import RetryingLLMClient
from agent.platform.llm.providers.openai_compat.client import OpenAICompatClient
from agent.platform.llm.providers.anthropic.client import AnthropicClient


_PROVIDER_CLIENTS: dict[str, type[LLMClient]] = {
    "openai_compat": OpenAICompatClient,
    "anthropic": AnthropicClient,
}


def create_llm_client(
    *,
    config: LLMFactoryConfig,
    transport: httpx.BaseTransport | None = None,
) -> LLMClient:
    """Instantiate an LLM client for the configured provider.

    Args:
        config: Provider/model/endpoint configuration.
        transport: Optional HTTPX transport for tests or custom networking.

    Returns:
        A provider-specific client implementing ``LLMClient``.

    Raises:
        ValueError: If the provider/model pair is unsupported.

    Notes:
        This is the sole location that maps provider name to concrete client
        class — agent.core never imports provider implementations directly.
    """
    metadata = resolve_model_metadata(config.provider, config.model)
    client_class = _resolve_client_class(config.provider)
    client = client_class(
        base_url=config.base_url,
        model=metadata.model,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        transport=transport,
    )
    return RetryingLLMClient(client)


def _resolve_client_class(provider: str) -> type[LLMClient]:
    try:
        return _PROVIDER_CLIENTS[provider]
    except KeyError:
        raise ValueError(f"unsupported llm provider: {provider}")
