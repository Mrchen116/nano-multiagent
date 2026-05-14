"""Unit tests for platform/tools/builtins/memory tool.

Validates: action dispatch, schema, error handling, § separator, source index,
fixed two-file contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock

import pytest

from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.memory import MemoryTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(memory_root: Path, session_id: str = "test-session") -> Any:
    ctx = MagicMock(spec=ToolContext)
    ctx.session_id = session_id
    ctx.session_metadata = {"memory_root": str(memory_root)}
    ctx.cwd = memory_root
    return ctx


@pytest.fixture()
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    root.mkdir()
    return root


@pytest.fixture()
def tool(memory_root: Path) -> MemoryTool:
    return MemoryTool(memory_root=memory_root)


# ---------------------------------------------------------------------------
# R5.1  Schema / protocol checks
# ---------------------------------------------------------------------------


def test_tool_name_is_memory(tool: MemoryTool) -> None:
    assert tool.name == "memory"


def test_tool_has_input_schema(tool: MemoryTool) -> None:
    assert isinstance(tool.input_schema, Mapping)
    props = tool.input_schema["properties"]
    assert "action" in props
    assert "target" in props


def test_action_enum_contains_add_replace_remove(tool: MemoryTool) -> None:
    enum_vals = tool.input_schema["properties"]["action"].get("enum", [])
    assert "add" in enum_vals
    assert "replace" in enum_vals
    assert "remove" in enum_vals
    # No 'read' action — memory is read via system prompt injection
    assert "read" not in enum_vals


def test_target_enum_contains_memory_user(tool: MemoryTool) -> None:
    enum_vals = tool.input_schema["properties"]["target"].get("enum", [])
    assert "memory" in enum_vals
    assert "user" in enum_vals


# ---------------------------------------------------------------------------
# R5.2  add action — memory target
# ---------------------------------------------------------------------------


def test_add_memory_success(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "add", "target": "memory", "content": "test fact"}, ctx)
    assert result["success"] is True
    assert (memory_root / "MEMORY.md").exists()


def test_add_user_success(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "add", "target": "user", "content": "user name is Alice"}, ctx)
    assert result["success"] is True
    assert (memory_root / "USER.md").exists()


def test_add_without_content_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "add", "target": "memory"}, ctx)
    assert result["success"] is False
    assert "content" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# R5.3  replace action
# ---------------------------------------------------------------------------


def test_replace_existing_entry(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    tool.run({"action": "add", "target": "memory", "content": "old text"}, ctx)
    result = tool.run(
        {"action": "replace", "target": "memory", "old_text": "old text", "content": "new text"},
        ctx,
    )
    assert result["success"] is True
    content = (memory_root / "MEMORY.md").read_text(encoding="utf-8")
    assert "new text" in content


def test_replace_missing_old_text_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run(
        {"action": "replace", "target": "memory", "old_text": "does not exist", "content": "new"},
        ctx,
    )
    assert result["success"] is False


def test_replace_missing_content_param_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "replace", "target": "memory", "old_text": "x"}, ctx)
    assert result["success"] is False


# ---------------------------------------------------------------------------
# R5.4  remove action
# ---------------------------------------------------------------------------


def test_remove_existing_entry(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    tool.run({"action": "add", "target": "memory", "content": "to be removed"}, ctx)
    result = tool.run({"action": "remove", "target": "memory", "old_text": "to be removed"}, ctx)
    assert result["success"] is True


def test_remove_missing_entry_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "remove", "target": "memory", "old_text": "ghost"}, ctx)
    assert result["success"] is False


def test_remove_missing_old_text_param_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "remove", "target": "memory"}, ctx)
    assert result["success"] is False


# ---------------------------------------------------------------------------
# R5.5  § separator in persisted file (L60 two files + § delimiter)
# ---------------------------------------------------------------------------


def test_two_entries_have_section_separator(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    tool.run({"action": "add", "target": "memory", "content": "fact A"}, ctx)
    tool.run({"action": "add", "target": "memory", "content": "fact B"}, ctx)
    content = (memory_root / "MEMORY.md").read_text(encoding="utf-8")
    assert "§" in content


# ---------------------------------------------------------------------------
# R5.6  Source index present (L61)
# ---------------------------------------------------------------------------


def test_source_index_in_file(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root, session_id="sess-test-001")
    tool.run({"action": "add", "target": "memory", "content": "indexed fact"}, ctx)
    content = (memory_root / "MEMORY.md").read_text(encoding="utf-8")
    assert "sess-test-001" in content


# ---------------------------------------------------------------------------
# R5.7  Only two fixed files created (L60)
# ---------------------------------------------------------------------------


def test_only_memory_and_user_files_created(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    tool.run({"action": "add", "target": "memory", "content": "note"}, ctx)
    tool.run({"action": "add", "target": "user", "content": "Alice"}, ctx)
    files = {p.name for p in memory_root.iterdir() if not p.name.endswith(".lock") and not p.name.endswith(".tmp")}
    assert files == {"MEMORY.md", "USER.md"}


# ---------------------------------------------------------------------------
# R5.8  Error cases
# ---------------------------------------------------------------------------


def test_unknown_action_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "read", "target": "memory"}, ctx)
    assert result["success"] is False


def test_unknown_target_returns_error(tool: MemoryTool, memory_root: Path) -> None:
    ctx = _make_ctx(memory_root)
    result = tool.run({"action": "add", "target": "unknown", "content": "x"}, ctx)
    assert result["success"] is False


# ---------------------------------------------------------------------------
# R5.9  serialize_result
# ---------------------------------------------------------------------------


def test_serialize_result_success_is_str(tool: MemoryTool) -> None:
    output = {"success": True, "message": "added"}
    result = tool.serialize_result(output)
    assert isinstance(result, str)


def test_serialize_result_error_uses_error_arg(tool: MemoryTool) -> None:
    result = tool.serialize_result(None, error="something went wrong")
    assert "something went wrong" in result


# ---------------------------------------------------------------------------
# R5.10  memory_root resolved from ctx.session_metadata
# ---------------------------------------------------------------------------


def test_memory_root_resolved_from_session_metadata(tmp_path: Path) -> None:
    root = tmp_path / "resolved_root"
    root.mkdir()
    ctx = _make_ctx(root)
    tool = MemoryTool()  # No fixed root
    result = tool.run({"action": "add", "target": "memory", "content": "from metadata"}, ctx)
    assert result["success"] is True
    assert (root / "MEMORY.md").exists()
