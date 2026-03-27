from agent.core.llm.model_registry import (
    get_default_base_url,
    get_default_model,
    resolve_model_metadata,
)


def test_openai_compat_default_model() -> None:
    assert get_default_model("openai_compat") == "codex_oauth:gpt-5.4"


def test_resolve_model_metadata_has_text_capability() -> None:
    metadata = resolve_model_metadata("openai_compat", "codex_oauth:gpt-5.4")

    assert metadata.provider == "openai_compat"
    assert metadata.model == "codex_oauth:gpt-5.4"
    assert metadata.supports_text is True


def test_anthropic_default_model_and_base_url() -> None:
    assert get_default_model("anthropic") == "moonshotAnthropic:kimi-k2.5"
    assert get_default_base_url("anthropic") == "http://127.0.0.1:4000"


def test_resolve_anthropic_metadata_has_text_capability() -> None:
    metadata = resolve_model_metadata("anthropic", "moonshotAnthropic:kimi-k2.5")

    assert metadata.provider == "anthropic"
    assert metadata.model == "moonshotAnthropic:kimi-k2.5"
    assert metadata.supports_text is True
    assert metadata.supports_streaming is False
