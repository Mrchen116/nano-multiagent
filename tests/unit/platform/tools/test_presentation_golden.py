"""Presentation golden baseline (refactor-406 决策 12 risk: IM 渲染零变化).

Before migrating presenter resolution off the platform global registry
(`_PRESENTERS` / `register_presenter` / `resolve_presenter`) onto the Tool object
(`tool.presenter`, resolved kernel-scoped), this test snapshots the **exact**
``format_start`` / ``format_end`` output of every built-in presenter + the default
fallback for a fixed input matrix. The migration must keep these byte-for-byte
(same打法 as the R1 prompt golden): the assertions below are the contract; the
resolution *path* changes underneath, the rendered values do not.

Each case asserts the full (visible, label, summary, detail) tuple so any drift in
any field fails. ``_resolve`` is the single seam that the migration re-points; the
expected values never change.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

# Seam (决策 12): resolve a presenter the kernel-scoped way — read it off the
# built-in tool object's ``.presenter`` (presentation travels with the tool),
# default for unknown names. This is the single line the migration re-points; the
# expected values below never change.
from agent.platform.tools.presentation import resolve_presenter_for_tool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.web_fetch import WebFetchTool
from agent.platform.tools.builtins.agent import AgentTool

_TOOL_BY_NAME = {
    "read": ReadTool,
    "write": WriteTool,
    "edit": EditTool,
    "bash": BashTool,
    "web_fetch": WebFetchTool,
    "agent": AgentTool,
}


def _resolve(name: str):
    tool = _TOOL_BY_NAME.get(name)
    # Pass the class (presenter is a class attribute) — unknown names → default.
    return resolve_presenter_for_tool(tool)


def _evt_tuple(evt: Any) -> tuple:
    detail = evt.detail
    return (
        evt.visible,
        evt.label,
        evt.summary,
        dict(detail) if detail is not None else None,
    )


class _Result:
    def __init__(self, output: Any = None, error: str | None = None) -> None:
        self.output = output
        self.error = error


# (tool_name, args, expected_start_tuple)
_START_CASES = [
    ("read", {"path": "src/app.py"}, (True, "Read", "src/app.py", None)),
    ("write", {"path": "src/app.py"}, (True, "Write", "src/app.py", None)),
    ("edit", {"path": "src/app.py"}, (True, "Edit", "src/app.py", None)),
    ("bash", {"command": "pytest tests/"}, (True, "Bash", "pytest tests/", None)),
    (
        "web_fetch",
        {"url": "https://example.com"},
        (True, "Web", "https://example.com", None),
    ),
    (
        "agent",
        {"description": "Refactor auth module"},
        (True, "Agent", "Refactor auth module", None),
    ),
    (
        "unknown_xyz",
        {"foo": "bar"},
        (True, "Tool", '{"foo": "bar"}', None),
    ),
]


@pytest.mark.parametrize("name,args,expected", _START_CASES)
def test_format_start_golden(
    name: str, args: Mapping[str, Any], expected: tuple
) -> None:
    evt = _resolve(name).format_start(dict(args))
    assert _evt_tuple(evt) == expected, f"{name} format_start drifted"


def test_read_end_text_lines_golden() -> None:
    # feat-409 readfix: read summary/detail 现在带 path。
    evt = _resolve("read").format_end(
        {"path": "src/app.py"},
        _Result(output={"path": "src/app.py", "total_lines": 42, "offset": 1}),
        duration_ms=5,
    )
    assert _evt_tuple(evt) == (
        True,
        "Read",
        "src/app.py · 42 lines",
        {
            "path": "src/app.py",
            "total_lines": 42,
            "offset": 1,
            "limit": None,
            "truncated": False,
        },
    )


def test_read_end_unchanged_golden() -> None:
    evt = _resolve("read").format_end(
        {"path": "src/app.py"},
        _Result(output={"path": "src/app.py", "type": "file_unchanged"}),
        duration_ms=1,
    )
    assert _evt_tuple(evt) == (
        True,
        "Read",
        "src/app.py · unchanged",
        {"path": "src/app.py", "unchanged": True},
    )


def test_write_end_created_golden() -> None:
    evt = _resolve("write").format_end(
        {"path": "a.txt", "content": "hello"},
        _Result(output={"type": "create"}),
        duration_ms=2,
    )
    assert evt.visible is True
    assert evt.label == "Write"
    assert evt.summary == "created (5 bytes)"
    assert evt.detail is not None and evt.detail["path"] == "a.txt"
    assert evt.detail["content"] == "hello" and evt.detail["bytes"] == 5


def test_bash_end_success_golden() -> None:
    evt = _resolve("bash").format_end(
        {"command": "echo hi"},
        _Result(output={"exitCode": 0, "stdout": "hi\n", "stderr": ""}),
        duration_ms=12,
    )
    assert evt.visible is True
    assert evt.label == "Bash"
    # 决策 4:summary 为人话;无 description 时降级为命令首段。
    assert evt.summary == "echo hi"
    assert evt.detail is not None and evt.detail["exit_code"] == 0
    assert evt.detail["stdout"] == "hi\n"


def test_bash_end_failed_golden() -> None:
    # feat-409 failalign: 失败态 summary = 干净人话主参数(命令首段,无 description 时),
    # 不含 error 文本;error 进 detail(BashCard 在 stderr 槽渲染一次)。
    evt = _resolve("bash").format_end(
        {"command": "false"},
        _Result(error="command failed"),
        duration_ms=3,
    )
    assert evt.visible is True
    assert evt.label == "Bash"
    assert evt.summary == "false"
    assert evt.detail == {"command": "false", "error": {"message": "command failed"}}


def test_default_end_golden() -> None:
    evt = _resolve("unknown_xyz").format_end(
        {"foo": "bar"},
        _Result(output={"ok": True}),
        duration_ms=1,
    )
    assert evt.visible is True
    assert evt.label == "Tool"
