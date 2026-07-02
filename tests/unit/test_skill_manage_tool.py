"""Unit tests for platform/tools/builtins/skill_manage tool.

Validates the thin Tool wrapper over SkillWriter: action dispatch, schema,
error serialization, and end-to-end create→list cycle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock

import pytest

from agent.core.skills.registry import SkillRegistry
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.skill_manage import SkillManageTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_FM = "---\nname: my-skill\ndescription: A skill\n---\n\n# Body\n\nContent."


def _make_ctx(workspace_root: Path) -> ToolContext:
    """Minimal ToolContext for skill_manage (no safety checks needed)."""
    ctx = MagicMock(spec=ToolContext)
    ctx.session_metadata = {"workspace_root": str(workspace_root)}
    ctx.cwd = workspace_root
    return ctx


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture()
def skill_root(workspace: Path) -> Path:
    # skill_manage derives root from workspace via .<ns>/skills/
    # For test simplicity, use a known root
    return workspace


@pytest.fixture()
def registry(skill_root: Path) -> SkillRegistry:
    return SkillRegistry(search_roots=[skill_root])


@pytest.fixture()
def tool(skill_root: Path, registry: SkillRegistry) -> SkillManageTool:
    return SkillManageTool(skill_root=skill_root, registry=registry)


# ---------------------------------------------------------------------------
# R4.1  Schema / protocol checks
# ---------------------------------------------------------------------------


def test_tool_name_is_skill_manage(tool: SkillManageTool) -> None:
    assert tool.name == "skill_manage"


def test_tool_has_input_schema(tool: SkillManageTool) -> None:
    assert isinstance(tool.input_schema, Mapping)
    assert "properties" in tool.input_schema
    props = tool.input_schema["properties"]
    assert "action" in props
    assert "name" in props


def test_tool_has_description(tool: SkillManageTool) -> None:
    assert isinstance(tool.description, str)
    assert len(tool.description) > 10


def test_action_enum_contains_expected_values(tool: SkillManageTool) -> None:
    action_prop = tool.input_schema["properties"]["action"]
    enum_values = action_prop.get("enum", [])
    assert "create" in enum_values
    assert "edit" in enum_values
    assert "patch" in enum_values
    assert "list" in enum_values
    assert "write_file" in enum_values
    assert "remove_file" in enum_values
    assert "view" not in enum_values


# ---------------------------------------------------------------------------
# R4.2  create action
# ---------------------------------------------------------------------------


def test_create_action_writes_file(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run(
        {"action": "create", "name": "my-skill", "content": _VALID_FM}, ctx
    )
    assert result.get("success") is True
    assert (workspace / "my-skill" / "SKILL.md").exists()


def test_create_action_duplicate_returns_error(
    tool: SkillManageTool, workspace: Path
) -> None:
    ctx = _make_ctx(workspace)
    tool.run({"action": "create", "name": "my-skill", "content": _VALID_FM}, ctx)
    result = tool.run(
        {"action": "create", "name": "my-skill", "content": _VALID_FM}, ctx
    )
    assert result.get("success") is False
    assert "already exists" in result.get("error", "").lower()


def test_create_invalid_name_returns_error(
    tool: SkillManageTool, workspace: Path
) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run(
        {"action": "create", "name": "INVALID NAME", "content": _VALID_FM}, ctx
    )
    assert result.get("success") is False


def test_create_missing_content_returns_error(
    tool: SkillManageTool, workspace: Path
) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run({"action": "create", "name": "my-skill"}, ctx)
    assert result.get("success") is False


# ---------------------------------------------------------------------------
# R4.3  edit action
# ---------------------------------------------------------------------------


def test_edit_action_updates_file(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    tool.run(
        {
            "action": "create",
            "name": "edit-skill",
            "content": _VALID_FM.replace("my-skill", "edit-skill"),
        },
        ctx,
    )
    new_fm = (
        "---\nname: edit-skill\ndescription: Updated\n---\n\n# New\n\nUpdated content."
    )
    result = tool.run({"action": "edit", "name": "edit-skill", "content": new_fm}, ctx)
    assert result.get("success") is True
    content = (workspace / "edit-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "Updated content." in content


def test_edit_nonexistent_returns_error(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run({"action": "edit", "name": "ghost", "content": _VALID_FM}, ctx)
    assert result.get("success") is False


# ---------------------------------------------------------------------------
# R4.4  patch action
# ---------------------------------------------------------------------------


def test_patch_action_replaces_text(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    content = (
        "---\nname: patch-skill\ndescription: desc\n---\n\n# Body\n\nOld sentence."
    )
    tool.run({"action": "create", "name": "patch-skill", "content": content}, ctx)
    result = tool.run(
        {
            "action": "patch",
            "name": "patch-skill",
            "old_string": "Old sentence.",
            "new_string": "New sentence.",
        },
        ctx,
    )
    assert result.get("success") is True
    file_content = (workspace / "patch-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "New sentence." in file_content


def test_patch_missing_old_string_returns_error(
    tool: SkillManageTool, workspace: Path
) -> None:
    ctx = _make_ctx(workspace)
    tool.run(
        {
            "action": "create",
            "name": "ps2",
            "content": _VALID_FM.replace("my-skill", "ps2"),
        },
        ctx,
    )
    result = tool.run(
        {
            "action": "patch",
            "name": "ps2",
            "old_string": "NOT_IN_CONTENT",
            "new_string": "y",
        },
        ctx,
    )
    assert result.get("success") is False


# ---------------------------------------------------------------------------
# R4.5  list action
# ---------------------------------------------------------------------------


def test_list_action_returns_skills(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    tool.run(
        {
            "action": "create",
            "name": "list-skill",
            "content": _VALID_FM.replace("my-skill", "list-skill"),
        },
        ctx,
    )
    result = tool.run({"action": "list"}, ctx)
    assert result.get("success") is True
    assert "list-skill" in str(result.get("skills", ""))


def test_list_empty_returns_empty(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run({"action": "list"}, ctx)
    assert result.get("success") is True


# ---------------------------------------------------------------------------
# R4.6  view action removed
# ---------------------------------------------------------------------------


def test_view_action_is_not_supported(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run({"action": "view", "name": "ghost"}, ctx)
    assert result.get("success") is False
    assert "unknown action" in result.get("error", "").lower()


def test_create_action_accepts_agent_scope_by_default(
    tool: SkillManageTool, workspace: Path
) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run(
        {
            "action": "create",
            "scope": "agent",
            "name": "agent-skill",
            "content": _VALID_FM.replace("my-skill", "agent-skill"),
        },
        ctx,
    )
    assert result.get("success") is True
    assert (workspace / "agent-skill" / "SKILL.md").exists()


def test_create_pa_scope_writes_pa_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    pa_root = tmp_path / "pa-skills"
    workspace.mkdir()
    pa_root.mkdir()
    tool = SkillManageTool(
        workspace_config_dirname=".nanoassistant",
        extra_roots=(pa_root,),
        pa_skill_root=pa_root,
    )
    ctx = _make_ctx(workspace)

    result = tool.run(
        {
            "action": "create",
            "scope": "pa",
            "name": "pa-skill",
            "content": _VALID_FM.replace("my-skill", "pa-skill"),
        },
        ctx,
    )

    assert result.get("success") is True
    assert (pa_root / "pa-skill" / "SKILL.md").exists()
    assert not (workspace / ".nanoassistant" / "skills" / "pa-skill").exists()


def test_create_pa_scope_fails_without_pa_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = SkillManageTool(workspace_config_dirname=".nanoassistant")
    ctx = _make_ctx(workspace)

    result = tool.run(
        {
            "action": "create",
            "scope": "pa",
            "name": "pa-skill",
            "content": _VALID_FM.replace("my-skill", "pa-skill"),
        },
        ctx,
    )

    assert result.get("success") is False
    assert "pa skill root is not configured" in result.get("error", "")
    assert not (workspace / ".nanoassistant" / "skills" / "pa-skill").exists()


# ---------------------------------------------------------------------------
# R4.7  serialize_result produces str
# ---------------------------------------------------------------------------


def test_serialize_result_success_is_str(tool: SkillManageTool) -> None:
    output = {"success": True, "message": "created"}
    result = tool.serialize_result(output)
    assert isinstance(result, str)


def test_serialize_result_error_uses_error_arg(tool: SkillManageTool) -> None:
    result = tool.serialize_result(None, error="something broke")
    assert "something broke" in result


# ---------------------------------------------------------------------------
# R4.8  unknown action returns error (no exception raised)
# ---------------------------------------------------------------------------


def test_unknown_action_returns_error(tool: SkillManageTool, workspace: Path) -> None:
    ctx = _make_ctx(workspace)
    result = tool.run({"action": "delete", "name": "x"}, ctx)
    # delete is not in the supported actions for this project
    assert result.get("success") is False


# ---------------------------------------------------------------------------
# bugfix-375/M2 (issue #49): write_file / remove_file via the tool
# ---------------------------------------------------------------------------

_FM = "---\nname: umb\ndescription: d\n---\n\n# Body\n"


def test_tool_write_file_then_view_lists_it(tool: SkillManageTool) -> None:
    assert tool.run({"action": "create", "name": "umb", "content": _FM}, ctx=None)[
        "success"
    ]
    r = tool.run(
        {
            "action": "write_file",
            "name": "umb",
            "file_path": "references/n.md",
            "file_content": "x",
        },
        ctx=None,
    )
    assert r["success"], r
    listed = tool.run({"action": "list"}, ctx=None)
    assert "umb" in str(listed.get("skills", []))


def test_tool_write_file_rejects_bad_path(tool: SkillManageTool) -> None:
    tool.run({"action": "create", "name": "umb", "content": _FM}, ctx=None)
    r = tool.run(
        {
            "action": "write_file",
            "name": "umb",
            "file_path": "secrets/k",
            "file_content": "x",
        },
        ctx=None,
    )
    assert not r["success"]


def test_tool_remove_file(tool: SkillManageTool) -> None:
    tool.run({"action": "create", "name": "umb", "content": _FM}, ctx=None)
    tool.run(
        {
            "action": "write_file",
            "name": "umb",
            "file_path": "scripts/p.sh",
            "file_content": "x",
        },
        ctx=None,
    )
    r = tool.run(
        {"action": "remove_file", "name": "umb", "file_path": "scripts/p.sh"}, ctx=None
    )
    assert r["success"], r
    assert r["path"].endswith("scripts/p.sh")
