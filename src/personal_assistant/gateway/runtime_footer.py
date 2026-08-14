"""Format optional runtime facts for a completed external assistant reply."""

from __future__ import annotations

from dataclasses import dataclass
import math

from personal_assistant.config.local_store import DisplayConfig


@dataclass(frozen=True, slots=True)
class TerminalFooterFacts:
    """The terminal runtime facts eligible for an external reply footer."""

    model: str | None = None
    prompt_tokens: int | None = None
    context_window: int | None = None


def format_external_final_text(
    text: str,
    *,
    config: DisplayConfig,
    channel_name: str,
    facts: TerminalFooterFacts,
) -> str:
    """Append one enabled external runtime footer, or preserve plain text.

    The caller owns terminal-event timing and supplies the run-bound facts.  This
    module only applies stable display policy so adapter and fallback paths can
    reuse one exact projection.
    """

    if not _runtime_footer_enabled(config, channel_name):
        return text
    values = _footer_values(facts)
    return f"{text}\n\n{' · '.join(values)}" if values else text


def _runtime_footer_enabled(config: DisplayConfig, channel_name: str) -> bool:
    platform = channel_name.split(":", 1)[0]
    return config.platform_runtime_footer_enabled.get(
        platform, config.runtime_footer_enabled
    )


def _footer_values(facts: TerminalFooterFacts) -> list[str]:
    values: list[str] = []
    model = facts.model.strip() if isinstance(facts.model, str) else ""
    display_model = model.rsplit("/", 1)[-1].strip()
    if display_model:
        values.append(display_model)
    if (
        isinstance(facts.prompt_tokens, int)
        and facts.prompt_tokens >= 0
        and isinstance(facts.context_window, int)
        and facts.context_window > 0
    ):
        percentage = math.floor(100 * facts.prompt_tokens / facts.context_window + 0.5)
        values.append(f"{min(100, max(0, percentage))}%")
    return values
