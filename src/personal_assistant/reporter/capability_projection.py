"""Gateway-owned product-semantic projection for IM capability payloads.

refactor-406-M2 (决策 4): the kernel reports *neutral facts* via ``kernel.list_*``
(model names + order, tool name/description, feature key/default_on/requires_tool,
per-workspace skill name/description). All *product semantics* — display i18n text,
the default-vs-optional tool split, the heartbeat/cron product toggles, and the
``available`` computation — are owned by this Gateway projection layer, not the
kernel (the kernel stays product-neutral: it holds no display text and no
product-specific feature).

These constants are the single source of truth after ``agent/products/`` is
dissolved. They are ported verbatim from the pre-refactor data:

- ``PA_DEFAULT_TOOL_IDS`` / ``PA_OPTIONAL_TOOL_IDS`` ← ``PERSONAL_ASSISTANT_PROFILE``
  ``default_tool_ids`` / ``optional_tool_ids`` (the default_on split the IM frontend
  uses to pre-select tool pills).
- ``FEATURE_PROJECTIONS`` ← the four FEATURE_REGISTRY entries (memory_curation,
  skill_creation, cron_scheduling, heartbeat) with their i18n keys, default_on,
  requires_tool, in declaration order. The kernel reports only the first two as
  neutral facts (key/default_on/requires_tool via ``list_features``); the i18n text
  for all four AND the two product toggles (cron/heartbeat) are projected here.

The capability payload (node.register flags + node.capabilities +
agent.capabilities.resolve) must stay byte-for-byte identical to the pre-refactor
baseline (design 风险 2); these constants reproduce its product-semantic fields.
"""

from __future__ import annotations

from typing import TypedDict


# ---------------------------------------------------------------------------
# Tool default_on split (PERSONAL_ASSISTANT_PROFILE default/optional tool ids)
# ---------------------------------------------------------------------------
# default_on=True for default_tool_ids (pre-selected when allowlist is empty),
# default_on=False for optional_tool_ids (must be explicitly added).

PA_DEFAULT_TOOL_IDS: tuple[str, ...] = (
    "read",
    "write",
    "edit",
    "bash",
    "agent",
    "task_stop",
    "web_fetch",
    "web_search",
    "skill_manage",
    "skill_view",
    "memory",
)

PA_OPTIONAL_TOOL_IDS: tuple[str, ...] = (
    "send_message",
    "cron",
)


# ---------------------------------------------------------------------------
# Feature projection (i18n text + heartbeat/cron product toggles)
# ---------------------------------------------------------------------------


class FeatureProjection(TypedDict):
    """One feature's product-semantic projection (Gateway-owned display data)."""

    key: str
    label_i18n: str
    help_i18n: str
    default_on: bool
    requires_tool: str | None


# Ported verbatim from FEATURE_REGISTRY (declaration order preserved). The kernel's
# list_features() reports the neutral facts (key/default_on/requires_tool) for the
# two kernel-general features (memory_curation/skill_creation); this table supplies
# the i18n text for all four AND the two PA product toggles (cron/heartbeat) in full.
FEATURE_PROJECTIONS: tuple[FeatureProjection, ...] = (
    FeatureProjection(
        key="memory_curation",
        label_i18n="feature.memory_curation.label",
        help_i18n="feature.memory_curation.help",
        default_on=True,
        requires_tool="memory",
    ),
    FeatureProjection(
        key="skill_creation",
        label_i18n="feature.skill_creation.label",
        help_i18n="feature.skill_creation.help",
        default_on=True,
        requires_tool="skill_manage",
    ),
    FeatureProjection(
        key="cron_scheduling",
        label_i18n="feature.cron_scheduling.label",
        help_i18n="feature.cron_scheduling.help",
        default_on=False,
        requires_tool="cron",
    ),
    FeatureProjection(
        key="heartbeat",
        label_i18n="feature.heartbeat.label",
        help_i18n="feature.heartbeat.help",
        default_on=False,
        requires_tool=None,
    ),
)


def project_tools(
    tool_infos: tuple[tuple[str, str], ...],
) -> tuple[dict[str, object], ...]:
    """Project the IM tool pills with ``default_on`` from the PA tool split.

    The output order follows PA_DEFAULT_TOOL_IDS then PA_OPTIONAL_TOOL_IDS — matching
    the pre-refactor payload which took names directly from the profile (not the live
    registry), guaranteeing the full declared surface is advertised regardless of
    which tools the live kernel happened to register.

    ``description`` is held at ``""`` to reproduce the pre-refactor payload byte-for-
    byte (design 风险 2 — capability payload is a migration invariant). The kernel's
    ``list_tools`` *does* report real descriptions, but the IM tool-pill payload has
    always advertised empty descriptions; surfacing real text is a payload change out
    of scope for this behavior-preserving refactor.

    Args:
        tool_infos: ``(name, description)`` pairs from ``kernel.list_tools()`` —
            accepted for forward compatibility; currently only used to keep the
            signature kernel-driven (descriptions are intentionally dropped).

    Returns:
        Ordered tuple of ``{name, description, default_on}`` dicts.
    """
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for tool_id in PA_DEFAULT_TOOL_IDS:
        if tool_id in seen:
            continue
        seen.add(tool_id)
        result.append({"name": tool_id, "description": "", "default_on": True})
    for tool_id in PA_OPTIONAL_TOOL_IDS:
        if tool_id in seen:
            continue
        seen.add(tool_id)
        result.append({"name": tool_id, "description": "", "default_on": False})
    return tuple(result)


def project_features(
    *, tool_allowlist: tuple[str, ...] | None = None
) -> list[dict[str, object]]:
    """Project the four-feature toggle list for IM (i18n + available computation).

    Args:
        tool_allowlist: When provided (agent level), a feature is ``available`` only
            if its ``requires_tool`` is None or present in the allowlist. When None
            (node level), every feature is ``available=True`` (no per-agent allowlist
            constrains node-level capabilities).

    Returns:
        Ordered list of feature dicts with key/label_i18n/help_i18n/default_on/
        available/requires_tool.
    """
    allowlist_set = set(tool_allowlist) if tool_allowlist is not None else None
    projection: list[dict[str, object]] = []
    for entry in FEATURE_PROJECTIONS:
        requires_tool = entry["requires_tool"]
        if allowlist_set is None:
            available = True
        else:
            available = requires_tool is None or requires_tool in allowlist_set
        projection.append(
            {
                "key": entry["key"],
                "label_i18n": entry["label_i18n"],
                "help_i18n": entry["help_i18n"],
                "default_on": entry["default_on"],
                "available": available,
                "requires_tool": requires_tool,
            }
        )
    return projection


__all__ = [
    "PA_DEFAULT_TOOL_IDS",
    "PA_OPTIONAL_TOOL_IDS",
    "FEATURE_PROJECTIONS",
    "FeatureProjection",
    "project_tools",
    "project_features",
]
