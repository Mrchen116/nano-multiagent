import asyncio
import threading
from pathlib import Path

import pytest

from agent.core.runs.executor import (
    ExecutorClosedError,
    KernelExecutor,
    TargetCompletion,
)
from agent.core.session.types import TurnRequest
from agent.core.types import TurnResult


class _Session:
    def __init__(self, events: list[str], *, block: bool = False) -> None:
        self.ref = type(
            "_Ref", (), {"session_id": "sess_executor", "workspace_root": Path.cwd()}
        )()
        self._events = events
        self._block = block
        self.started = threading.Event()
        self.cleaned = threading.Event()

    async def submit_turn(self, request: TurnRequest) -> TurnResult:
        del request
        self._events.append("started")
        self.started.set()
        try:
            if self._block:
                await asyncio.Event().wait()
            return TurnResult(
                session_id=self.ref.session_id,
                turn_id="turn_executor",
                messages=(),
                completed=True,
                stop_reason="end_turn",
            )
        finally:
            self._events.append("cleaned")
            self.cleaned.set()


class _Sink:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.bound = threading.Event()
        self.completed = threading.Event()
        self.completion: TargetCompletion | None = None

    def bind_target(self, token) -> None:  # noqa: ANN001
        self.events.append("bound")
        self.bound.set()

    def complete(self, completion: TargetCompletion) -> None:
        self.events.append("completed")
        self.completion = completion
        self.completed.set()


def test_top_level_binds_token_before_carrier_starts() -> None:
    events: list[str] = []
    executor = KernelExecutor()
    sink = _Sink(events)
    session = _Session(events)

    executor.start_top_level(
        "run_1",
        session,
        TurnRequest(parts=({"type": "text", "text": "hello"},)),
        sink,
    )

    assert sink.completed.wait(timeout=1)
    assert events == ["bound", "started", "cleaned", "completed"]
    assert sink.completion is not None
    assert sink.completion.result is not None
    executor.shutdown()


def test_cancel_has_separate_cleanup_ack_and_same_executor_remains_usable() -> None:
    events: list[str] = []
    executor = KernelExecutor(cancel_grace_seconds=0)
    first_sink = _Sink(events)
    first = _Session(events, block=True)
    token = executor.start_top_level(
        "run_blocked",
        first,
        TurnRequest(parts=({"type": "text", "text": "block"},)),
        first_sink,
    )
    assert first.started.wait(timeout=1)

    assert executor.request_cancel(token) is True
    assert first_sink.completed.wait(timeout=1)
    assert first.cleaned.is_set()
    assert first_sink.completion is not None
    assert first_sink.completion.cancelled is True
    assert first_sink.completion.cleanup_ack is True

    second_sink = _Sink(events)
    executor.start_top_level(
        "run_after_cancel",
        _Session(events),
        TurnRequest(parts=({"type": "text", "text": "again"},)),
        second_sink,
    )
    assert second_sink.completed.wait(timeout=1)
    executor.shutdown()


def test_auxiliary_is_owned_through_shutdown_and_new_targets_are_rejected() -> None:
    executor = KernelExecutor(cancel_grace_seconds=0)
    session = _Session([], block=True)
    handle = executor.start_auxiliary(
        "aux_1",
        session,
        TurnRequest(parts=({"type": "text", "text": "background"},)),
    )
    assert session.started.wait(timeout=1)

    accepted = executor.begin_shutdown()
    executor.shutdown()

    assert accepted.top_level == ()
    assert len(accepted.auxiliary) == 1
    assert handle.cleanup_ack.wait(timeout=1)
    assert handle.cancelled is True
    assert executor.active_target_count == 0
    with pytest.raises(ExecutorClosedError):
        executor.start_auxiliary(
            "aux_late",
            _Session([]),
            TurnRequest(parts=({"type": "text", "text": "late"},)),
        )
