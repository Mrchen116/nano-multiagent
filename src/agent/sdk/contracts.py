"""SDK-owned structural Protocols for the tool/hook extension surface (refactor-406 决策 2).

Applications extend the kernel by passing native ``Tool`` objects and ``setup``
hooks through ``build_kernel(tools=…, hooks=…)`` — no inheritance of kernel base
classes, no ``agent/products/`` directory. The contracts here are runtime-checkable
structural Protocols (duck typing): an object satisfies ``Tool`` if it exposes
``name`` / ``description`` / ``input_schema`` / ``run(args, ctx)`` — exactly the
shape the platform tool loader already checks (``loader._is_tool``).

``ToolContext`` and ``HookAPI`` declare only the **promised** field/method subset
the kernel guarantees to extension authors; non-promised attributes are not part
of the contract. They are Protocols (not concrete classes) so the kernel can keep
constructing its own real ``core.tools.base.ToolContext`` / ``core.hooks.registry.HookAPI``
without importing agent.sdk (which would invert core→sdk). The real kernel objects
satisfy these Protocols structurally.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class ToolContext(Protocol):
    """Promised execution-context fields passed to ``Tool.run`` (决策 2).

    The kernel passes its own ToolContext object; these are the fields an
    extension author may rely on. Other attributes the kernel happens to set are
    not part of the contract and may change.

    Attributes:
        repo_root: Agent workspace root (Path).
        cwd: Current working directory for this turn.
        session_id: Kernel session id that triggered the tool call.
        session_metadata: Session metadata dict (e.g. ``agent_id`` for routing).
    """

    repo_root: Any
    cwd: Any
    session_id: Any
    session_metadata: Mapping[str, Any]


@runtime_checkable
class Tool(Protocol):
    """Structural contract for a native tool object (决策 2).

    An object satisfies ``Tool`` when it exposes the four required members below;
    it need not inherit any kernel base class. Side-effect tools (e.g. a cron tool
    that talks to a Gateway scheduler) close over their own service handles in the
    application package and are passed via ``build_kernel(tools=…)`` — there is
    no host-capability callback channel back into the kernel (决策 9).

    Attributes:
        name: Stable tool name surfaced to the model and used in ``enabled_tools``.
        description: Human/model-facing description.
        input_schema: JSON-schema dict for the tool arguments.
        presenter: *Optional* ``ToolPresenter`` (决策 12) describing how the tool's
            calls render in the IM (label / summary / detail on ``tool_start`` /
            ``tool_end``). Tool presentation travels with the tool object: a product
            that brings a tool also brings its render card. When absent (the common
            case for MCP / ``.nano/tools`` runtime-discovered tools) the kernel uses
            a default presenter (visible + truncated args). Declared as an optional
            attribute, **not** a required Protocol member — the kernel reads it via
            ``getattr(tool, "presenter", None)`` so existing tools without one still
            satisfy ``isinstance(obj, Tool)``.

    Methods:
        run: ``(args: Mapping, ctx: ToolContext) -> Mapping`` — execute the tool.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any]

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Execute the tool with the given arguments and context."""
        ...


@runtime_checkable
class HookAPI(Protocol):
    """Promised hook-registration surface passed to a ``setup(hooks)`` callable (决策 2).

    A hook module is a callable ``setup(hooks: HookAPI) -> None`` registered via
    ``build_kernel(hooks=…)``. It registers handlers with ``hooks.on(event, handler,
    mode=…)``. Hooks observe/intercept tool calls and run background work; they do
    **not** inject the system prompt (决策 8 — the system prompt is per-session via
    PromptSlots). The event-name set is part of the public contract.
    """

    def on(self, event: str, handler: Any, *, mode: Any = ..., **kwargs: Any) -> Any:
        """Register a hook handler for an event."""
        ...


__all__ = ["Tool", "ToolContext", "HookAPI"]
