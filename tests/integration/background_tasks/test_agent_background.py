"""Integration tests for background agent execution with runtime stub."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.runs.origin import RunOrigin
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.types import Message, TurnResult
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

from ._runtime_stub import _RunsRegistryStub, _RuntimeStubBase, _make_ctx

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _RuntimeStub(_RuntimeStubBase):
    def __init__(
        self,
        tmp_path: Path,
        delay: float = 0.0,
        gate: threading.Event | None = None,
    ) -> None:
        super().__init__(tmp_path, delay)
        # gate: 当测试需要确定性观察到 RUNNING 状态时,run() 在返回前阻塞等待它 set,
        # 避免用 sleep 在高负载 CI 上仍可能让后台任务先跑完导致竞态。
        self._gate = gate
        # bugfix-422 (#129): record the llm_session_id seen by each run() so tests
        # can assert the subagent's LLM requests reuse the parent session id.
        self.run_calls: list[dict[str, Any]] = []

    async def run(
        self,
        session_id: str,
        parts: Any,
        *,
        stream: bool = False,
        controller: Any = None,
        parent_session_id: str | None = None,
        workspace_root: Any = None,
        run_id: str | None = None,
        llm_session_id: str | None = None,
        model: str | None = None,
    ) -> TurnResult:
        self.run_calls.append(
            {
                "session_id": session_id,
                "parent_session_id": parent_session_id,
                "llm_session_id": llm_session_id,
            }
        )
        if self._delay > 0:
            time.sleep(self._delay)
        if self._gate is not None:
            # 阻塞直到测试断言完 RUNNING 后放行;超时兜底防测试 bug 时整 job 挂死。
            self._gate.wait(timeout=10)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_1",
            messages=(
                Message(message_id="msg_1", role="assistant", content="subagent done"),
            ),
            completed=True,
            stop_reason="completed",
        )


def test_background_agent_launches_and_returns_async_receipt(tmp_path: Path) -> None:
    runtime = _RuntimeStub(tmp_path)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "description": "research loop",
            "prompt": "Study the core loop.",
            "subagent_type": "explore",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )

    assert result["status"] == "async_launched"
    agent_id = result["agent_id"]
    assert agent_id.startswith("a")
    assert "output_file" in result
    assert result["description"] == "research loop"


def test_background_agent_registry_record_created(tmp_path: Path) -> None:
    # gate 让后台 run() 阻塞在完成前,确保断言能确定性观察到 RUNNING 而非偶发的 completed。
    gate = threading.Event()
    runtime = _RuntimeStub(tmp_path, gate=gate)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    try:
        result = tool.run(
            {
                "description": "test agent",
                "prompt": "Do something.",
                "subagent_type": "oracle",
                "load_skills": [],
                "run_in_background": True,
            },
            ctx,
        )

        agent_id = result["agent_id"]
        record = wiring.registry.get(agent_id)
        assert record is not None
        assert record.status == BackgroundTaskStatus.RUNNING
        assert record.task_type.value == "subagent"
        assert record.parent_session_id == "sess_parent"
    finally:
        gate.set()


def test_background_agent_completes_and_delivers_notification(tmp_path: Path) -> None:
    runtime = _RuntimeStub(tmp_path, delay=0.1)
    runs = _RunsRegistryStub()
    wiring = wire_background_tasks(
        workspace_root=tmp_path, runtime=runtime, runs_registry=runs
    )
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "description": "notify test",
            "prompt": "Do something.",
            "subagent_type": "oracle",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )

    agent_id = result["agent_id"]

    # Poll for completion.
    for _ in range(50):
        record = wiring.registry.get(agent_id)
        if record is not None and record.status.value in (
            "completed",
            "failed",
            "killed",
        ):
            break
        time.sleep(0.05)

    record = wiring.registry.get(agent_id)
    assert record is not None
    assert record.status.value == "completed"
    assert record.result_text == "subagent done"

    # Notification delivered.
    assert len(runs.submissions) == 1
    assert runs.submissions[0]["session_id"] == "sess_parent"
    assert runs.submissions[0]["origin"] == RunOrigin.BACKGROUND_TASK
    assert runs.submissions[0]["source_task_id"] == agent_id
    assert "<task-notification>" in runs.submissions[0]["parts"][0]["text"]
    assert agent_id in runs.submissions[0]["parts"][0]["text"]


def test_background_subagent_run_reuses_parent_llm_session_id(tmp_path: Path) -> None:
    """bugfix-422 (#129): end-to-end through the real wiring + RuntimeRunner, the
    subagent's runtime.run() must be called with llm_session_id=parent so the LLM
    proxy groups the subagent under the parent session, while the run target stays
    the subagent's own (independent) session id."""
    runtime = _RuntimeStub(tmp_path, delay=0.05)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    result = tool.run(
        {
            "description": "session grouping",
            "prompt": "Do something.",
            "subagent_type": "oracle",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]

    # Poll for the worker thread to actually invoke runtime.run.
    for _ in range(50):
        if runtime.run_calls:
            break
        time.sleep(0.05)

    assert len(runtime.run_calls) == 1
    call = runtime.run_calls[0]
    assert call["llm_session_id"] == "sess_parent"
    assert call["parent_session_id"] == "sess_parent"
    # The run target is the subagent's own session, not the parent's.
    assert call["session_id"] != "sess_parent"
    assert agent_id  # receipt returned
