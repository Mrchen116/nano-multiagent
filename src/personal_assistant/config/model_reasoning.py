"""Model reasoning capability rules owned by the Personal Assistant gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelReasoningCapability:
    """Describe one model's public reasoning capability.

    Args:
        kind: Either ``selectable`` or ``fixed``.
        default: Recommended selectable level.
        levels: Ordered selectable levels exposed to users.
    """

    kind: str
    default: str | None = None
    levels: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        """Return the safe public capability descriptor."""

        if self.kind == "fixed":
            return {"kind": "fixed"}
        return {
            "kind": "selectable",
            "default": self.default or "",
            "levels": list(self.levels),
        }


def parse_model_reasoning(
    value: Any, *, field_name: str
) -> ModelReasoningCapability | None:
    """Parse one model's Gateway reasoning declaration.

    Args:
        value: YAML-decoded reasoning value.
        field_name: Fully qualified field name used in validation errors.

    Returns:
        Parsed capability, or ``None`` when the field is omitted.

    Raises:
        ValueError: When the declaration is malformed.
    """

    if value is None:
        return None
    if value == "fixed":
        return ModelReasoningCapability(kind="fixed")
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be 'fixed' or a mapping")
    default = value.get("default")
    if not isinstance(default, str) or not default.strip():
        raise ValueError(f"{field_name}.default must be a non-empty string")
    raw_levels = value.get("levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError(f"{field_name}.levels must be a non-empty list")
    levels: list[str] = []
    for index, raw_level in enumerate(raw_levels):
        if not isinstance(raw_level, str) or not raw_level.strip():
            raise ValueError(f"{field_name}.levels[{index}] must be a non-empty string")
        level = raw_level.strip()
        if level in levels:
            raise ValueError(f"{field_name}.levels must not contain duplicates")
        levels.append(level)
    normalized_default = default.strip()
    if normalized_default not in levels:
        raise ValueError(f"{field_name}.default must be one of {field_name}.levels")
    return ModelReasoningCapability(
        kind="selectable", default=normalized_default, levels=tuple(levels)
    )


class ModelReasoningCatalog:
    """Resolve and validate model-specific reasoning settings.

    Args:
        llm_config: PA-owned LLM catalog containing provider model entries.
    """

    def __init__(self, llm_config: object) -> None:
        self._capabilities: dict[str, ModelReasoningCapability | None] = {}
        for provider in tuple(getattr(llm_config, "providers", ()) or ()):
            for model in tuple(getattr(provider, "models", ()) or ()):
                self._capabilities[model.name] = getattr(model, "reasoning", None)

    def capability_for(self, model: str) -> ModelReasoningCapability | None:
        """Return the model's capability, or ``None`` when it has none."""

        return self._capabilities.get(model)

    def validate(self, model: str | None, selected_effort: str | None) -> None:
        """Validate one persisted model/effort pairing.

        Args:
            model: Explicit model id, or ``None`` for product-default selection.
            selected_effort: Persisted selectable effort.

        Raises:
            ValueError: When the model is unknown or the pairing is invalid.
        """

        if model is None:
            if selected_effort is not None:
                raise ValueError(
                    "reasoning_effort requires an explicitly selected model"
                )
            return
        if model not in self._capabilities:
            raise ValueError(f"unknown model: {model}")
        capability = self._capabilities[model]
        if capability is None or capability.kind == "fixed":
            if selected_effort is not None:
                raise ValueError(f"model {model!r} does not accept reasoning_effort")
            return
        if selected_effort is not None and selected_effort not in capability.levels:
            raise ValueError(
                f"reasoning_effort {selected_effort!r} is not supported by model {model!r}"
            )

    def resolve(self, model: str, selected_effort: str | None) -> str | None:
        """Resolve a valid pairing to its provider-neutral effective effort."""

        self.validate(model, selected_effort)
        capability = self._capabilities[model]
        if capability is None or capability.kind == "fixed":
            return None
        return selected_effort or capability.default


__all__ = [
    "ModelReasoningCapability",
    "ModelReasoningCatalog",
    "parse_model_reasoning",
]
