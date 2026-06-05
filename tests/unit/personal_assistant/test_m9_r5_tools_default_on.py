"""Tests for feat-394 M9 R5: upstream_reporter.tools carries {name, description, default_on}.

R5 goal: capabilities.tools format changes from bare string list to rich object list,
so the IM frontend can render tool pills with default_on state (show as "selected by
default" when the agent's tool_allowlist is empty).

These tests are RED until R5 implementation lands.
"""

from __future__ import annotations

import inspect


class TestBuildToolNamesStructure:
    """_build_tool_names must return rich dicts with name/description/default_on."""

    def _get_tool_names(self):
        from personal_assistant.reporter.upstream_reporter import _build_tool_names
        return _build_tool_names()

    def test_tools_are_dicts_not_strings(self) -> None:
        """_build_tool_names must return dicts, not plain strings (feat-394 M9 R5).

        After R5 the list carries {name, description, default_on} so the frontend
        can render tool pills with their default selection state.
        """
        tools = self._get_tool_names()
        assert len(tools) > 0, "_build_tool_names must return at least one tool"
        first = tools[0]
        assert isinstance(first, dict), (
            f"_build_tool_names must return dicts, got {type(first).__name__}. "
            "R5 upgrade: return {name, description, default_on} per tool."
        )

    def test_tools_have_name_key(self) -> None:
        """Each tool entry must have 'name' key."""
        tools = self._get_tool_names()
        for tool in tools:
            assert "name" in tool, f"tool entry missing 'name' key: {tool}"

    def test_tools_have_description_key(self) -> None:
        """Each tool entry must have 'description' key."""
        tools = self._get_tool_names()
        for tool in tools:
            assert "description" in tool, f"tool entry missing 'description' key: {tool}"

    def test_tools_have_default_on_key(self) -> None:
        """Each tool entry must have 'default_on' key (feat-394 M9 R5)."""
        tools = self._get_tool_names()
        for tool in tools:
            assert "default_on" in tool, (
                f"tool entry missing 'default_on' key: {tool}. "
                "R5: default_on=True for tools in default_tool_ids, False for optional_tool_ids."
            )

    def test_default_tools_have_default_on_true(self) -> None:
        """Tools in PERSONAL_ASSISTANT_PROFILE.default_tool_ids must have default_on=True."""
        from agent.sdk import PERSONAL_ASSISTANT_PROFILE
        from personal_assistant.reporter.upstream_reporter import _build_tool_names

        tools = _build_tool_names()
        tool_map = {t["name"]: t for t in tools}
        for tool_id in (PERSONAL_ASSISTANT_PROFILE.default_tool_ids or []):
            if tool_id in tool_map:
                assert tool_map[tool_id]["default_on"] is True, (
                    f"default tool '{tool_id}' must have default_on=True "
                    "(it's in PERSONAL_ASSISTANT_PROFILE.default_tool_ids)"
                )

    def test_optional_tools_have_default_on_false(self) -> None:
        """Tools in PERSONAL_ASSISTANT_PROFILE.optional_tool_ids must have default_on=False."""
        from agent.sdk import PERSONAL_ASSISTANT_PROFILE
        from personal_assistant.reporter.upstream_reporter import _build_tool_names

        tools = _build_tool_names()
        tool_map = {t["name"]: t for t in tools}
        for tool_id in (PERSONAL_ASSISTANT_PROFILE.optional_tool_ids or []):
            if tool_id in tool_map:
                assert tool_map[tool_id]["default_on"] is False, (
                    f"optional tool '{tool_id}' must have default_on=False "
                    "(it's in PERSONAL_ASSISTANT_PROFILE.optional_tool_ids)"
                )

    def test_memory_still_in_tools(self) -> None:
        """memory must still appear in _build_tool_names() after R5 format change."""
        tools = self._get_tool_names()
        names = {t["name"] for t in tools}
        assert "memory" in names, "memory must be in capabilities.tools after R5 format change"

    def test_feature_registry_required_tools_still_present(self) -> None:
        """FEATURE_REGISTRY requires_tool entries must still appear in tools list."""
        from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY
        from personal_assistant.reporter.upstream_reporter import _build_tool_names

        tools = _build_tool_names()
        names = {t["name"] for t in tools}
        for entry in FEATURE_REGISTRY.values():
            rt = entry.get("requires_tool")
            if rt is not None:
                assert rt in names, (
                    f"FEATURE_REGISTRY requires_tool '{rt}' must be in capabilities.tools "
                    "(feat-379-M9 decision 13)"
                )


class TestBuildNodeCapabilitiesToolsFormat:
    """build_node_capabilities_payload tools must use rich dict format."""

    def test_node_capabilities_tools_are_dicts(self) -> None:
        """build_node_capabilities_payload()['tools'] must be list of dicts."""
        from personal_assistant.reporter.upstream_reporter import build_node_capabilities_payload

        payload = build_node_capabilities_payload()
        tools = payload["tools"]
        assert isinstance(tools, list) and len(tools) > 0
        assert isinstance(tools[0], dict), (
            "node capabilities tools must be dicts after R5. "
            "Got: " + repr(type(tools[0]))
        )
        assert "name" in tools[0]
        assert "default_on" in tools[0]
