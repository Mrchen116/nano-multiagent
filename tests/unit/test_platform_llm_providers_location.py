"""Verify platform/llm/providers is importable and re-exports protocol adapters."""


def test_platform_llm_providers_anthropic_importable() -> None:
    """After migration, anthropic provider must be importable from platform path."""
    from nano_multiagent.platform.llm.providers import anthropic  # noqa: F401


def test_platform_llm_providers_openai_compat_importable() -> None:
    """After migration, openai_compat provider must be importable from platform path."""
    from nano_multiagent.platform.llm.providers import openai_compat  # noqa: F401


def test_old_llm_protocols_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for llm.protocols."""
    from nano_multiagent.llm.protocols import anthropic, openai_compat  # noqa: F401
