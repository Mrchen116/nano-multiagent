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


def test_force_cancel_bypasses_cooperative_grace() -> None:
    """A foreground stopper must not let the stopped tool close as success."""

    executor = KernelExecutor(cancel_grace_seconds=30)
    events: list[str] = []
    session = _Session(events, block=True)
    sink = _Sink(events)
    token = executor.start_top_level(
        "run-force",
        session,
        TurnRequest(parts=({"type": "text", "text": "hello"},)),
        sink,
    )
    assert session.started.wait(timeout=1)

    assert executor.request_cancel(token, force=True) is True

    assert sink.completed.wait(timeout=1)
    assert sink.completion is not None
    assert sink.completion.cancelled is True
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


def test_idle_admission_stays_busy_until_completion_settlement_finishes() -> None:
    settling = threading.Event()
    release = threading.Event()
    idle = threading.Event()

    class SettlingSink(_Sink):
        async def complete(self, completion):
            settling.set()
            assert await asyncio.to_thread(release.wait, 2)
            super().complete(completion)

    executor = KernelExecutor(on_session_idle=lambda session: idle.set())
    session = _Session([])
    request = TurnRequest(parts=({"type": "text", "text": "work"},))
    try:
        executor.start_top_level("initial", session, request, SettlingSink([]))
        assert settling.wait(1)
        assert (
            executor.start_top_level(
                "too-early", session, request, _Sink([]), only_if_idle=True
            )
            is None
        )
        release.set()
        assert idle.wait(1)
        accepted = _Sink([])
        assert (
            executor.start_top_level(
                "next", session, request, accepted, only_if_idle=True
            )
            is not None
        )
        assert accepted.completed.wait(1)
    finally:
        release.set()
        executor.shutdown()


@pytest.mark.parametrize("queued_kind", ["turn", "compact"])
def test_idle_admission_rejects_queued_carriers_before_they_start(queued_kind) -> None:
    blocked = threading.Event()
    release = threading.Event()

    class BlockingSession(_Session):
        async def submit_turn(self, request):
            if request.parts[0]["text"] == "hold-loop":
                blocked.set()
                assert release.wait(2)
            return await super().submit_turn(request)

        async def compact(self, **kwargs):
            return None

    executor = KernelExecutor()
    blocker = BlockingSession([])
    session = BlockingSession([])
    hold = TurnRequest(parts=({"type": "text", "text": "hold-loop"},))
    next_request = TurnRequest(parts=({"type": "text", "text": "queued"},))
    thread = None
    try:
        executor.start_top_level("block-owner-loop", blocker, hold, _Sink([]))
        assert blocked.wait(1)
        if queued_kind == "turn":
            executor.start_top_level("queued-turn", session, next_request, _Sink([]))
        else:

            def compact():
                asyncio.run(executor.compact(session))

            thread = threading.Thread(target=compact)
            thread.start()
            # Admission is synchronous before the lifecycle awaits its result.
            import time

            deadline = time.monotonic() + 1
            while executor.active_target_count < 2 and time.monotonic() < deadline:
                time.sleep(0.001)
            assert executor.active_target_count == 2
        assert (
            executor.start_top_level(
                "idle-attempt", session, next_request, _Sink([]), only_if_idle=True
            )
            is None
        )
    finally:
        release.set()
        if thread is not None:
            thread.join(2)
        executor.shutdown()
