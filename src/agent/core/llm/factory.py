"""LLM client factory that keeps provider wiring in one boundary."""

import os
from dataclasses import dataclass

import httpx

from .interfaces import LLMClient
from .retry import RetryingLLMClient
from .model_registry import (
    get_default_base_url,
    get_default_model,
    get_default_provider,
    resolve_model_metadata,
)
from agent.platform.llm.providers.openai_compat.client import OpenAICompatClient
from agent.platform.llm.providers.anthropic.client import AnthropicClient


@dataclass(frozen=True, slots=True)
class LLMFactoryConfig:
    """Collect provider configuration needed to build an LLM client."""

    provider: str = "anthropic"
    model: str = "codex_oauth:gpt-5.5"
    base_url: str = "http://127.0.0.1:4000"
    api_key: str | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMFactoryConfig":
        """Load LLM factory configuration from environment variables.

        Returns:
            Parsed configuration with provider defaults applied.
        """

        provider = os.getenv("NANO_MULTIAGENT_LLM_PROVIDER", get_default_provider())
        model = os.getenv("NANO_MULTIAGENT_LLM_MODEL", get_default_model(provider))
        env_base_url = os.getenv("NANO_MULTIAGENT_LLM_BASE_URL")
        config_base_url = get_default_base_url(provider)
        if env_base_url is not None:
            base_url = env_base_url
        elif config_base_url is not None:
            base_url = config_base_url
        else:
            raise ValueError(
                f"base_url unset for provider {provider!r}: neither NANO_MULTIAGENT_LLM_BASE_URL"
                " nor llm.providers[].base_url is configured"
            )
        timeout_seconds = float(os.getenv("NANO_MULTIAGENT_LLM_TIMEOUT_SECONDS", "30"))
        api_key = os.getenv("NANO_MULTIAGENT_LLM_API_KEY")
        return cls(
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
        )


def create_llm_client(
    *,
    config: LLMFactoryConfig | None = None,
    transport: httpx.BaseTransport | None = None,
) -> LLMClient:
    """Instantiate an LLM client for the configured provider.

    Args:
        config: Explicit config override; falls back to environment when omitted.
        transport: Optional HTTPX transport for tests/custom networking.

    Returns:
        A provider-specific client implementing `LLMClient`.

    Raises:
        ValueError: If the provider/model pair is unsupported.

    Notes:
        Provider-specific branches are intentionally isolated in this factory and
        `llm/providers/*`, so runtime/agent code stays provider-agnostic.
    """

    active_config = config or LLMFactoryConfig.from_env()
    metadata = resolve_model_metadata(active_config.provider, active_config.model)

    # Provider protocol details must not leak into agent/runtime layers.
    client_class = _resolve_client_class(active_config.provider)
    client = client_class(
        base_url=active_config.base_url,
        model=metadata.model,
        api_key=active_config.api_key,
        timeout_seconds=active_config.timeout_seconds,
        transport=transport,
    )
    return RetryingLLMClient(client)


_PROVIDER_CLIENTS: dict[str, type[LLMClient]] = {
    "openai_compat": OpenAICompatClient,
    "anthropic": AnthropicClient,
}


def _resolve_client_class(provider: str) -> type[LLMClient]:
    try:
        return _PROVIDER_CLIENTS[provider]
    except KeyError:
        raise ValueError(f"unsupported llm provider: {provider}")
