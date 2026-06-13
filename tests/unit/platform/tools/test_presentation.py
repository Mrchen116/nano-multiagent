"""Unit tests for built-in tool presenters."""

from agent.core.tools.presentation import ToolPresentationEvent
from agent.platform.tools.presentation import resolve_presenter_for_tool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.web_fetch import WebFetchTool
from agent.platform.tools.builtins.task import TaskTool

_TOOL_BY_NAME = {
    "read": ReadTool,
    "write": WriteTool,
    "edit": EditTool,
    "bash": BashTool,
    "web_fetch": WebFetchTool,
    "task": TaskTool,
}


class _FakeResult:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error


def _presenter(name: str):
    # 决策 12: presenter travels with the tool object; resolve off the built-in
    # tool class .presenter (unknown names → default presenter).
    return resolve_presenter_for_tool(_TOOL_BY_NAME.get(name))


class TestReadPresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("read").format_start({"path": "src/app.py"})
        assert evt.visible is True
        assert evt.label == "Read"
        assert evt.summary == "src/app.py"

    def test_end_text_file_lines(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "src/app.py"},
            _FakeResult(output={"total_lines": 120, "offset": 1}),
            duration_ms=12,
        )
        assert evt.summary == "120 lines"

    def test_end_text_file_with_limit(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "src/app.py", "limit": 40},
            _FakeResult(output={"total_lines": 120, "offset": 40}),
            duration_ms=12,
        )
        assert evt.summary == "lines 40-79"

    def test_end_image(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "img.png"},
            _FakeResult(output={"content": [{"type": "image", "data": "..."}]}),
            duration_ms=12,
        )
        assert evt.summary == "image"

    def test_end_unchanged(self) -> None:
        evt = _presenter("read").format_end(
            {"path": "src/app.py"},
            _FakeResult(output={"type": "file_unchanged"}),
            duration_ms=12,
        )
        assert evt.summary == "unchanged"


class TestWritePresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("write").format_start({"path": "src/app.py"})
        assert evt.label == "Write"
        assert evt.summary == "src/app.py"

    def test_end_created(self) -> None:
        evt = _presenter("write").format_end(
            {"path": "src/app.py", "content": "hello"},
            _FakeResult(output={"type": "create"}),
            duration_ms=5,
        )
        assert "created" in evt.summary
        assert evt.detail is not None
        assert evt.detail["path"] == "src/app.py"
        assert evt.detail["bytes"] == 5

    def test_end_updated(self) -> None:
        evt = _presenter("write").format_end(
            {"path": "src/app.py", "content": "hello world"},
            _FakeResult(output={"type": "update"}),
            duration_ms=5,
        )
        assert "overwritten" in evt.summary
        assert evt.detail is not None


class TestEditPresenter:
    def test_start_shows_path(self) -> None:
        evt = _presenter("edit").format_start({"path": "src/app.py"})
        assert evt.label == "Edit"
        assert evt.summary == "src/app.py"

    def test_end_updated(self) -> None:
        evt = _presenter("edit").format_end(
            {"path": "src/app.py", "oldText": "foo", "newText": "bar"},
            _FakeResult(output={}),
            duration_ms=5,
        )
        assert "updated" in evt.summary
        assert evt.detail is not None
        assert "diff" in evt.detail

    def test_end_failed(self) -> None:
        evt = _presenter("edit").format_end(
            {"path": "src/app.py", "oldText": "foo", "newText": "bar"},
            _FakeResult(error="Could not find the exact text"),
            duration_ms=5,
        )
        assert "failed" in evt.summary
        assert evt.detail is not None
        assert "error" in evt.detail


class TestBashPresenter:
    def test_start_shows_command(self) -> None:
        evt = _presenter("bash").format_start({"command": "pytest tests/"})
        assert evt.label == "Bash"
        assert evt.summary == "pytest tests/"

    def test_end_success(self) -> None:
        evt = _presenter("bash").format_end(
            {"command": "pytest"},
            _FakeResult(output={"exitCode": 0, "stdout": "OK"}),
            duration_ms=2100,
        )
        assert "exit=0" in evt.summary
        assert "elapsed=2100ms" in evt.summary
        assert evt.detail is not None
        assert evt.detail["stdout"] == "OK"

    def test_end_failed(self) -> None:
        evt = _presenter("bash").format_end(
            {"command": "pytest"},
            _FakeResult(error="Command exited with code 1"),
            duration_ms=500,
        )
        assert "failed" in evt.summary


class TestWebFetchPresenter:
    def test_start_shows_url(self) -> None:
        evt = _presenter("web_fetch").format_start({"url": "https://example.com"})
        assert evt.label == "Web"
        assert evt.summary == "https://example.com"

    def test_end_success(self) -> None:
        evt = _presenter("web_fetch").format_end(
            {"url": "https://example.com"},
            _FakeResult(output={"status": 200, "title": "Example"}),
            duration_ms=300,
        )
        assert "status=200" in evt.summary
        assert "Example" in evt.summary
        assert evt.detail is not None
        assert evt.detail["status"] == 200


class TestTaskPresenter:
    def test_start_shows_description(self) -> None:
        evt = _presenter("task").format_start({"description": "Refactor auth module"})
        assert evt.label == "Task"
        assert evt.summary == "Refactor auth module"

    def test_end_success(self) -> None:
        evt = _presenter("task").format_end(
            {"description": "Refactor auth module"},
            _FakeResult(output={"status": "completed", "summary": "Done"}),
            duration_ms=5000,
        )
        assert "status=completed" in evt.summary
        assert evt.detail is not None


class TestDefaultPresenter:
    def test_unknown_tool(self) -> None:
        evt = _presenter("unknown_tool_xyz").format_start({"foo": "bar"})
        assert evt.visible is True
        assert evt.label == "Tool"

    def test_default_end_with_error(self) -> None:
        evt = _presenter("unknown_tool_xyz").format_end(
            {"foo": "bar"},
            _FakeResult(error="something broke"),
            duration_ms=10,
        )
        assert "failed" in evt.summary
