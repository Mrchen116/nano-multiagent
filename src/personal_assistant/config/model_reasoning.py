"""Personal Assistant parsing for SDK-owned model reasoning capabilities."""

from __future__ import annotations

from typing import Any

from agent.sdk import ModelReasoningCapability, ModelReasoningCatalog


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

    return ModelReasoningCapability.from_payload(value, field_name=field_name)


__all__ = [
    "ModelReasoningCapability",
    "ModelReasoningCatalog",
    "parse_model_reasoning",
]
