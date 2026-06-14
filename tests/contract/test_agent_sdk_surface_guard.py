"""Surface guard for ``agent.sdk`` (refactor-406 决策 7).

Two gates pin the curated public surface so that "widening the public contract"
is always an explicit, reviewable diff:

1. **Exact-name gate**: ``agent.sdk.__all__`` must equal ``EXPECTED_SURFACE``
   byte-for-byte. Adding/removing an export forces a matching change here.
2. **Ownership gate**: every export's defining module (``__module__``; for
   instances, ``type(obj).__module__``) must start with ``agent.sdk`` — i.e. the
   symbol is genuinely SDK-owned — UNLESS the name is on an explicit, verbatim
   exemption list. Exemptions are core/platform-owned types that are deliberately
   re-exported (moving them into agent.sdk would invert the dependency).

Exemption groups (each entry documents WHY it is allowed):

- ``_C1_REEXPORTS``: core/platform-owned boundary types referenced widely by
  core/platform; re-exported, never relocated (permanent).
- ``_DECISION12_PRESENTER``: tool-presentation pure-function types, core-owned,
  sdk re-export (permanent, 决策 12).
- ``_TYPING_ALIAS``: ``CanUseToolFn`` is an sdk-owned ``Callable`` alias with no
  class ``__module__``; handled specially (not an ownership violation).
- ``_M1_TEMP_REPORTER_EXPORTS`` / ``_M1_TEMP_PROFILES``: reporter-only exports +
  product profiles still consumed by ``upstream_reporter`` (capability reporting).
  These are removed in M2 when the reporter migrates to ``Kernel.list_*`` (决策 4);
  the exemption + the names disappear together then.
"""

from __future__ import annotations

import agent.sdk as sdk


# ---------------------------------------------------------------------------
# Gate 1: exact public surface
# ---------------------------------------------------------------------------

EXPECTED_SURFACE: frozenset[str] = frozenset(
    {
        # Core kernel assembly
        "build_kernel",
        "Kernel",
        "CanUseToolFn",
        # 2-layer surface (决策 2/4/5/6/8)
        "Tool",
        "ToolContext",
        "HookAPI",
        "PromptSlots",
        "PromptText",
        "LLMConfig",
        "LLMProvider",
        "LLMModel",
        "SessionInfo",
        "RunInfo",
        "ModelInfo",
        "ToolInfo",
        "FeatureInfo",
        "SkillInfo",
        # Tool presentation (决策 12)
        "ToolPresenter",
        "ToolPresentationEvent",
        # Permission
        "PermissionDecision",
        # Run origin + terminal statuses (C1)
        "RunOrigin",
        "TERMINAL_RUN_STATUSES",
        # --- M1-temporary: reporter-only exports (removed in M2) ---
        "LLMFactoryConfig",
        "LLMConfigPayload",
        "LLMModelPayload",
        "LLMProviderPayload",
        "init_model_registry",
        "get_default_model",
        "get_default_provider",
        "list_provider_models",
        "list_supported_providers",
        "SkillRegistry",
        "default_skill_search_roots",
        "ConfigResolver",
        "FEATURE_REGISTRY",
        "LOCAL_CODING_PROFILE",
        "PERSONAL_ASSISTANT_PROFILE",
    }
)


def test_sdk_all_equals_expected_surface() -> None:
    """agent.sdk.__all__ must equal EXPECTED_SURFACE byte-for-byte (决策 7 闸 1)."""
    actual = frozenset(sdk.__all__)
    missing = EXPECTED_SURFACE - actual
    extra = actual - EXPECTED_SURFACE
    assert not missing and not extra, (
        "agent.sdk public surface drifted from EXPECTED_SURFACE.\n"
        f"  missing (in EXPECTED_SURFACE, absent from __all__): {sorted(missing)}\n"
        f"  extra (in __all__, absent from EXPECTED_SURFACE): {sorted(extra)}\n"
        "Widening/narrowing the public contract must be an explicit diff here."
    )
    # __all__ must have no duplicates.
    assert len(sdk.__all__) == len(set(sdk.__all__)), "agent.sdk.__all__ has duplicates"


# ---------------------------------------------------------------------------
# Gate 2: ownership (sdk-owned, or explicitly exempt)
# ---------------------------------------------------------------------------

# C1 boundary types — core/platform-owned, re-exported, never relocated (permanent).
_C1_REEXPORTS: frozenset[str] = frozenset(
    {"RunOrigin", "PermissionDecision", "TERMINAL_RUN_STATUSES"}
)

# 决策 12: tool-presentation pure-function types, core-owned, sdk re-export (permanent).
_DECISION12_PRESENTER: frozenset[str] = frozenset(
    {"ToolPresenter", "ToolPresentationEvent"}
)

# sdk-owned Callable alias (no class __module__) — special-cased, not a violation.
_TYPING_ALIAS: frozenset[str] = frozenset({"CanUseToolFn"})

# M1-temporary: reporter-only exports still consumed by upstream_reporter. Removed
# in M2 when the reporter migrates to Kernel.list_* (决策 4).
_M1_TEMP_REPORTER_EXPORTS: frozenset[str] = frozenset(
    {
        "LLMFactoryConfig",
        "LLMConfigPayload",
        "LLMModelPayload",
        "LLMProviderPayload",
        "init_model_registry",
        "get_default_model",
        "get_default_provider",
        "list_provider_models",
        "list_supported_providers",
        "SkillRegistry",
        "default_skill_search_roots",
        "ConfigResolver",
        "FEATURE_REGISTRY",
    }
)

# M1-temporary: product profiles still consumed by upstream_reporter (product_id /
# default tool ids / ConfigResolver(profile=…)). Removed in M2 with products/.
_M1_TEMP_PROFILES: frozenset[str] = frozenset(
    {"LOCAL_CODING_PROFILE", "PERSONAL_ASSISTANT_PROFILE"}
)

_OWNERSHIP_EXEMPT: frozenset[str] = (
    _C1_REEXPORTS
    | _DECISION12_PRESENTER
    | _TYPING_ALIAS
    | _M1_TEMP_REPORTER_EXPORTS
    | _M1_TEMP_PROFILES
)


def _defining_module(name: str) -> str:
    obj = getattr(sdk, name)
    module = getattr(obj, "__module__", None)
    if module is None:
        module = type(obj).__module__
    return module or ""


def test_sdk_exports_are_sdk_owned_or_explicitly_exempt() -> None:
    """Every export is sdk-owned, or on the verbatim exemption list (决策 7 闸 2)."""
    violations: list[str] = []
    for name in sdk.__all__:
        if name in _OWNERSHIP_EXEMPT:
            continue
        module = _defining_module(name)
        if not module.startswith("agent.sdk"):
            violations.append(f"{name} (__module__={module})")
    assert not violations, (
        "agent.sdk exports must be sdk-owned (__module__ under agent.sdk) or listed "
        "in an explicit exemption group.\nNon-owned, non-exempt exports:\n  "
        + "\n  ".join(violations)
    )


def test_exemption_names_are_actually_exported() -> None:
    """Every exemption name must be a real export (no stale exemptions)."""
    stale = _OWNERSHIP_EXEMPT - frozenset(sdk.__all__)
    assert not stale, (
        f"exemption list names that are no longer exported (remove them): {sorted(stale)}"
    )
