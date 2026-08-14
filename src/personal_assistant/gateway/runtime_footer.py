"""Project optional runtime facts for completed external assistant replies."""

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


@dataclass(frozen=True, slots=True)
class ExternalFinalProjection:
    """One run-owned external final delivery representation."""

    text: str
    runtime_footer: str = ""


def build_external_final_projection(
    text: str,
    *,
    config: DisplayConfig,
    channel_name: str,
    facts: TerminalFooterFacts,
) -> ExternalFinalProjection:
    """Build one enabled external runtime projection, or preserve plain text.

    The caller owns terminal-event timing and supplies the run-bound facts.  This
    module only applies stable display policy so adapter and fallback paths reuse
    one exact representation. Feishu receives an adapter presentation hint; other
    external adapters retain the compatible text representation.
    """

    if not _runtime_footer_enabled(config, channel_name):
        return ExternalFinalProjection(text=text)
    values = _footer_values(facts)
    if not values:
        return ExternalFinalProjection(text=text)
    footer = " · ".join(values)
    if _platform_name(channel_name) == "feishu":
        return ExternalFinalProjection(text=text, runtime_footer=footer)
    return ExternalFinalProjection(text=f"{text}\n\n{footer}")


def _runtime_footer_enabled(config: DisplayConfig, channel_name: str) -> bool:
    platform = _platform_name(channel_name)
    return config.platform_runtime_footer_enabled.get(
        platform, config.runtime_footer_enabled
    )


def _platform_name(channel_name: str) -> str:
    return channel_name.split(":", 1)[0]


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
        values.append(f"ctx {min(100, max(0, percentage))}%")
    return values
