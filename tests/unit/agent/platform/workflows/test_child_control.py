from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core.types import Message, TurnResult
from agent.core.workflows import AgentCallSpec
from agent.platform.workflows import WorkflowChildRunner, WorkflowLaunchContext


class _Control:
    def __init__(self) -> None:
        self.directory = SimpleNamespace(
            get=lambda _ref: SimpleNamespace(tool_allowlist=(), skills=None)
        )
        self.ref = object()
        self.created = 0

    def list_parent_enabled_tool_names(self):
        return ()

    def resolve_run_model(self):
        return "parent-model"

    def resolve_reasoning_effort(self):
        return "high"

    def create_subagent(self, **_kwargs):
        self.created += 1
        return SimpleNamespace(session_id=f"child-{self.created}")


class _NoActiveRunControl(_Control):
    def list_parent_enabled_tool_names(self):
        raise RuntimeError("active ContextVar is unavailable in manager thread")

    def resolve_run_model(self):
        raise RuntimeError("active ContextVar is unavailable in manager thread")

    def resolve_reasoning_effort(self):
        raise RuntimeError("active ContextVar is unavailable in manager thread")


class _AttemptHandle:
    def __init__(self, result_text: str) -> None:
        self.result_text = result_text
        self.released = threading.Event()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True
        self.released.set()

    def result(self):
        self.released.wait(timeout=2)
        if self.stopped:
            raise RuntimeError("attempt stopped")
        return TurnResult(
            session_id="child",
            turn_id="turn",
            messages=(
                Message(
                    message_id="message",
                    role="assistant",
                    content=self.result_text,
                ),
            ),
        )


class _Runner:
    def __init__(self) -> None:
        self.handles: list[_AttemptHandle] = []

    def start_workflow_agent(self, **_kwargs):
        handle = _AttemptHandle(f"attempt-{len(self.handles) + 1}")
        self.handles.append(handle)
        return handle


async def _wait_for_attempts(runner: _Runner, count: int) -> None:
    for _ in range(100):
        if len(runner.handles) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected {count} Workflow Agent attempts")


def _call() -> AgentCallSpec:
    return AgentCallSpec(prompt="review", start_ordinal=0, resume_key="key")


@pytest.mark.asyncio
async def test_restart_replaces_attempt_but_preserves_logical_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent.platform.workflows.child.provider_of", lambda _model: "p"
    )
    control = _Control()
    runner = _Runner()
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=control,
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
    )

    task = asyncio.create_task(child(_call()))
    await _wait_for_attempts(runner, 1)
    assert child.restart_agent("wa_000000") is True
    await _wait_for_attempts(runner, 2)
    runner.handles[1].released.set()

    assert await task == "attempt-2"
    assert control.created == 2
    assert child.status_for("wa_000000") == "completed"


@pytest.mark.asyncio
async def test_stop_selected_agent_returns_none_without_stopping_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent.platform.workflows.child.provider_of", lambda _model: "p"
    )
    runner = _Runner()
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=_Control(),
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
    )

    task = asyncio.create_task(child(_call()))
    await _wait_for_attempts(runner, 1)
    assert child.stop_agent("wa_000000") is True

    assert await task is None
    assert child.status_for("wa_000000") == "stopped"


@pytest.mark.asyncio
async def test_child_uses_parent_runtime_snapshot_outside_the_active_turn_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent.platform.workflows.child.provider_of", lambda _model: "p"
    )
    control = _NoActiveRunControl()
    runner = _Runner()
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=control,
            parent_runtime_captured=True,
            parent_model="captured-model",
            parent_effort="high",
            parent_enabled_tools=("read",),
            parent_skills=("review",),
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
    )

    task = asyncio.create_task(child(_call()))
    await _wait_for_attempts(runner, 1)
    runner.handles[0].released.set()

    assert await task == "attempt-1"
