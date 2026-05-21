"""Unit tests for WriteTool and EditTool: basic operations, serialize_result, read-before-write guard."""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.safety import ToolSafety
from agent.platform.tools.safety import ToolSafetyConfig
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.core.tools.session_file_state import SessionFileState

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def _context_with_state(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> tuple[ToolContext, SessionFileState]:
    base = ToolContext.create(repo_root=tmp_path, safety_config=config)
    state = SessionFileState()
    ctx = base.with_session("test-session", session_file_state=state)
    return ctx, state


# ---------------------------------------------------------------------------
# WriteTool basic operations
# ---------------------------------------------------------------------------


def test_write_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "notes" / "todo.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before", encoding="utf-8")
    ctx = _context(tmp_path)

    result = WriteTool().run({"path": "notes/todo.txt", "content": "after"}, ctx)

    assert target.read_text(encoding="utf-8") == "after"
    assert result["type"] == "update"
    assert result["displayPath"] == "notes/todo.txt"


def test_write_creates_new_file(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    result = WriteTool().run({"path": "newfile.txt", "content": "hello"}, ctx)
    assert result["type"] == "create"
    assert result["displayPath"] == "newfile.txt"
    assert (tmp_path / "newfile.txt").read_text(encoding="utf-8") == "hello"


# ---------------------------------------------------------------------------
# EditTool basic operations
# ---------------------------------------------------------------------------


def test_edit_replaces_exact_text_once(tmp_path: Path) -> None:
    target = tmp_path / "config.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = _context(tmp_path)

    result = EditTool().run(
        {"path": "config.txt", "oldText": "beta", "newText": "BETA"},
        ctx,
    )

    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert result["displayPath"] == "config.txt"
    assert result["replaceAll"] is False
    assert result["details"]["firstChangedLine"] == 2
    assert "--- a/config.txt" in result["details"]["diff"]
    assert "+++ b/config.txt" in result["details"]["diff"]
    assert "-beta" in result["details"]["diff"]
    assert "+BETA" in result["details"]["diff"]


def test_edit_fails_on_multiple_matches(tmp_path: Path) -> None:
    target = tmp_path / "dup.txt"
    target.write_text("x\nx\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="text must be unique"):
        EditTool().run({"path": "dup.txt", "oldText": "x", "newText": "y"}, ctx)


def test_edit_fails_when_old_text_not_found(tmp_path: Path) -> None:
    target = tmp_path / "missing.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="Could not find the exact text"):
        EditTool().run({"path": "missing.txt", "oldText": "gamma", "newText": "GAMMA"}, ctx)


def test_edit_fails_when_replacement_makes_no_change(tmp_path: Path) -> None:
    target = tmp_path / "same.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="No changes made"):
        EditTool().run({"path": "same.txt", "oldText": "beta", "newText": "beta"}, ctx)


# ---------------------------------------------------------------------------
# serialize_result
# ---------------------------------------------------------------------------


def test_write_serialize_result_create() -> None:
    tool = WriteTool()
    output = {"type": "create", "filePath": "/tmp/foo.py", "displayPath": "foo.py"}
    result = tool.serialize_result(output)
    assert result == "File created successfully at: foo.py"


def test_write_serialize_result_update() -> None:
    tool = WriteTool()
    output = {"type": "update", "filePath": "/tmp/bar.py", "displayPath": "bar.py"}
    result = tool.serialize_result(output)
    assert result == "The file bar.py has been updated successfully."


def test_write_serialize_result_fallback_for_unknown_type() -> None:
    tool = WriteTool()
    output = {"type": "unknown", "filePath": "/tmp/baz.py", "displayPath": "baz.py"}
    result = tool.serialize_result(output)
    import json
    assert json.loads(result) == output


def test_edit_serialize_result_success() -> None:
    tool = EditTool()
    output = {"filePath": "/tmp/foo.py", "displayPath": "foo.py", "replaceAll": False}
    result = tool.serialize_result(output)
    assert result == "The file foo.py has been updated successfully."


def test_edit_serialize_result_replace_all() -> None:
    tool = EditTool()
    output = {"filePath": "/tmp/bar.py", "displayPath": "bar.py", "replaceAll": True}
    result = tool.serialize_result(output)
    assert result == (
        "The file bar.py has been updated. "
        "All occurrences were successfully replaced."
    )


def test_edit_serialize_result_error() -> None:
    tool = EditTool()
    result = tool.serialize_result(None, error="file does not exist")
    assert result == "file does not exist"


def test_edit_serialize_result_fallback() -> None:
    tool = EditTool()
    result = tool.serialize_result("unexpected string")
    assert result == '"unexpected string"'


# ---------------------------------------------------------------------------
# SessionFileState / read-before-write guard
# ---------------------------------------------------------------------------


class TestWriteReadBeforeWrite:
    def test_rejects_overwrite_when_file_never_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        with pytest.raises(ToolError) as exc_info:
            WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert exc_info.value.details.get("errorCode") == 6
        assert "has not been read yet" in str(exc_info.value)

    def test_rejects_overwrite_when_file_stale(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        stat = (tmp_path / "existing.txt").stat()
        state.record_read(str(tmp_path / "existing.txt"), stat.st_mtime_ns, stat.st_size, offset=1, limit=None)

        # Simulate external modification
        (tmp_path / "existing.txt").write_text("externally changed", encoding="utf-8")

        with pytest.raises(ToolError) as exc_info:
            WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert exc_info.value.details.get("errorCode") == 7
        assert "modified externally" in str(exc_info.value)

    def test_allows_create_without_read(self, tmp_path: Path) -> None:
        ctx, _state = _context_with_state(tmp_path)

        result = WriteTool().run({"path": "newfile.txt", "content": "hello"}, ctx)

        assert result["type"] == "create"

    def test_allows_overwrite_after_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        # Simulate prior read
        ReadTool().run({"path": "existing.txt"}, ctx)

        result = WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert result["type"] == "update"
        assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "new"

    def test_allows_second_write_after_first(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("v1", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)
        WriteTool().run({"path": "existing.txt", "content": "v2"}, ctx)

        # Second write should succeed because first write updated the state.
        result = WriteTool().run({"path": "existing.txt", "content": "v3"}, ctx)
        assert result["type"] == "update"


class TestEditReadBeforeWrite:
    def test_rejects_edit_when_file_never_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        with pytest.raises(ToolError) as exc_info:
            EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert exc_info.value.details.get("errorCode") == 6
        assert "has not been read yet" in str(exc_info.value)

    def test_rejects_edit_when_file_stale(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        stat = (tmp_path / "existing.txt").stat()
        state.record_read(str(tmp_path / "existing.txt"), stat.st_mtime_ns, stat.st_size, offset=1, limit=None)

        (tmp_path / "existing.txt").write_text("externally changed", encoding="utf-8")

        with pytest.raises(ToolError) as exc_info:
            EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert exc_info.value.details.get("errorCode") == 7
        assert "modified externally" in str(exc_info.value)

    def test_allows_edit_after_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)

        result = EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert result["displayPath"] == "existing.txt"
        assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "hi world"

    def test_allows_second_edit_after_first(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)
        EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        # Second edit should succeed because first edit updated the state.
        result = EditTool().run({"path": "existing.txt", "oldText": "hi", "newText": "hey"}, ctx)
        assert result["displayPath"] == "existing.txt"
