import os
from dataclasses import dataclass

import httpx

from .interfaces import LLMClient
from .model_registry import (
    DEFAULT_PROVIDER,
    get_default_base_url,
    get_default_model,
    resolve_model_metadata,
)
from .protocols.anthropic.client import AnthropicClient
from .protocols.openai_compat.client import OpenAICompatClient


@dataclass(frozen=True, slots=True)
class LLMFactoryConfig:
    provider: str = DEFAULT_PROVIDER
    model: str = "codexOAuth:gpt-5.2-codex"
    base_url: str = "http://127.0.0.1:4000"
    api_key: str | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMFactoryConfig":
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
    active_config = config or LLMFactoryConfig.from_env()
    metadata = resolve_model_metadata(active_config.provider, active_config.model)

    if active_config.provider == "openai_compat":
        return OpenAICompatClient(
            base_url=active_config.base_url,
            model=metadata.model,
            api_key=active_config.api_key,
            timeout_seconds=active_config.timeout_seconds,
            transport=transport,
        )
    if active_config.provider == "anthropic":
        return AnthropicClient(
            base_url=active_config.base_url,
            model=metadata.model,
            api_key=active_config.api_key,
            timeout_seconds=active_config.timeout_seconds,
            transport=transport,
        )
    raise ValueError(f"unsupported llm provider: {active_config.provider}")
