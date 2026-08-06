"""Kernel-scoped model selection for automatic tool approval classification."""

from __future__ import annotations

from typing import Any

from agent.core.hooks.registry import HookRegistry


_STATE_KEY = "kernel.tool_approval_model"


def set_tool_approval_model(registry: HookRegistry, model: str | None) -> None:
    """Store the optional classifier model on one Kernel hook registry.

    Args:
        registry: Hook registry owned by the Kernel being assembled.
        model: Registered model id, or ``None`` to reuse the current run model.
    """

    registry.set_extension_state(_STATE_KEY, model)


def get_tool_approval_model(hooks: Any) -> str | None:
    """Read the classifier model exposed to the canonical auto-mode gate.

    Args:
        hooks: Hook registration facade supplied by the platform loader.

    Returns:
        The configured model id, or ``None`` to reuse the current run model.
    """

    value = hooks.get_state(_STATE_KEY)
    return value if isinstance(value, str) else None
