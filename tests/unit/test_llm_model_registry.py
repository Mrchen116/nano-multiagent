"""Tests for agent.core.llm.model_registry — registry API, init/reset, hard-fail, extra_request_body保真."""

import pytest

from agent.core.llm.model_registry import (
    _reset_for_tests,
    get_default_base_url,
    get_default_model,
    get_default_provider,
    init_model_registry,
    list_provider_models,
    list_supported_providers,
    resolve_model_metadata,
)


# ---------------------------------------------------------------------------
# 基线行为测试（依赖 conftest autouse fixture 初始化的 registry）
# ---------------------------------------------------------------------------


def test_openai_compat_default_model() -> None:
    assert get_default_model("openai_compat") == "codex_oauth:gpt-5.5"


def test_anthropic_default_model_and_base_url() -> None:
    assert get_default_model("anthropic") == "kimiCoding:K2.6"
    assert get_default_base_url("anthropic") == "http://127.0.0.1:4000"


def test_resolve_model_metadata_no_dead_fields() -> None:
    """ModelMetadata must not have supports_text/image/tools/streaming (dead fields removed)."""
    metadata = resolve_model_metadata("openai_compat", "codex_oauth:gpt-5.5")
    assert metadata.provider == "openai_compat"
    assert metadata.model == "codex_oauth:gpt-5.5"
    assert not hasattr(metadata, "supports_text"), "supports_text dead field must be removed"
    assert not hasattr(metadata, "supports_image"), "supports_image dead field must be removed"
    assert not hasattr(metadata, "supports_tools"), "supports_tools dead field must be removed"
    assert not hasattr(metadata, "supports_streaming"), "supports_streaming dead field must be removed"


def test_resolve_anthropic_metadata_extra_request_body_preserved() -> None:
    """K2.6 extra_request_body must roundtrip exactly — thinking signature chain depends on this."""
    metadata = resolve_model_metadata("anthropic", "kimiCoding:K2.6")
    assert metadata.provider == "anthropic"
    assert metadata.model == "kimiCoding:K2.6"
    assert metadata.extra_request_body == {"thinking": {"type": "adaptive"}}


def test_resolve_unknown_anthropic_model_inherits_extra_request_body() -> None:
    metadata = resolve_model_metadata("anthropic", "custom:unknown-model")
    assert metadata.model == "custom:unknown-model"
    assert metadata.extra_request_body == {"thinking": {"type": "adaptive"}}


def test_get_default_provider() -> None:
    assert get_default_provider() == "anthropic"


def test_list_supported_providers() -> None:
    providers = list_supported_providers()
    assert "anthropic" in providers
    assert "openai_compat" in providers


def test_list_provider_models_anthropic() -> None:
    models = list_provider_models("anthropic")
    model_names = [m.model for m in models]
    assert "kimiCoding:K2.6" in model_names


# ---------------------------------------------------------------------------
# 工厂化行为测试：未 init 时硬失败
# ---------------------------------------------------------------------------


def test_not_initialized_raises_runtime_error() -> None:
    """Registry must raise RuntimeError when not initialized, not silently return defaults."""
    _reset_for_tests()
    with pytest.raises(RuntimeError, match="not initialized"):
        get_default_model("anthropic")


def test_reset_and_reinit() -> None:
    """After reset, init with new payload must work correctly."""
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    _reset_for_tests()
    with pytest.raises(RuntimeError):
        list_supported_providers()

    payload = LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://test:4000",
                models=(LLMModelPayload(name="test:model"),),
            ),
        ),
    )
    init_model_registry(payload)
    assert get_default_model("anthropic") == "test:model"
    assert get_default_base_url("anthropic") == "http://test:4000"


def test_double_init_raises() -> None:
    """Calling init_model_registry twice without reset must raise RuntimeError."""
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    _reset_for_tests()
    payload = LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://test:4000",
                models=(LLMModelPayload(name="test:model"),),
            ),
        ),
    )
    init_model_registry(payload)
    with pytest.raises(RuntimeError, match="already initialized"):
        init_model_registry(payload)


def test_get_default_base_url_returns_none_when_not_configured() -> None:
    """get_default_base_url must return None when provider.base_url is None — not empty string."""
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

    _reset_for_tests()
    payload = LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url=None,
                models=(LLMModelPayload(name="test:model"),),
            ),
        ),
    )
    init_model_registry(payload)
    result = get_default_base_url("anthropic")
    assert result is None, "base_url=None in config must propagate as None, not ''"


def test_from_env_raises_when_no_base_url_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLMFactoryConfig.from_env() must raise ValueError when env and config both lack base_url."""
    import os
    from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
    from agent.core.llm.factory import LLMFactoryConfig

    _reset_for_tests()
    payload = LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url=None,
                models=(LLMModelPayload(name="test:model"),),
            ),
        ),
    )
    init_model_registry(payload)

    monkeypatch.delenv("NANO_MULTIAGENT_LLM_BASE_URL", raising=False)

    with pytest.raises(ValueError, match="base_url unset for provider"):
        LLMFactoryConfig.from_env()
