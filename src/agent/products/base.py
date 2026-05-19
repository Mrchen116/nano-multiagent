"""Canonical product contracts for product-owned defaults and resolved wiring.

This module is the stable home for product-level configuration objects. The
platform layer may assemble or resolve these profiles, but the contract itself
belongs to the canonical ``agent.products`` package so product
packages can be treated as first-class application surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.core.hooks.registry import HookRegistry
    from agent.core.session.jsonl_store import JsonlSessionStore
    from agent.platform.config.resolver import ConfigResolver
    from agent.platform.tools.registry import ToolRegistry


@dataclass
class ProductProfile:
    """Declare the defaults, policies, and layouts for a product variant.

    A product profile is the single source of truth for product-owned defaults.
    Bootstrap resolves it once at startup into a ``ResolvedProductConfig`` that
    runtime and server layers can consume without product-conditional branches.

    Args:
        product_id: Stable machine identifier (for example ``"local_coding"``).
        display_name: Human-readable product name shown in UI and logs.
        config_namespace: Product config namespace used by resolver-owned paths.
        default_system_prompt: Product-owned default system prompt. ``None``
            means the product leaves the prompt unspecified.
        default_tool_ids: Ordered built-in tool ids enabled by default. ``None``
            means bootstrap keeps the platform default tool set.
        optional_tool_ids: Built-in tool ids that the product recognizes as
            supported but does not enable by default.
        default_hook_modules: Hook module stems enabled by default. ``None``
            means bootstrap keeps the platform default hook set.
        skill_search_policy: Product policy for skill discovery precedence.
        session_store_policy: Product policy for backing session storage.
        memory_layout: Product-owned memory contract metadata. The milestone only
            records structure here; runtime wiring can evolve later.
        heartbeat_layout: Product-owned heartbeat contract metadata. The
            milestone only records structure here; runtime wiring can evolve later.
        safety_defaults: Safety override mapping merged over platform defaults.
        capabilities: Freeform capability flags published by the product.
        global_config_home: User-global config directory path, optionally using
            ``~``. ``None`` keeps legacy fallback behavior.
        workspace_config_dirname: Per-workspace config directory name, if the
            product supports workspace-local overrides.
        session_db_filename: SQLite filename stored under ``global_config_home``.
        compat_skill_roots: Legacy skill directories appended at lowest priority.
    """

    product_id: str
    display_name: str
    config_namespace: str

    default_system_prompt: str | None = None

    # None means "keep platform default behavior"; lists make product defaults explicit.
    default_tool_ids: list[str] | None = None
    optional_tool_ids: list[str] = field(default_factory=list)
    default_hook_modules: list[str] | None = None

    skill_search_policy: str | None = None
    session_store_policy: str | None = None

    memory_layout: dict[str, Any] = field(default_factory=dict)
    heartbeat_layout: dict[str, Any] = field(default_factory=dict)
    safety_defaults: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)

    global_config_home: Path | None = None
    workspace_config_dirname: str | None = None
    session_db_filename: str = "sessions.sqlite3"
    compat_skill_roots: list[Path] = field(default_factory=list)


@dataclass
class ResolvedProductConfig:
    """Hold the concrete objects assembled from a ``ProductProfile``.

    Args:
        product_id: Source product identifier used for tracing and logging.
        resolved_system_prompt: Final prompt string after bootstrap-owned
            resolution.
        tool_registry: Wired tool registry, or ``None`` until bootstrap chooses
            the effective registry.
        hook_registry: Wired hook registry, or ``None`` until bootstrap chooses
            the effective registry.
        session_store: Session backing store, or ``None`` when the product
            defers to server defaults.
        config_resolver: Resolver used to derive product-owned filesystem roots.
    """

    product_id: str
    resolved_system_prompt: str
    tool_registry: "ToolRegistry | None"
    hook_registry: "HookRegistry | None"
    session_store: "JsonlSessionStore | None"
    config_resolver: "ConfigResolver | None" = None
    skill_registry: object | None = None
    # Tool ids exposed to the LLM by default (before per-session allowlists are
    # applied).  ``None`` uses platform default (all tools in registry).  Set by
    # bootstrap from ``ProductProfile.default_tool_ids``.
    default_tool_ids: list[str] | None = None
    # Workspace-level metadata merged into every new session created under this
    # product.  Populated from the workspace config file (e.g. .nanocode/config.yaml)
    # by bootstrap; empty when no file exists.
    default_session_metadata: dict = field(default_factory=dict)


__all__ = ["ProductProfile", "ResolvedProductConfig"]
