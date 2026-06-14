"""Tests for the capabilities.tools rich format ({name, description, default_on}).

feat-394 M9 R5 introduced the rich dict format so the IM frontend can render tool
pills with default_on state (show as "selected by default" when the agent's
tool_allowlist is empty).

refactor-406-M2: the tool pill projection moved from the deleted reporter
``_build_tool_names`` to the Gateway projection layer
(``capability_projection.project_tools``), which adds the default_on split from the
PA default/optional tool ids. These tests now exercise that projection directly plus
the node-level payload it feeds.
"""

from __future__ import annotations

from pathlib import Path

from personal_assistant.reporter.capability_projection import (
    PA_DEFAULT_TOOL_IDS,
    PA_OPTIONAL_TOOL_IDS,
    project_tools,
)

from ._im_connection_helpers import _build_test_kernel


def _projected_tools() -> tuple[dict[str, object], ...]:
    # Descriptions are intentionally dropped to "" by the projection; pass arbitrary
    # (name, description) pairs to confirm the projection ignores them.
    fake_infos = tuple(
        (name, "REAL DESC") for name in (*PA_DEFAULT_TOOL_IDS, *PA_OPTIONAL_TOOL_IDS)
    )
    return project_tools(fake_infos)


class TestProjectToolsStructure:
    """project_tools must return rich dicts with name/description/default_on."""

    def test_tools_are_dicts_not_strings(self) -> None:
        tools = _projected_tools()
        assert len(tools) > 0
        assert isinstance(tools[0], dict)

    def test_tools_have_name_key(self) -> None:
        for tool in _projected_tools():
            assert "name" in tool, f"tool entry missing 'name' key: {tool}"

    def test_tools_have_description_key(self) -> None:
        for tool in _projected_tools():
            assert "description" in tool, (
                f"tool entry missing 'description' key: {tool}"
            )

    def test_tool_descriptions_are_empty(self) -> None:
        """Tool pill descriptions stay "" (payload invariant, design 风险 2)."""
        for tool in _projected_tools():
            assert tool["description"] == "", (
                "capabilities.tools description must remain empty — surfacing real "
                "kernel tool descriptions is a payload change out of refactor scope"
            )

    def test_tools_have_default_on_key(self) -> None:
        for tool in _projected_tools():
            assert "default_on" in tool, f"tool entry missing 'default_on' key: {tool}"

    def test_default_tools_have_default_on_true(self) -> None:
        tool_map = {t["name"]: t for t in _projected_tools()}
        for tool_id in PA_DEFAULT_TOOL_IDS:
            assert tool_map[tool_id]["default_on"] is True, (
                f"default tool '{tool_id}' must have default_on=True"
            )

    def test_optional_tools_have_default_on_false(self) -> None:
        tool_map = {t["name"]: t for t in _projected_tools()}
        for tool_id in PA_OPTIONAL_TOOL_IDS:
            assert tool_map[tool_id]["default_on"] is False, (
                f"optional tool '{tool_id}' must have default_on=False"
            )

    def test_memory_still_in_tools(self) -> None:
        names = {t["name"] for t in _projected_tools()}
        assert "memory" in names


class TestNodeCapabilitiesToolsFormat:
    """build_node_capabilities_payload tools must use the rich dict format."""

    def test_node_capabilities_tools_are_dicts(self, tmp_path: Path) -> None:
        from personal_assistant.reporter.upstream_reporter import (
            build_node_capabilities_payload,
        )

        kernel = _build_test_kernel(tmp_path / "kernel-root")
        payload = build_node_capabilities_payload(kernel)
        tools = payload["tools"]
        assert isinstance(tools, list) and len(tools) > 0
        assert isinstance(tools[0], dict)
        assert "name" in tools[0]
        assert "default_on" in tools[0]
