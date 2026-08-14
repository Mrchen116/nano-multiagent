"""Unit tests for external runtime final projections."""

from __future__ import annotations

from personal_assistant.config.local_store import DisplayConfig
from personal_assistant.gateway.runtime_footer import (
    ExternalFinalProjection,
    TerminalFooterFacts,
    build_external_final_projection,
)


def test_projection_defaults_to_plain_text() -> None:
    assert build_external_final_projection(
        "Answer.",
        config=DisplayConfig(),
        channel_name="feishu:agent-a",
        facts=TerminalFooterFacts(
            model="codex_oauth:gpt-5.5",
            prompt_tokens=42_000,
            context_window=100_000,
        ),
    ) == ExternalFinalProjection(text="Answer.")


def test_feishu_projection_uses_card_footer_and_rounds_context() -> None:
    assert build_external_final_projection(
        "Answer.",
        config=DisplayConfig(
            runtime_footer_enabled=False,
            platform_runtime_footer_enabled={"feishu": True},
        ),
        channel_name="feishu:agent-a",
        facts=TerminalFooterFacts(
            model="provider/path/gpt-5.4",
            prompt_tokens=42_499,
            context_window=100_000,
        ),
    ) == ExternalFinalProjection(
        text="Answer.",
        runtime_footer="gpt-5.4 · ctx 42%",
    )


def test_non_feishu_projection_retains_compatible_text_presentation() -> None:
    assert build_external_final_projection(
        "Answer.",
        config=DisplayConfig(runtime_footer_enabled=True),
        channel_name="future-channel",
        facts=TerminalFooterFacts(
            model="gpt-5.4",
            prompt_tokens=42_500,
            context_window=100_000,
        ),
    ) == ExternalFinalProjection(text="Answer.\n\ngpt-5.4 · ctx 43%")


def test_projection_platform_override_can_disable_global() -> None:
    assert build_external_final_projection(
        "Answer.",
        config=DisplayConfig(
            runtime_footer_enabled=True,
            platform_runtime_footer_enabled={"feishu": False},
        ),
        channel_name="feishu:agent-a",
        facts=TerminalFooterFacts(model="gpt-5.4"),
    ) == ExternalFinalProjection(text="Answer.")


def test_projection_omits_missing_facts_and_clamps_context() -> None:
    enabled = DisplayConfig(runtime_footer_enabled=True)
    assert build_external_final_projection(
        "Answer.",
        config=enabled,
        channel_name="future-channel",
        facts=TerminalFooterFacts(model="gpt-5.4"),
    ) == ExternalFinalProjection(text="Answer.\n\ngpt-5.4")
    assert build_external_final_projection(
        "Answer.",
        config=enabled,
        channel_name="future-channel",
        facts=TerminalFooterFacts(
            model=None,
            prompt_tokens=200,
            context_window=100,
        ),
    ) == ExternalFinalProjection(text="Answer.\n\nctx 100%")
    assert build_external_final_projection(
        "Answer.",
        config=enabled,
        channel_name="future-channel",
        facts=TerminalFooterFacts(prompt_tokens=0, context_window=100),
    ) == ExternalFinalProjection(text="Answer.\n\nctx 0%")
    assert build_external_final_projection(
        "Answer.",
        config=enabled,
        channel_name="future-channel",
        facts=TerminalFooterFacts(),
    ) == ExternalFinalProjection(text="Answer.")


def test_projection_compacts_an_oversized_model_label() -> None:
    projection = build_external_final_projection(
        "Answer.",
        config=DisplayConfig(runtime_footer_enabled=True),
        channel_name="feishu:agent-a",
        facts=TerminalFooterFacts(model="x" * 30_000),
    )

    assert projection.runtime_footer.endswith("...")
    assert len(projection.runtime_footer) == 512
