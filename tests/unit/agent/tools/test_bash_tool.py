"""Tests for BashTool background/foreground paths."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool


class _FakeStopper:
    def stop(self) -> None:
        pass


class _FakeBashRunner:
    """Fake bash runner that completes quickly or slowly based on command."""

    def __init__(self, *, delay: float = 0.0, exit_code: int = 0) -> None:
        self._delay = delay
        self._exit_code = exit_code

    def start(self, *, command, cwd, output, task_id, timeout, on_complete, on_fail):
        def _worker() -> None:
            if self._delay > 0:
                time.sleep(self._delay)
            if self._exit_code == 0:
                on_complete(
                    task_id=task_id,
                    result_text=None,
                    usage=None,
                    duration_ms=int(self._delay * 1000),
                    tool_use_count=0,
                )
            else:
                on_fail(task_id=task_id, error=f"exit code {self._exit_code}")

        threading.Thread(target=_worker, daemon=True).start()
        return _FakeStopper()


class _FakeOutput:
    def __init__(self, tmpdir: str) -> None:
        self._tmpdir = tmpdir
        self._paths: dict[str, Path] = {}

    def open(self, parent_session_id: str, task_id: str) -> Path:
        path = Path(self._tmpdir) / "tasks" / parent_session_id / f"{task_id}.output"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(f"# Background task {task_id} — output will appear here\n")
        self._paths[task_id] = path
        return path

    def append(self, task_id: str, text: str, *, stream: str = "stdout") -> None:
        path = self._paths.get(task_id)
        if path is None:
            return
        with path.open("a", encoding="utf-8") as f:
            f.write(text)

    def flush(self, task_id: str) -> None:
        pass


def _make_tool(*, with_wiring: bool = True, runner_delay: float = 0.0, runner_exit: int = 0) -> BashTool:
    if not with_wiring:
        return BashTool()

    registry = BackgroundTaskRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _FakeBashRunner(delay=runner_delay, exit_code=runner_exit)

    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner

    return BashTool(wiring=wiring)


def _make_ctx(tmpdir: str) -> ToolContext:
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    safety = ToolSafety(repo_root=Path(tmpdir), config=ToolSafetyConfig())
    return ToolContext(repo_root=Path(tmpdir), cwd=Path(tmpdir), safety=safety, session_id="parent_1")


# ------------------------------------------------------------------
# Background launch
# ------------------------------------------------------------------

def test_background_launch_returns_async_launched() -> None:
    tool = _make_tool()
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "echo hello",
                "description": "test bg",
                "run_in_background": True,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["task_id"].startswith("b")
        assert "output_file" in result
        assert result["description"] == "test bg"


# ------------------------------------------------------------------
# Foreground completion
# ------------------------------------------------------------------

def test_foreground_completes_within_budget() -> None:
    tool = _make_tool(runner_delay=0.0)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "echo hello",
                "run_in_background": False,
            },
            ctx,
        )
        assert result["exitCode"] == 0
        assert "stdout" in result


# ------------------------------------------------------------------
# Foreground auto-background
# ------------------------------------------------------------------

def test_foreground_auto_backgrounds_on_slow_command(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch budget to 0.1s so the test completes quickly.
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._DEFAULT_FOREGROUND_BUDGET", 0.1
    )
    tool = _make_tool(runner_delay=0.5)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "sleep 20",
                "run_in_background": False,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["task_id"].startswith("b")
        assert "output_file" in result


# ------------------------------------------------------------------
# Foreground failure within budget
# ------------------------------------------------------------------

def test_foreground_fails_within_budget_raises_tool_error() -> None:
    tool = _make_tool(runner_delay=0.0, runner_exit=1)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="Command exited with code 1"):
            tool.run(
                {
                    "command": "false",
                    "run_in_background": False,
                },
                ctx,
            )


# ------------------------------------------------------------------
# Legacy sync path (no wiring)
# ------------------------------------------------------------------

def test_legacy_sync_without_wiring() -> None:
    tool = _make_tool(with_wiring=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "echo hello",
                "run_in_background": False,
            },
            ctx,
        )
        assert result["exitCode"] == 0
        assert "hello" in result["stdout"]


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------

def test_serialize_async_launched() -> None:
    tool = _make_tool()
    text = tool.serialize_result({
        "status": "async_launched",
        "task_id": "b1234",
        "output_file": "/tmp/out.txt",
    })
    assert "b1234" in text
    assert "/tmp/out.txt" in text


def test_serialize_completed() -> None:
    tool = _make_tool()
    text = tool.serialize_result({
        "stdout": "hello world",
        "exitCode": 0,
    })
    assert text == "hello world"


def test_serialize_no_output() -> None:
    tool = _make_tool()
    text = tool.serialize_result({
        "stdout": "",
        "exitCode": 0,
    })
    assert text == "(no output)"
