from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.types import SessionRef
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
        self.created_kwargs = []
        self.files = JsonlSessionFiles(
            data_dir=None, workspace_config_dirname=".nanocode"
        )

    def list_parent_enabled_tool_names(self):
        return ()

    def resolve_run_model(self):
        return "parent-model"

    def resolve_reasoning_effort(self):
        return "high"

    def create_subagent(self, **kwargs):  # noqa: ANN003
        self.created += 1
        self.created_kwargs.append(kwargs)
        return SessionRef(
            session_id=f"child-{self.created}",
            workspace_root=kwargs["workspace_root"],
            parent_session_id="parent",
        )


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
        self.started_kwargs = []

    def start_workflow_agent(self, **kwargs):  # noqa: ANN003
        self.started_kwargs.append(kwargs)
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
        model_override="codexOAuth:gpt-5.6-luna",
    )

    task = asyncio.create_task(child(_call()))
    await _wait_for_attempts(runner, 1)
    runner.handles[0].released.set()

    assert await task == "attempt-1"
    assert control.created_kwargs[0]["runtime_model"] == ("codexOAuth:gpt-5.6-luna")
    assert control.created_kwargs[0]["runtime_reasoning_effort"] == "high"
    assert runner.started_kwargs[0]["model"] == "codexOAuth:gpt-5.6-luna"


@pytest.mark.asyncio
async def test_invalid_child_override_substitutes_parent_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _provider(model: str) -> str:
        if model == "parent-model":
            return "provider"
        raise ValueError(f"unknown model: {model}")

    monkeypatch.setattr("agent.platform.workflows.child.provider_of", _provider)
    control = _Control()
    runner = _Runner()
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=control,
            parent_runtime_captured=True,
            parent_model="parent-model",
            parent_effort="high",
            parent_enabled_tools=(),
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
        model_override="missing-luna",
    )

    first = asyncio.create_task(child(_call()))
    await _wait_for_attempts(runner, 1)
    runner.handles[0].released.set()
    assert await first == "attempt-1"

    second = asyncio.create_task(
        child(AgentCallSpec(prompt="verify", start_ordinal=1, resume_key="key-2"))
    )
    await _wait_for_attempts(runner, 2)
    runner.handles[1].released.set()
    assert await second == "attempt-2"

    assert [item["model"] for item in runner.started_kwargs] == [
        "parent-model",
        "parent-model",
    ]
    assert child.warnings == (
        "workflow_model_substituted: requested=missing-luna, resolved=parent-model",
    )
