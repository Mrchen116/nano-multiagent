"""LLM client factory that keeps provider wiring in one boundary."""

import os
from dataclasses import dataclass
from importlib import import_module

import httpx

from .interfaces import LLMClient
from .model_registry import (
    DEFAULT_PROVIDER,
    get_default_base_url,
    get_default_model,
    resolve_model_metadata,
)


@dataclass(frozen=True, slots=True)
class LLMFactoryConfig:
    """Collect provider configuration needed to build an LLM client."""

    provider: str = DEFAULT_PROVIDER
    model: str = "codex_oauth:gpt-5.4"
    base_url: str = "http://127.0.0.1:4000"
    api_key: str | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMFactoryConfig":
        """Load LLM factory configuration from environment variables.

        Returns:
            Parsed configuration with provider defaults applied.
        """

        provider = os.getenv("NANO_MULTIAGENT_LLM_PROVIDER", DEFAULT_PROVIDER)
        model = os.getenv("NANO_MULTIAGENT_LLM_MODEL", get_default_model(provider))
        base_url = os.getenv("NANO_MULTIAGENT_LLM_BASE_URL", get_default_base_url(provider))
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
    return client_class(
        base_url=active_config.base_url,
        model=metadata.model,
        api_key=active_config.api_key,
        timeout_seconds=active_config.timeout_seconds,
        transport=transport,
    )


def _resolve_client_class(provider: str) -> type[LLMClient]:
    if provider == "openai_compat":
        module = import_module(_provider_module_path("openai_compat"))
        return module.OpenAICompatClient
    if provider == "anthropic":
        module = import_module(_provider_module_path("anthropic"))
        return module.AnthropicClient
    raise ValueError(f"unsupported llm provider: {provider}")


def _provider_module_path(provider: str) -> str:
    return ".".join(("agent", "platform", "llm", "providers", provider, "client"))
