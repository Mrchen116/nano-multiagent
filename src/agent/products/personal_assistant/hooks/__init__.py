"""Hook module exports for the personal_assistant product."""

from .communication_context import DEFAULT_HOOK_MODULES, _build_communication_context_block, setup

__all__ = ["DEFAULT_HOOK_MODULES", "setup", "_build_communication_context_block"]
