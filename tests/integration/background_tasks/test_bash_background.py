"""Integration tests for background bash execution with real shell runner."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _RunsRegistryStub:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.injections: list[dict[str, Any]] = []
        self._active_run_by_session: dict[str, str] = {}

    def get_active_run_id(self, session_id: str) -> str | None:
        return self._active_run_by_session.get(session_id)

    def inject_pending_message(self, session_id: str, message: LLMMessage) -> bool:
        self.injections.append({"session_id": session_id, "message": message})
        return True

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict[str, Any]],
        origin: RunOrigin = RunOrigin.USER,
        source_task_id: str | None = None,
        trace_id: str | None = None,
    ) -> Any:
        self.submissions.append({
            "session_id": session_id,
            "parts": parts,
            "origin": origin,
            "source_task_id": source_task_id,
        })
        return type("RunRecord", (), {"run_id": "run_1", "session_id": session_id, "status": "queued"})()


def _make_ctx(tmp_path: Path, session_id: str = "sess_parent") -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session(session_id=session_id)


def test_background_bash_launches_and_returns_async_receipt(tmp_path: Path) -> None:
    wiring = wire_background_tasks(workspace_root=tmp_path)
    tool = BashTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "command": "echo hello_bg",
            "description": "echo test",
            "run_in_background": True,
        },
        ctx,
    )

    assert result["status"] == "async_launched"
    assert result["task_id"].startswith("b")
    assert "output_file" in result
    assert result["description"] == "echo test"


def test_background_bash_output_file_is_created_and_written(tmp_path: Path) -> None:
    wiring = wire_background_tasks(workspace_root=tmp_path)
    tool = BashTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "command": "echo hello_output",
            "description": "output test",
            "run_in_background": True,
        },
        ctx,
    )

    output_file = Path(result["output_file"])
    assert output_file.exists()

    # Poll for process completion.
    task_id = result["task_id"]
    for _ in range(50):
        record = wiring.registry.get(task_id)
        if record is not None and record.status.value in ("completed", "failed", "killed"):
            break
        time.sleep(0.05)

    text = output_file.read_text(encoding="utf-8")
    assert "hello_output" in text


def test_background_bash_completes_and_delivers_notification(tmp_path: Path) -> None:
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=runs)
    tool = BashTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "command": "echo notify_me",
            "description": "notify test",
            "run_in_background": True,
        },
        ctx,
    )

    task_id = result["task_id"]

    # Poll for completion.
    for _ in range(50):
        record = wiring.registry.get(task_id)
        if record is not None and record.status.value in ("completed", "failed", "killed"):
            break
        time.sleep(0.05)

    record = wiring.registry.get(task_id)
    assert record is not None
    assert record.status.value == "completed"

    # Notification delivered to parent session.
    assert len(runs.submissions) == 1
    assert runs.submissions[0]["session_id"] == "sess_parent"
    assert runs.submissions[0]["origin"] == RunOrigin.BACKGROUND_TASK
    assert runs.submissions[0]["source_task_id"] == task_id
    parts = runs.submissions[0]["parts"]
    assert len(parts) == 1
    assert "<task-notification>" in parts[0]["text"]
    assert task_id in parts[0]["text"]


def test_background_bash_failed_exit_code_delivers_failed_notification(tmp_path: Path) -> None:
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=runs)
    tool = BashTool(wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "command": "exit 42",
            "description": "fail test",
            "run_in_background": True,
        },
        ctx,
    )

    task_id = result["task_id"]

    for _ in range(50):
        record = wiring.registry.get(task_id)
        if record is not None and record.status.value in ("completed", "failed", "killed"):
            break
        time.sleep(0.05)

    record = wiring.registry.get(task_id)
    assert record is not None
    assert record.status.value == "failed"

    assert len(runs.submissions) == 1
    assert "<task-notification>" in runs.submissions[0]["parts"][0]["text"]
    assert "failed" in runs.submissions[0]["parts"][0]["text"]
