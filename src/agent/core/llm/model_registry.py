"""Registry for supported providers, models, and capability metadata."""

from dataclasses import dataclass


DEFAULT_PROVIDER = "openai_compat"


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Describe model capabilities used by runtime planning and validation."""

    provider: str
    model: str
    default_base_url: str
    supports_text: bool
    supports_image: bool
    supports_tools: bool
    supports_streaming: bool


_PROVIDER_MODELS: dict[str, dict[str, ModelMetadata]] = {
    "openai_compat": {
        "codex_oauth:gpt-5.4": ModelMetadata(
            provider="openai_compat",
            model="codex_oauth:gpt-5.4",
            default_base_url="http://127.0.0.1:4000",
            supports_text=True,
            supports_image=False,
            supports_tools=False,
            supports_streaming=False,
        ),
    },
    "anthropic": {
        "moonshotAnthropic:kimi-k2.5": ModelMetadata(
            provider="anthropic",
            model="moonshotAnthropic:kimi-k2.5",
            default_base_url="http://127.0.0.1:4000",
            supports_text=True,
            supports_image=False,
            supports_tools=False,
            supports_streaming=False,
        ),
    },
}

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "openai_compat": "codex_oauth:gpt-5.4",
    "anthropic": "moonshotAnthropic:kimi-k2.5",
}


def get_default_model(provider: str) -> str:
    """Return the default model name for a provider.

    Raises:
        ValueError: If provider is unsupported.
    """

    _ensure_provider(provider)
    return _PROVIDER_DEFAULT_MODEL[provider]


def list_supported_providers() -> tuple[str, ...]:
    """List all supported provider identifiers."""

    return tuple(sorted(_PROVIDER_MODELS.keys()))


def list_provider_models(provider: str) -> tuple[ModelMetadata, ...]:
    """List supported models for a provider ordered by model name.

    Raises:
        ValueError: If provider is unsupported.
    """

    _ensure_provider(provider)
    provider_models = _PROVIDER_MODELS[provider]
    return tuple(provider_models[model] for model in sorted(provider_models.keys()))


def get_default_base_url(provider: str) -> str:
    """Return the default base URL for a provider."""

    metadata = resolve_model_metadata(provider, None)
    return metadata.default_base_url


def resolve_model_metadata(provider: str, model: str | None) -> ModelMetadata:
    """Resolve model metadata for a provider/model pair.

    Args:
        provider: Provider identifier.
        model: Optional model override; defaults to provider default when omitted.

    Returns:
        Capability metadata for the resolved model.

    Raises:
        ValueError: If provider or model is unsupported.
    """

    _ensure_provider(provider)
    selected_model = model or _PROVIDER_DEFAULT_MODEL[provider]
    provider_models = _PROVIDER_MODELS[provider]
    if selected_model not in provider_models:
        raise ValueError(f"unsupported model for provider '{provider}': {selected_model}")
    return provider_models[selected_model]


def _ensure_provider(provider: str) -> None:
    if provider not in _PROVIDER_MODELS:
        raise ValueError(f"unsupported llm provider: {provider}")
