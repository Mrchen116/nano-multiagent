from dataclasses import dataclass


DEFAULT_PROVIDER = "openai_compat"


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    provider: str
    model: str
    default_base_url: str
    supports_text: bool
    supports_image: bool
    supports_tools: bool
    supports_streaming: bool


_PROVIDER_MODELS: dict[str, dict[str, ModelMetadata]] = {
    "openai_compat": {
        "codexOAuth:gpt-5.2-codex": ModelMetadata(
            provider="openai_compat",
            model="codexOAuth:gpt-5.2-codex",
            default_base_url="http://127.0.0.1:4000",
            supports_text=True,
            supports_image=False,
            supports_tools=False,
            supports_streaming=False,
        ),
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": ModelMetadata(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            default_base_url="http://127.0.0.1:4000",
            supports_text=True,
            supports_image=False,
            supports_tools=False,
            supports_streaming=False,
        ),
    }
}

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "openai_compat": "codexOAuth:gpt-5.2-codex",
    "anthropic": "claude-3-5-sonnet-20241022",
}


def get_default_model(provider: str) -> str:
    _ensure_provider(provider)
    return _PROVIDER_DEFAULT_MODEL[provider]


def list_supported_providers() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDER_MODELS.keys()))


def list_provider_models(provider: str) -> tuple[ModelMetadata, ...]:
    _ensure_provider(provider)
    provider_models = _PROVIDER_MODELS[provider]
    return tuple(provider_models[model] for model in sorted(provider_models.keys()))


def get_default_base_url(provider: str) -> str:
    metadata = resolve_model_metadata(provider, None)
    return metadata.default_base_url


def resolve_model_metadata(provider: str, model: str | None) -> ModelMetadata:
    _ensure_provider(provider)
    selected_model = model or _PROVIDER_DEFAULT_MODEL[provider]
    provider_models = _PROVIDER_MODELS[provider]
    if selected_model not in provider_models:
        raise ValueError(f"unsupported model for provider '{provider}': {selected_model}")
    return provider_models[selected_model]


def _ensure_provider(provider: str) -> None:
    if provider not in _PROVIDER_MODELS:
        raise ValueError(f"unsupported llm provider: {provider}")
