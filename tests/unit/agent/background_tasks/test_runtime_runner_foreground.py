"""Tests for the typed subagent adapter over Directory and KernelExecutor."""

from __future__ import annotations

import threading
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.core.types import Message, TurnResult
from agent.platform.background_tasks.runtime_runner import RuntimeRunner


class _Auxiliary:
    def __init__(self, future: Future[TurnResult]) -> None:
        self.future = future
        self.cancelled = False

    def result(self, timeout: float | None = None) -> TurnResult:
        return self.future.result(timeout=timeout)

    def cancel(self) -> bool:
        self.cancelled = self.future.cancel()
        return self.cancelled


class _Executor:
    def __init__(self, future: Future[TurnResult]) -> None:
        self.future = future
        self.calls: list[tuple[str, Any, Any]] = []
        self.auxiliary = _Auxiliary(future)

    def start_auxiliary(self, agent_id: str, session: Any, request: Any) -> _Auxiliary:
        self.calls.append((agent_id, session, request))
        return self.auxiliary


class _Directory:
    def __init__(self) -> None:
        self.session = SimpleNamespace(ref="subagent")
        self.refs: list[Any] = []

    def get(self, ref: Any) -> object:
        self.refs.append(ref)
        return object()

    def open(self, ref: Any) -> object:
        self.refs.append(ref)
        return self.session


def _result(text: str = "done") -> TurnResult:
    return TurnResult(
        session_id="subagent",
        turn_id="turn-1",
        messages=(Message(message_id="m1", role="assistant", content=text),),
    )


def test_foreground_submits_typed_request_to_executor(tmp_path: Path) -> None:
    future: Future[TurnResult] = Future()
    future.set_result(_result())
    executor = _Executor(future)
    runner = RuntimeRunner(directory=_Directory(), executor=executor)  # type: ignore[arg-type]

    handle = runner.start_foreground(
        agent_session_id="subagent",
        parent_session_id="parent",
        prompt="inspect",
        workspace_root=tmp_path,
        llm_session_id="parent",
        model="test:model",
    )

    assert handle.result(timeout=1).messages[-1].content == "done"
    _agent_id, _session, request = executor.calls[0]
    assert request.parts == ({"type": "text", "text": "inspect"},)
    assert request.llm_session_id == "parent"
    assert request.model == "test:model"


def test_background_completion_uses_callback(tmp_path: Path) -> None:
    future: Future[TurnResult] = Future()
    executor = _Executor(future)
    runner = RuntimeRunner(directory=_Directory(), executor=executor)  # type: ignore[arg-type]
    done = threading.Event()
    observed: dict[str, Any] = {}

    runner.start(
        agent_session_id="subagent",
        parent_session_id="parent",
        prompt="inspect",
        workspace_root=tmp_path,
        on_complete=lambda **kwargs: (observed.update(kwargs), done.set()),
        on_fail=lambda **kwargs: None,
        on_kill=lambda **kwargs: None,
    )
    future.set_result(_result("findings"))

    assert done.wait(timeout=1)
    assert observed["result_text"] == "findings"


def test_stop_cancels_typed_auxiliary_and_reports_kill(tmp_path: Path) -> None:
    future: Future[TurnResult] = Future()
    executor = _Executor(future)
    runner = RuntimeRunner(directory=_Directory(), executor=executor)  # type: ignore[arg-type]
    killed = threading.Event()

    handle = runner.start(
        agent_session_id="subagent",
        parent_session_id="parent",
        prompt="inspect",
        workspace_root=tmp_path,
        on_complete=lambda **kwargs: None,
        on_fail=lambda **kwargs: None,
        on_kill=lambda **kwargs: killed.set(),
    )
    handle.stop()

    assert executor.auxiliary.cancelled is True
    assert killed.wait(timeout=1)


def test_live_follow_up_is_queued_on_turn_controller(tmp_path: Path) -> None:
    future: Future[TurnResult] = Future()
    executor = _Executor(future)
    runner = RuntimeRunner(directory=_Directory(), executor=executor)  # type: ignore[arg-type]
    handle = runner.start_foreground(
        agent_session_id="subagent",
        parent_session_id="parent",
        prompt="inspect",
        workspace_root=tmp_path,
    )

    assert handle.send_message("also inspect tests") is True
    request = executor.calls[0][2]
    assert [item.message.content for item in request.controller.drain_pending()] == [
        "also inspect tests"
    ]
    future.cancel()
