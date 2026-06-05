"""Feature registry — single source of truth for user-togglable prompt features.

Each entry maps a feature key to:
  sections:      tuple of segment names that become active when this feature is on.
  default_on:    product-level default (user can override per-agent in config.yaml).
  requires_tool: segment also requires this tool in the session's active toolset;
                 None means no tool dependency.
  layer:         "core" (segment lives in core_sections) or "product".
  label_i18n:    i18n key for the feature toggle label shown in the IM frontend.
  help_i18n:     i18n key for the one-line help text shown below the label.

Decision 7: registry is the single event source for feature→segment→tool→default
mapping.  The IM frontend receives a projection of this registry via the
capabilities API (GET /im/v1/agents/{id}/capabilities → features list) so it can
render toggles without hardcoding the key set.

M1 status: skeleton only — section names are correct, i18n keys are stubs.
M2 will fill in the capabilities API projection and per-agent config plumbing.
"""

from __future__ import annotations

from typing import TypedDict


class FeatureEntry(TypedDict):
    """Shape of one entry in FEATURE_REGISTRY."""

    sections: tuple[str, ...]
    default_on: bool
    requires_tool: str | None
    layer: str
    label_i18n: str
    help_i18n: str


# ---------------------------------------------------------------------------
# Canonical feature registry (feat-379 decision 7)
# ---------------------------------------------------------------------------
# Keys here are the authoritative feature_key identifiers used in:
#   - config.yaml  agent.features.<key>
#   - PromptContext.flags.<key>
#   - capabilities API response
#   - IM frontend toggle rendering
#
# Extending: add a new entry here; the IM frontend picks it up automatically
# once capabilities API is updated (no frontend hardcoding needed).
# ---------------------------------------------------------------------------

FEATURE_REGISTRY: dict[str, FeatureEntry] = {
    # Provenance: new — decision 3/7; replaces self_evolution.memory_curation
    #   (feat-349 per-instance flag) with per-agent granularity.
    "memory_curation": FeatureEntry(
        sections=("core.memory_guidance",),
        default_on=True,
        requires_tool="memory",
        layer="core",
        label_i18n="feature.memory_curation.label",
        help_i18n="feature.memory_curation.help",
    ),
    # Provenance: new — decision 3/7; replaces self_evolution.skill_creation
    #   (feat-349 per-instance flag) with per-agent granularity.
    "skill_creation": FeatureEntry(
        sections=("core.skills_guidance",),
        default_on=True,
        requires_tool="skill_manage",
        layer="core",
        label_i18n="feature.skill_creation.label",
        help_i18n="feature.skill_creation.help",
    ),
    # ---------------------------------------------------------------------------
    # Personal Assistant product-layer features (feat-394 decision D)
    # ---------------------------------------------------------------------------
    # Both entries are layer="product" and default_on=False:
    #   - layer="product" → coding_cli capabilities projection omits them (decision 7)
    #   - default_on=False → opt-in per-agent; not enabled for coding_cli or by default
    #
    # cron_scheduling gates pa.cron segment AND wires cron into the agent's tool
    # allowlist via the standard feature→requires_tool invariant (same mechanism as
    # memory_curation→memory / skill_creation→skill_manage).
    # heartbeat has no dedicated tool (agent self-manages via file tools); it only
    # gates the pa.heartbeat prompt segment.
    # ---------------------------------------------------------------------------
    # Provenance: feat-394 decision D — cron_scheduling/heartbeat unified into
    #   FEATURE_REGISTRY; prompt text verbatim from openclaw (see prompt_sections.py)
    "cron_scheduling": FeatureEntry(
        sections=("pa.cron",),
        default_on=False,
        requires_tool="cron",
        layer="product",
        label_i18n="feature.cron_scheduling.label",
        help_i18n="feature.cron_scheduling.help",
    ),
    # Provenance: feat-394 decision D — heartbeat prompt text verbatim from
    #   openclaw/src/agents/system-prompt.ts:124-138 buildHeartbeatSection
    "heartbeat": FeatureEntry(
        sections=("pa.heartbeat",),
        default_on=False,
        requires_tool=None,
        layer="product",
        label_i18n="feature.heartbeat.label",
        help_i18n="feature.heartbeat.help",
    ),
}
