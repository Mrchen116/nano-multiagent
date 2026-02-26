from nano_multiagent.llm.model_registry import get_default_model, resolve_model_metadata


def test_openai_compat_default_model() -> None:
    assert get_default_model("openai_compat") == "codexOAuth:gpt-5.2-codex"


def test_resolve_model_metadata_has_text_capability() -> None:
    metadata = resolve_model_metadata("openai_compat", "codexOAuth:gpt-5.2-codex")

    assert metadata.provider == "openai_compat"
    assert metadata.model == "codexOAuth:gpt-5.2-codex"
    assert metadata.supports_text is True
