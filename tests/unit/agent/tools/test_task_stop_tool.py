"""Tests for TaskStopTool."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.task_stop import TaskStopTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


def _make_tool() -> TaskStopTool:
    registry = BackgroundTaskRegistry()
    wiring = MagicMock()
    wiring.registry = registry
    return TaskStopTool(wiring=wiring)


def _make_ctx(tmpdir: str) -> ToolContext:
    safety = ToolSafety(repo_root=Path(tmpdir), config=ToolSafetyConfig())
    return ToolContext(
        repo_root=Path(tmpdir), cwd=Path(tmpdir), safety=safety, session_id="parent_1"
    )


def test_stop_running_bash_task_kills_synchronously_and_suppresses_notification() -> (
    None
):
    """bugfix-420 decision 1: stopping a bash task synchronously transitions it
    to KILLED with notified=True so the _NotifyingStore wrapper suppresses the
    model-facing <task-notification> (LLM only sees the tool_result)."""
    tool = _make_tool()
    registry = tool._wiring.registry

    registry.register_bash(
        task_id="b1",
        parent_session_id="parent_1",
        description="test",
        command="sleep 30",
        output_file="/tmp/b1.output",
    )
    registry.mark_running("b1")
    registry.set_stop_handle("b1", MagicMock())

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run({"task_id": "b1"}, ctx)

    assert result["status"] == "killed"
    assert result["task_id"] == "b1"
    assert result["task_type"] == "bash"

    record = registry.get("b1")
    assert record is not None
    assert record.status == BackgroundTaskStatus.KILLED
    # Suppression flag set so the notifying store skips delivery.
    assert record.notified is True


def test_stop_running_subagent_defers_terminal_to_worker_unwind() -> None:
    """bugfix-420 decision 2: stopping a subagent only requests stop; it does
    NOT synchronously kill. The terminal transition (carrying the partial
    <result>) is owned by the worker's abort-unwind path (on_kill), so the
    registry record must stay non-terminal right after task_stop returns."""
    tool = _make_tool()
    registry = tool._wiring.registry

    registry.register_subagent(
        task_id="a1",
        parent_session_id="parent_1",
        agent_id="a1",
        agent_session_id="sess_1",
        description="research",
        prompt="do research",
        agent_type="explore",
        output_file="/tmp/a1.output",
    )
    registry.mark_running("a1")
    stop_handle = MagicMock()
    registry.set_stop_handle("a1", stop_handle)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run({"task_id": "a1"}, ctx)

    assert result["status"] == "killed"
    assert result["task_id"] == "a1"
    assert result["task_type"] == "subagent"

    # Stop was requested (abort signalled to the worker)...
    stop_handle.stop.assert_called_once()
    # ...but task_stop did NOT flip the record terminal; the worker unwind does.
    record = registry.get("a1")
    assert record is not None
    assert record.status == BackgroundTaskStatus.RUNNING


def test_stop_not_found_raises_tool_error() -> None:
    tool = _make_tool()

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="No background task found") as exc_info:
            tool.run({"task_id": "b_missing"}, ctx)

    assert exc_info.value.details.get("code") == "task_not_found"


def test_stop_already_terminal_raises_tool_error() -> None:
    tool = _make_tool()
    registry = tool._wiring.registry

    registry.register_bash(
        task_id="b1",
        parent_session_id="parent_1",
        description="test",
        command="echo done",
        output_file="/tmp/b1.output",
    )
    registry.mark_running("b1")
    registry.complete("b1")

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="already completed") as exc_info:
            tool.run({"task_id": "b1"}, ctx)

    assert exc_info.value.details.get("code") == "task_already_terminal"


def test_serialize_killed() -> None:
    tool = _make_tool()
    text = tool.serialize_result(
        {
            "status": "killed",
            "task_id": "b1",
            "task_type": "bash",
            "output_file": "/tmp/b1.output",
        }
    )
    assert "Task stopped." in text
    assert "b1" in text
    assert "/tmp/b1.output" in text


def test_missing_task_id_raises() -> None:
    tool = _make_tool()

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="task_id is required"):
            tool.run({"task_id": ""}, ctx)
