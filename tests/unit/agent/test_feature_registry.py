"""Unit tests for the feature registry skeleton (feat-379-M1 R2).

M1 only establishes the registry skeleton with correct field shapes.
M2 will fill in the full implementation and add contract tests for the
capabilities API projection.
"""

from __future__ import annotations

import pytest


def test_feature_registry_is_importable():
    """FEATURE_REGISTRY must be importable from the prompt_sections package."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY  # noqa: F401


def test_feature_registry_has_memory_curation_entry():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert "memory_curation" in FEATURE_REGISTRY


def test_feature_registry_has_skill_creation_entry():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert "skill_creation" in FEATURE_REGISTRY


def test_feature_registry_entries_have_required_fields():
    """Each registry entry must have the standard feature projection fields."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    required_fields = {
        "sections",
        "default_on",
        "requires_tool",
        "requires_any_tool",
        "layer",
        "label_i18n",
        "help_i18n",
    }
    for key, entry in FEATURE_REGISTRY.items():
        missing = required_fields - set(entry)
        assert not missing, f"FEATURE_REGISTRY[{key!r}] missing fields: {missing}"


def test_feature_registry_sections_are_tuples_of_strings():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    for key, entry in FEATURE_REGISTRY.items():
        assert isinstance(entry["sections"], tuple), f"{key}: sections must be tuple"
        for s in entry["sections"]:
            assert isinstance(s, str), f"{key}: each section name must be str"


def test_feature_registry_default_on_is_bool():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    for key, entry in FEATURE_REGISTRY.items():
        assert isinstance(entry["default_on"], bool), f"{key}: default_on must be bool"


def test_feature_registry_requires_tool_is_str_or_none():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    for key, entry in FEATURE_REGISTRY.items():
        val = entry["requires_tool"]
        assert val is None or isinstance(val, str), (
            f"{key}: requires_tool must be str or None"
        )


def test_feature_registry_requires_any_tool_is_tuple_of_strings_or_none():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    for key, entry in FEATURE_REGISTRY.items():
        val = entry["requires_any_tool"]
        assert val is None or isinstance(val, tuple), (
            f"{key}: requires_any_tool must be tuple[str, ...] or None"
        )
        if val is not None:
            assert val, f"{key}: requires_any_tool must not be empty when set"
            assert all(isinstance(tool, str) for tool in val), (
                f"{key}: requires_any_tool entries must be strings"
            )


def test_feature_registry_layer_is_valid():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    valid_layers = {"core", "product"}
    for key, entry in FEATURE_REGISTRY.items():
        assert entry["layer"] in valid_layers, (
            f"{key}: layer must be 'core' or 'product'"
        )


def test_memory_curation_defaults():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    entry = FEATURE_REGISTRY["memory_curation"]
    assert entry["default_on"] is True
    assert entry["requires_tool"] == "memory"
    assert "core.memory_guidance" in entry["sections"]


def test_skill_creation_defaults():
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    entry = FEATURE_REGISTRY["skill_creation"]
    assert entry["default_on"] is True
    assert entry["requires_tool"] == "skill_manage"
    assert entry["requires_any_tool"] == ("skill_manage", "skill_view")
    assert "core.skills_guidance" in entry["sections"]


# ---------------------------------------------------------------------------
# feat-394 decision D: cron_scheduling and heartbeat as product-layer features
# ---------------------------------------------------------------------------


def test_feature_registry_has_cron_scheduling_entry():
    """FEATURE_REGISTRY must contain the cron_scheduling feature (decision D)."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert "cron_scheduling" in FEATURE_REGISTRY, (
        "cron_scheduling must be in FEATURE_REGISTRY — decision D requires "
        "heartbeat/cron to use the same FEATURE_REGISTRY model as memory/skill"
    )


def test_feature_registry_has_heartbeat_entry():
    """FEATURE_REGISTRY must contain the heartbeat feature (decision D)."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert "heartbeat" in FEATURE_REGISTRY, (
        "heartbeat must be in FEATURE_REGISTRY — decision D requires "
        "heartbeat/cron to use the same FEATURE_REGISTRY model as memory/skill"
    )


def test_cron_scheduling_entry_shape():
    """cron_scheduling: requires_tool=cron, sections=(pa.cron,), default_on=False, layer=product."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    entry = FEATURE_REGISTRY["cron_scheduling"]
    assert entry["requires_tool"] == "cron", (
        "cron_scheduling.requires_tool must be 'cron' so feature→tool invariant works"
    )
    assert "pa.cron" in entry["sections"], (
        "cron_scheduling.sections must contain 'pa.cron'"
    )
    assert entry["default_on"] is False, "cron_scheduling is opt-in (default_on=False)"
    assert entry["layer"] == "product", (
        "cron_scheduling is a product-layer feature (PA only)"
    )


def test_heartbeat_entry_shape():
    """heartbeat: requires_tool=None, sections=(pa.heartbeat,), default_on=False, layer=product."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    entry = FEATURE_REGISTRY["heartbeat"]
    assert entry["requires_tool"] is None, (
        "heartbeat.requires_tool must be None — heartbeat uses file tools, no dedicated tool"
    )
    assert "pa.heartbeat" in entry["sections"], (
        "heartbeat.sections must contain 'pa.heartbeat'"
    )
    assert entry["default_on"] is False, "heartbeat is opt-in (default_on=False)"
    assert entry["layer"] == "product", "heartbeat is a product-layer feature (PA only)"


def test_cron_scheduling_is_not_default_on_for_coding_cli_isolation():
    """cron_scheduling must NOT be default_on so coding_cli doesn't advertise it.

    Decision 7 / Decision D: cron/heartbeat are PA-only. default_on=False +
    layer='product' means coding_cli's capabilities projection omits them.
    """
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert FEATURE_REGISTRY["cron_scheduling"]["default_on"] is False


def test_heartbeat_is_not_default_on_for_coding_cli_isolation():
    """heartbeat must NOT be default_on so coding_cli doesn't advertise it."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert FEATURE_REGISTRY["heartbeat"]["default_on"] is False
