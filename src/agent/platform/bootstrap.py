"""Platform bootstrap: resolve a ProductProfile into ready-to-inject objects.

Architecture contract:
- This module is the only place that knows about ProductProfile.
- The runtime/loop/agent code receives resolved objects (ToolRegistry,
  HookRegistry, etc.) and never receives a ProductProfile or product_id.
- This keeps the execution kernel product-agnostic.
"""

from __future__ import annotations

from pathlib import Path

from agent.core.hooks.registry import HookRegistry
from agent.core.skills.discovery import default_skill_search_roots
from agent.core.skills.registry import SkillRegistry
from agent.platform.config.resolver import ConfigResolver
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
from agent.platform.tools.loader import build_tool_registry
from agent.platform.tools.registry import ToolRegistry

from agent.products.base import ProductProfile, ResolvedProductConfig


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
    # When default_tool_ids is declared, only those tool names are kept.
    full_tool_registry = build_tool_registry(
        repo_root=resolved_root,
        hook_runner=None,
        runtime=None,
        config_resolver=config_resolver,
        product_tool_dir=product_root / "tools",
    )
    if profile.default_tool_ids is not None:
        tool_registry = _filter_tool_registry(full_tool_registry, profile.default_tool_ids)
    else:
        tool_registry = full_tool_registry

    session_store = None
    if config_resolver is not None:
        session_store = SQLiteSessionStore(db_path=config_resolver.session_db_path())

    skill_registry = SkillRegistry(
        search_roots=default_skill_search_roots(
            workspace_root=resolved_root,
            config_resolver=config_resolver,
            product_skill_root=product_root / "skills",
        )
    )

    return ResolvedProductConfig(
        product_id=profile.product_id,
        resolved_system_prompt=resolved_system_prompt,
        tool_registry=tool_registry,
        hook_registry=hook_registry,
        session_store=session_store,
        config_resolver=config_resolver,
        skill_registry=skill_registry,
    )


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
            source=registration.source,
            module_name=registration.module_name,
            file_path=registration.file_path,
        )
    return filtered
