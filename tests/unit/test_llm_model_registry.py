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
    provider_of,
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
    assert not hasattr(metadata, "supports_text"), (
        "supports_text dead field must be removed"
    )
    assert not hasattr(metadata, "supports_image"), (
        "supports_image dead field must be removed"
    )
    assert not hasattr(metadata, "supports_tools"), (
        "supports_tools dead field must be removed"
    )
    assert not hasattr(metadata, "supports_streaming"), (
        "supports_streaming dead field must be removed"
    )


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


def test_resolve_model_metadata_empty_provider_raises_clearly() -> None:
    """bugfix-429: a provider with no models must fail with a clear ValueError, not
    a bare StopIteration from ``next(iter(...))`` on an empty model map."""
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )

    _reset_for_tests()
    payload = LLMConfigPayload(
        default_model="kimiCoding:K2.6",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModelPayload(name="kimiCoding:K2.6"),),
            ),
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(),
            ),
        ),
    )
    init_model_registry(payload)
    with pytest.raises(ValueError, match="no models registered"):
        resolve_model_metadata("openai_compat", None)


def test_provider_of_reverse_lookup() -> None:
    """bugfix-429 R2: model id → owning provider, for multi-client routing."""
    assert provider_of("kimiCoding:K2.6") == "anthropic"
    assert provider_of("codex_oauth:gpt-5.5") == "openai_compat"


def test_provider_of_unknown_model_raises() -> None:
    """Unknown model has no registered provider — fail loud, never guess (禁兜底)."""
    with pytest.raises(ValueError, match="no registered provider"):
        provider_of("nonexistent:model")


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
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )

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
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )

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
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )

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


def test_from_env_raises_when_no_base_url_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLMFactoryConfig.from_env() must raise ValueError when env and config both lack base_url."""
    import os
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )
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


# ---------------------------------------------------------------------------
# feat-436: per-model context_window 进注册表 + 安全查询 helper
# ---------------------------------------------------------------------------


def _init_windows_registry() -> None:
    """重置注册表为带 context_window 的目录（conftest autouse 在下个测试前复原默认）。"""
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )

    _reset_for_tests()
    init_model_registry(
        LLMConfigPayload(
            default_model="big-window",
            providers=(
                LLMProviderPayload(
                    name="anthropic",
                    base_url="http://127.0.0.1:4000",
                    models=(
                        LLMModelPayload(name="big-window", context_window=1_000_000),
                        LLMModelPayload(name="no-window"),
                        LLMModelPayload(name="zero-window", context_window=0),
                    ),
                ),
            ),
        )
    )


def test_context_window_propagates_into_model_metadata() -> None:
    _init_windows_registry()
    assert resolve_model_metadata("anthropic", "big-window").context_window == 1_000_000
    assert resolve_model_metadata("anthropic", "no-window").context_window is None


def test_context_window_for_model_returns_configured_value() -> None:
    from agent.core.llm.model_registry import context_window_for_model

    _init_windows_registry()
    assert context_window_for_model("big-window") == 1_000_000


def test_context_window_for_model_unconfigured_returns_none() -> None:
    from agent.core.llm.model_registry import context_window_for_model

    _init_windows_registry()
    assert context_window_for_model("no-window") is None


def test_context_window_for_model_invalid_value_returns_none() -> None:
    from agent.core.llm.model_registry import context_window_for_model

    _init_windows_registry()
    # 配成 0（非正整数）→ 当未配处理
    assert context_window_for_model("zero-window") is None


def test_context_window_for_model_unknown_id_returns_none() -> None:
    from agent.core.llm.model_registry import context_window_for_model

    _init_windows_registry()
    assert context_window_for_model("never-registered") is None
    assert context_window_for_model(None) is None
    assert context_window_for_model("") is None


def test_context_window_for_model_uninitialized_registry_returns_none() -> None:
    """注册表未初始化（单测 / fork 路径）时不抛错，返回 None 让调用方回退。"""
    from agent.core.llm.model_registry import context_window_for_model

    _reset_for_tests()
    assert context_window_for_model("big-window") is None


def test_sdk_from_payload_carries_context_window_into_registry() -> None:
    """端到端：PA 风格 payload → SDK LLMConfig.from_payload → build_kernel 注册表初始化."""
    from agent.core.llm.config import (
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )
    from agent.core.llm.model_registry import context_window_for_model
    from agent.sdk import LLMConfig
    from agent.sdk.kernel import _init_model_registry_from_llm_config

    payload = LLMConfigPayload(
        default_model="big-window",
        providers=(
            LLMProviderPayload(
                name="anthropic",
                base_url="http://x",
                models=(
                    LLMModelPayload(name="big-window", context_window=512_000),
                    LLMModelPayload(name="no-window"),
                ),
            ),
        ),
    )
    _reset_for_tests()
    _init_model_registry_from_llm_config(LLMConfig.from_payload(payload))
    assert context_window_for_model("big-window") == 512_000
    assert context_window_for_model("no-window") is None
