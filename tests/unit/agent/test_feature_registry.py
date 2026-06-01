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
    """Each registry entry must have: sections, default_on, requires_tool, layer, label_i18n, help_i18n."""
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    required_fields = {
        "sections",
        "default_on",
        "requires_tool",
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
    assert "core.skills_guidance" in entry["sections"]
