"""Unit tests for external runtime footer policy and formatting."""

from __future__ import annotations

from personal_assistant.config.local_store import DisplayConfig
from personal_assistant.gateway.runtime_footer import (
    TerminalFooterFacts,
    format_external_final_text,
)


def test_format_external_final_text_defaults_to_plain_text() -> None:
    assert (
        format_external_final_text(
            "Answer.",
            config=DisplayConfig(),
            channel_name="feishu:agent-a",
            facts=TerminalFooterFacts(
                model="codex_oauth:gpt-5.5",
                prompt_tokens=42_000,
                context_window=100_000,
            ),
        )
        == "Answer."
    )


def test_format_external_final_text_uses_platform_override_and_rounds_context() -> None:
    assert (
        format_external_final_text(
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
        )
        == "Answer.\n\ngpt-5.4 · 42%"
    )


def test_format_external_final_text_platform_override_can_disable_global() -> None:
    assert (
        format_external_final_text(
            "Answer.",
            config=DisplayConfig(
                runtime_footer_enabled=True,
                platform_runtime_footer_enabled={"feishu": False},
            ),
            channel_name="feishu:agent-a",
            facts=TerminalFooterFacts(
                model="gpt-5.4",
                prompt_tokens=42_500,
                context_window=100_000,
            ),
        )
        == "Answer."
    )


def test_format_external_final_text_omits_missing_facts_and_clamps_context() -> None:
    enabled = DisplayConfig(runtime_footer_enabled=True)
    assert (
        format_external_final_text(
            "Answer.",
            config=enabled,
            channel_name="future-channel",
            facts=TerminalFooterFacts(model="gpt-5.4"),
        )
        == "Answer.\n\ngpt-5.4"
    )
    assert (
        format_external_final_text(
            "Answer.",
            config=enabled,
            channel_name="future-channel",
            facts=TerminalFooterFacts(
                model=None,
                prompt_tokens=200,
                context_window=100,
            ),
        )
        == "Answer.\n\n100%"
    )
    assert (
        format_external_final_text(
            "Answer.",
            config=enabled,
            channel_name="future-channel",
            facts=TerminalFooterFacts(prompt_tokens=0, context_window=100),
        )
        == "Answer.\n\n0%"
    )
    assert (
        format_external_final_text(
            "Answer.",
            config=enabled,
            channel_name="future-channel",
            facts=TerminalFooterFacts(),
        )
        == "Answer."
    )
