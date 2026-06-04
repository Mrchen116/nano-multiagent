"""Platform-level tool base classes and shared helpers.

Re-exports the core Tool/ToolContext contracts, and provides platform-level
mixins for tools that need late-bound wiring (e.g. background task runner).
"""

from typing import Any

from agent.core.errors import ToolError
from agent.core.tools.base import Tool, ToolContext


class WiringMixin:
    """Mixin for tools that receive a background-task wiring object after construction.

    Three builtins (bash, task_stop, agent) each carried a private copy of
    bind_wiring / _require_wiring — consolidated here as refactor-395-M1.
    The concrete class must:
    - Declare a ``name: str`` attribute (used in ToolError messages).
    - Set ``self._wiring: Any | None`` in its own ``__init__`` (typically to None
      or an optional constructor argument).
    """

    name: str  # Provided by the concrete tool class.
    _wiring: Any  # Set by the concrete class __init__.

    def bind_wiring(self, wiring: Any | None) -> None:
        """Bind background task wiring after bootstrap."""
        self._wiring = wiring

    def _require_wiring(self) -> Any:
        """Return wiring or raise ToolError if not yet bound.

        Returns:
            The wiring object bound via bind_wiring().

        Raises:
            ToolError: If _wiring is None.
        """
        if self._wiring is None:
            raise ToolError(
                "background task wiring is not configured", tool_name=self.name
            )
        return self._wiring


__all__ = ["Tool", "ToolContext", "WiringMixin"]
