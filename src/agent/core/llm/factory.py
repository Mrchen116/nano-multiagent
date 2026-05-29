"""LLM factory configuration dataclass — core layer only.

This module holds the configuration port for LLM clients. Concrete provider
implementations live in agent.platform.llm.factory so that core never depends
on platform (rule: core does not import platform/products/apps).

The composition root (agent.sdk.build_kernel) is responsible for wiring the
platform factory into AgentRuntime via llm_client_factory injection.
"""

import os
from dataclasses import dataclass

from .model_registry import (
    get_default_base_url,
    get_default_model,
    get_default_provider,
)


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
