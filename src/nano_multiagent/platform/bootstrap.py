"""Platform bootstrap: resolve a ProductProfile into ready-to-inject objects.

Architecture contract:
- This module is the only place that knows about ProductProfile.
- The runtime/loop/agent code receives resolved objects (ToolRegistry,
  HookRegistry, etc.) and never receives a ProductProfile or product_id.
- This keeps the execution kernel product-agnostic.
"""

from __future__ import annotations

from pathlib import Path

from nano_multiagent.hooks.loader import build_hook_registry
from nano_multiagent.tools.loader import build_tool_registry

from .product import ProductProfile, ResolvedProductConfig


def bootstrap_product(
    *,
    profile: ProductProfile,
    repo_root: Path,
) -> ResolvedProductConfig:
    """Resolve a ProductProfile into concrete, ready-to-inject objects.

    Assembles the ToolRegistry, HookRegistry, and resolved system prompt from
    the given profile. The caller (server/app, tests) receives a
    ResolvedProductConfig and passes individual fields to the runtime; the
    runtime never sees the ProfileProduct or product_id.

    Args:
        profile: Product configuration describing defaults and policies.
        repo_root: Workspace root used for hook/tool discovery; should be
            the actual project root at runtime.

    Returns:
        ResolvedProductConfig with wired registries and resolved system prompt.
        ``session_store`` is ``None`` here — M74 defers store path resolution
        to the server; M75 will wire product-specific store paths.
    """

    resolved_root = Path(repo_root).expanduser().resolve()

    # Resolve system prompt: use profile default when set, otherwise let the
    # server/runtime fall back to the platform-level DEFAULT_SYSTEM_PROMPT.
    from nano_multiagent.agent.prompting import DEFAULT_SYSTEM_PROMPT

    resolved_system_prompt = profile.default_system_prompt or DEFAULT_SYSTEM_PROMPT

    # Build hook registry using platform defaults (builtin + workspace).
    # ProductProfile.default_hook_modules is reserved for future filtering (M75+).
    hook_registry = build_hook_registry(repo_root=resolved_root)

    # Build tool registry without a hook_runner initially; the server wires
    # the hook_runner after it creates the HookRunner wrapper.
    tool_registry = build_tool_registry(
        repo_root=resolved_root,
        hook_runner=None,
        runtime=None,
    )

    # session_store=None: M74 scope only introduces the seam; M75 will wire
    # product-specific SQLite paths based on config_namespace.
    return ResolvedProductConfig(
        product_id=profile.product_id,
        resolved_system_prompt=resolved_system_prompt,
        tool_registry=tool_registry,
        hook_registry=hook_registry,
        session_store=None,
    )
