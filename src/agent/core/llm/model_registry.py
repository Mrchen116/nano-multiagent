"""Config-driven registry for supported providers, models, and capability metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.core.llm.config import LLMConfigPayload


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Describe model capabilities used by runtime planning and validation."""

    provider: str
    model: str
    default_base_url: str | None
    extra_request_body: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class _RegistryState:
    default_model: str
    default_provider: str
    # provider → {model_name → ModelMetadata}
    models: dict[str, dict[str, ModelMetadata]]
    # provider → default_model_name
    provider_defaults: dict[str, str]
    # model_name → provider (bugfix-429 fix-r1 #3: O(1) reverse lookup for routing)
    model_to_provider: dict[str, str]


_REGISTRY: _RegistryState | None = None


def init_model_registry(payload: "LLMConfigPayload") -> None:
    """Populate the process-level model registry from a config payload.

    Must be called exactly once per process (Gateway and Kernel each call it
    at startup). Repeated calls without _reset_for_tests() raise RuntimeError.

    Args:
        payload: LLMConfigPayload deserialized from YAML (Gateway) or env JSON (Kernel).

    Raises:
        RuntimeError: If the registry has already been initialized.
        ValueError: If payload.default_model is not found in any provider.
    """
    global _REGISTRY
    if _REGISTRY is not None:
        raise RuntimeError(
            "model registry already initialized — call _reset_for_tests() first in tests"
        )

    models: dict[str, dict[str, ModelMetadata]] = {}
    provider_defaults: dict[str, str] = {}
    model_to_provider: dict[str, str] = {}

    for provider_payload in payload.providers:
        pname = provider_payload.name
        base_url = provider_payload.base_url
        provider_models: dict[str, ModelMetadata] = {}
        for model_payload in provider_payload.models:
            provider_models[model_payload.name] = ModelMetadata(
                provider=pname,
                model=model_payload.name,
                default_base_url=base_url,
                extra_request_body=model_payload.extra_request_body,
            )
            # First declaration wins on duplicate model names across providers
            # (matches the forward iteration order used by the old linear scan).
            model_to_provider.setdefault(model_payload.name, pname)
        models[pname] = provider_models
        # first model in provider is the provider default
        if provider_payload.models:
            provider_defaults[pname] = provider_payload.models[0].name

    # Find which provider owns the global default_model and make it the provider default
    default_provider: str | None = None
    for pname, pmodels in models.items():
        if payload.default_model in pmodels:
            default_provider = pname
            provider_defaults[pname] = payload.default_model
            break
    if default_provider is None:
        raise ValueError(
            f"default_model '{payload.default_model}' not found in any provider"
        )

    _REGISTRY = _RegistryState(
        default_model=payload.default_model,
        default_provider=default_provider,
        models=models,
        provider_defaults=provider_defaults,
        model_to_provider=model_to_provider,
    )


def _reset_for_tests() -> None:
    """Reset the registry singleton for test isolation.

    Tests that need to verify 'not initialized' behavior call this before the
    assertion; the conftest autouse fixture re-initializes after each test.
    """
    global _REGISTRY
    _REGISTRY = None


def _require_initialized() -> _RegistryState:
    if _REGISTRY is None:
        raise RuntimeError(
            "model registry not initialized — call init_model_registry(payload) at process startup"
        )
    return _REGISTRY


def get_default_provider() -> str:
    """Return the provider that owns the global default model."""
    return _require_initialized().default_provider


def get_default_model(provider: str) -> str:
    """Return the default model name for a provider.

    Raises:
        ValueError: If provider is not in the registry.
    """
    registry = _require_initialized()
    _ensure_provider(registry, provider)
    return registry.provider_defaults[provider]


def list_supported_providers() -> tuple[str, ...]:
    """List all registered provider identifiers."""
    return tuple(sorted(_require_initialized().models.keys()))


def list_provider_models(provider: str) -> tuple[ModelMetadata, ...]:
    """List models for a provider ordered by model name.

    Raises:
        ValueError: If provider is not in the registry.
    """
    registry = _require_initialized()
    _ensure_provider(registry, provider)
    provider_models = registry.models[provider]
    return tuple(provider_models[m] for m in sorted(provider_models.keys()))


def provider_of(model: str) -> str:
    """Return the provider that registered ``model`` (bugfix-429).

    The kernel routes each run to the client of its model's registered provider
    (anthropic / openai_compat). Model id ↔ provider is bound at config-register
    time, so this is an exact reverse lookup.

    Raises:
        ValueError: If no provider registered this model — fail loud rather than
            guessing a provider/format (no silent fallback).
    """
    registry = _require_initialized()
    provider = registry.model_to_provider.get(model)
    if provider is None:
        raise ValueError(f"no registered provider for model: {model}")
    return provider


def get_default_base_url(provider: str) -> str | None:
    """Return the default base URL for a provider, or None if not configured."""
    metadata = resolve_model_metadata(provider, None)
    return metadata.default_base_url


def resolve_model_metadata(provider: str, model: str | None) -> ModelMetadata:
    """Resolve model metadata for a provider/model pair.

    Args:
        provider: Provider identifier.
        model: Optional model override; defaults to provider default when omitted.

    Returns:
        Capability metadata for the resolved model. Unknown models inherit
        provider-level defaults (base_url, extra_request_body) with their
        own model name — allows pass-through of arbitrary model strings.

    Raises:
        ValueError: If provider is not in the registry.
    """
    registry = _require_initialized()
    _ensure_provider(registry, provider)
    provider_models = registry.models[provider]
    # bugfix-429: a provider declared with no models has nothing to resolve — fail
    # loud rather than blowing up on next(iter(...)) of an empty map below.
    if not provider_models:
        raise ValueError(f"no models registered for provider: {provider}")
    selected_model = model or registry.provider_defaults.get(provider, "")
    if selected_model in provider_models:
        return provider_models[selected_model]
    # Unknown model: inherit provider defaults with the requested model name.
    default_name = registry.provider_defaults.get(provider, next(iter(provider_models)))
    default = provider_models[default_name]
    return ModelMetadata(
        provider=provider,
        model=selected_model,
        default_base_url=default.default_base_url,
        extra_request_body=default.extra_request_body,
    )


def _ensure_provider(registry: _RegistryState, provider: str) -> None:
    if provider not in registry.models:
        raise ValueError(f"unsupported llm provider: {provider}")
