"""Product profile and resolved configuration contracts.

Architecture note: ProductProfile lives in the platform layer. The core
runtime/loop layer only receives resolved objects (ToolRegistry, HookRegistry,
etc.) and never sees product_id or profile structures. This keeps the kernel
product-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nano_multiagent.hooks.registry import HookRegistry
    from nano_multiagent.session.stores.base import SessionStore
    from nano_multiagent.tools.registry import ToolRegistry


@dataclass
class ProductProfile:
    """Declarative configuration for a product variant.

    A product profile is the single source of truth for what defaults a
    product ships with. It is resolved once at startup by ``bootstrap_product``
    into a ``ResolvedProductConfig`` that the runtime/server can consume
    directly without any product-conditional branching.

    Args:
        product_id: Stable machine identifier (e.g. ``"local_coding"``).
        display_name: Human-readable product name shown in UI/logs.
        config_namespace: Config directory prefix (e.g. ``.nanocode``).
        default_system_prompt: System prompt template; ``None`` means use the
            platform-level default.
        default_tool_ids: Ordered list of built-in tool ids to activate; ``None``
            means activate all registered built-ins.
        default_hook_modules: Hook module names to enable by default; ``None``
            means load all built-in hooks.
        skill_search_policy: How skills are discovered (e.g.
            ``"workspace"``). Reserved for future M75+ wiring.
        session_store_policy: Backing store type (e.g. ``"sqlite"``). Reserved
            for M75 session store migration.
        safety_defaults: Mapping of safety flag overrides; merged over
            platform-level safety config at bootstrap time.
        capabilities: Freeform capability flags (e.g. ``{"multi_tool": True}``).
    """

    # --- Identity ---
    product_id: str
    display_name: str
    config_namespace: str

    # --- Prompt ---
    default_system_prompt: str | None = None

    # --- Tool / Hook enablement ---
    # None = "use platform defaults" (i.e. all built-ins + workspace)
    default_tool_ids: list[str] | None = None
    default_hook_modules: list[str] | None = None

    # --- Policies (reserved for M75+) ---
    skill_search_policy: str | None = None
    session_store_policy: str | None = None

    # --- Safety / capabilities ---
    safety_defaults: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedProductConfig:
    """Resolved, ready-to-inject objects assembled from a ProductProfile.

    Bootstrap resolves a ProductProfile into concrete instances that the
    server/runtime can consume. The runtime never sees the ProductProfile;
    it only receives these resolved objects.

    Args:
        product_id: Source product identifier (for tracing/logging only).
        resolved_system_prompt: Final system prompt string after template
            resolution. May still contain ``<RUNTIME_FILL:*>`` placeholders
            that are expanded per-turn by the prompt builder.
        tool_registry: Wired tool registry. ``None`` until bootstrap completes.
        hook_registry: Wired hook registry. ``None`` until bootstrap completes.
        session_store: Session backing store. ``None`` when the product defers
            to the server default.
    """

    product_id: str
    resolved_system_prompt: str

    # Resolved registries; None signals "use server/app default"
    tool_registry: "ToolRegistry | None"
    hook_registry: "HookRegistry | None"
    session_store: "SessionStore | None"
