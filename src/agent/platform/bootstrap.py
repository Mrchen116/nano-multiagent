"""Platform bootstrap: resolve a ProductProfile into ready-to-inject objects.

Architecture contract:
- This module is the only place that knows about ProductProfile.
- The runtime/loop/agent code receives resolved objects (ToolRegistry,
  HookRegistry, etc.) and never receives a ProductProfile or product_id.
- This keeps the execution kernel product-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import logging

from agent.core.hooks.registry import HookRegistry
from agent.core.skills.discovery import default_skill_search_roots
from agent.core.skills.registry import SkillRegistry
from agent.platform.config.resolver import ConfigResolver
from agent.platform.hooks.loader import build_hook_registry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.tools.builtins.memory import MemoryTool
from agent.platform.tools.builtins.skill_manage import SkillManageTool
from agent.platform.tools.loader import build_tool_registry
from agent.platform.tools.registry import ToolRegistry

from agent.products.base import ProductProfile, ResolvedProductConfig

_logger = logging.getLogger(__name__)

# Default self_evolution config injected when no workspace config file exists.
_DEFAULT_SELF_EVOLUTION_CONFIG: dict = {
    "enabled": True,
    "skill_creation": True,
    "memory_curation": True,
    "skill_nudge_interval": 10,
    "memory_nudge_interval": 10,
}


def _product_root(profile: ProductProfile) -> Path:
    return Path(__file__).resolve().parents[1] / "products" / profile.product_id


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
    config_resolver = None
    if profile.global_config_home is not None:
        config_resolver = ConfigResolver(profile=profile, workspace_root=resolved_root)

    # Use profile's declared prompt; empty string signals "no product prompt set".
    # Callers (server/runtime) should supply a product profile with a non-empty
    # default_system_prompt; the empty fallback is intentional — it forces
    # product owners to declare their prompt rather than inheriting a shared one.
    resolved_system_prompt = profile.default_system_prompt or ""

    # Build hook registry.  When default_hook_modules is declared, only the
    # specified module stems (e.g. "bash_risk_gate") are retained; otherwise
    # all built-in hooks are loaded (None = platform default "load all").
    product_root = _product_root(profile)

    full_hook_registry = build_hook_registry(
        repo_root=resolved_root,
        config_resolver=config_resolver,
        product_hook_dir=product_root / "hooks",
    )
    if profile.default_hook_modules is not None:
        hook_registry = _filter_hook_registry(full_hook_registry, profile.default_hook_modules)
    else:
        hook_registry = full_hook_registry

    # Build tool registry without a hook_runner initially; the server wires
    # the hook_runner after it creates the HookRunner wrapper.
    # When default_tool_ids is declared the registry is built from the union of
    # default_tool_ids + optional_tool_ids so that optional tools (e.g.
    # send_message) are physically present for per-session allowlist filtering,
    # while the resolved config records default_tool_ids separately so the
    # runtime can apply the product default gate when no per-session allowlist
    # is supplied.
    full_tool_registry = build_tool_registry(
        repo_root=resolved_root,
        hook_runner=None,
        runtime=None,
        config_resolver=config_resolver,
        product_tool_dir=product_root / "tools",
    )
    if profile.default_tool_ids is not None:
        # Include both default and optional ids so optional tools are accessible
        # when an explicit tool_allowlist enables them on a per-session basis.
        combined_ids = list(profile.default_tool_ids) + [
            tid for tid in profile.optional_tool_ids
            if tid not in profile.default_tool_ids
        ]
        tool_registry = _filter_tool_registry(full_tool_registry, combined_ids)
    else:
        tool_registry = full_tool_registry

    session_store = JsonlSessionStore(data_dir=resolved_root / ".nano")

    skill_registry = SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=resolved_root,
            config_resolver=config_resolver,
            product_skill_root=product_root / "skills",
        )
    )

    # Register self-evolution tools when config_resolver provides resolved paths.
    # These tools require constructor-time path arguments; they are NOT in the
    # default builtin_tools() tuple (see platform/tools/builtins/__init__.py).
    if config_resolver is not None:
        skill_roots = config_resolver.user_skill_roots()
        # Prefer workspace skill root (first in precedence); fall back to global.
        skill_root = skill_roots[0] if skill_roots else config_resolver.global_config_root() / "skills"
        memory_root = config_resolver.user_memory_root()

        skill_manage_tool = SkillManageTool(skill_root=skill_root, registry=skill_registry)
        tool_registry.register(skill_manage_tool, replace=True)

        memory_tool = MemoryTool(memory_root=memory_root)
        tool_registry.register(memory_tool, replace=True)

    # Read workspace config file for self_evolution settings.
    default_session_metadata: dict = {}
    if config_resolver is not None:
        workspace_config_root = config_resolver.workspace_config_root()
        if workspace_config_root is not None:
            self_evo_config = _load_self_evolution_config(workspace_config_root / "config.yaml")
            default_session_metadata["self_evolution"] = self_evo_config
        else:
            default_session_metadata["self_evolution"] = dict(_DEFAULT_SELF_EVOLUTION_CONFIG)

    return ResolvedProductConfig(
        product_id=profile.product_id,
        resolved_system_prompt=resolved_system_prompt,
        tool_registry=tool_registry,
        hook_registry=hook_registry,
        session_store=session_store,
        config_resolver=config_resolver,
        skill_registry=skill_registry,
        default_tool_ids=list(profile.default_tool_ids) if profile.default_tool_ids is not None else None,
        default_session_metadata=default_session_metadata,
    )


def _load_self_evolution_config(config_path: Path) -> dict:
    """Read self_evolution section from a workspace config YAML file.

    Falls back to the platform default (all features enabled, interval=10) when
    the file does not exist or is malformed.

    Args:
        config_path: Path to the workspace config YAML file.

    Returns:
        Dictionary with self_evolution settings (always a valid, complete dict).
    """
    if not config_path.is_file():
        return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
    try:
        import yaml  # noqa: PLC0415 — imported lazily to keep core dependencies minimal

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        user_evo = raw.get("self_evolution", {})
        if not isinstance(user_evo, dict):
            return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        # Merge user values over platform defaults so missing keys get defaults.
        result = dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        result.update(user_evo)
        return result
    except Exception:
        _logger.warning("Failed to read workspace config %s; using defaults", config_path, exc_info=True)
        return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)


def _filter_tool_registry(full: ToolRegistry, allowed_ids: list[str]) -> ToolRegistry:
    """Return a new ToolRegistry containing only tools in ``allowed_ids``.

    Args:
        full: Fully-populated registry to filter.
        allowed_ids: Ordered list of tool names to include.

    Returns:
        New ToolRegistry with only the allowed tools registered.
    """

    allowed_set = set(allowed_ids)
    filtered = ToolRegistry(context=full.context)
    for spec in full.list_specs():
        if spec.name in allowed_set:
            filtered.register(full._tools[spec.name])  # type: ignore[attr-defined]
    return filtered


def _filter_hook_registry(full: HookRegistry, allowed_modules: list[str]) -> HookRegistry:
    """Return a new HookRegistry containing only hooks from ``allowed_modules``.

    Hooks are identified by the stem (filename without extension) of their
    source module, as declared in ``ProductProfile.default_hook_modules``.

    Args:
        full: Fully-populated registry to filter.
        allowed_modules: List of module stems to include (e.g. ``"bash_risk_gate"``).

    Returns:
        New HookRegistry with only hooks from allowed modules.
    """

    allowed_set = set(allowed_modules)
    filtered = HookRegistry()
    for registration in full.all_handlers():
        # Filter by file_path stem; registrations without a file_path (e.g.
        # inline test hooks) are always included to avoid over-eager filtering.
        file_path = registration.file_path
        if file_path is not None:
            stem = Path(file_path).stem
            if stem not in allowed_set:
                continue
        filtered.on(
            registration.event,
            registration.handler,
            priority=registration.priority,
            timeout_ms=registration.timeout_ms,
            mode=registration.mode,
            source=registration.source,
            module_name=registration.module_name,
            file_path=registration.file_path,
        )
    return filtered
