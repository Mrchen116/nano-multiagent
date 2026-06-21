"""Tests for ForegroundExecutionRegistry (bugfix-417-M7 / decision 12).

The foreground bash path no longer parasites on BackgroundTaskRegistry. This narrow
registry holds only what a foreground tool genuinely needs: an in-flight killpg
stopper handle keyed by session, so interrupt/cancel can reap the run-blocking
subprocess tree without the foreground command ever entering the background-task
state machine (and thus never emitting a <task-notification>).
"""

from __future__ import annotations

from agent.core.background_tasks.foreground_registry import ForegroundExecutionRegistry


class _RecordingStopper:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def test_stop_for_session_stops_registered_foreground_stopper() -> None:
    reg = ForegroundExecutionRegistry()
    stopper = _RecordingStopper()
    reg.register(session_id="s1", stopper=stopper)

    assert reg.stop_for_session("s1") is True
    assert stopper.stopped is True


def test_stop_for_session_scopes_to_session() -> None:
    """A foreground tool in another session must not be stopped."""
    reg = ForegroundExecutionRegistry()
    other = _RecordingStopper()
    reg.register(session_id="other", stopper=other)

    assert reg.stop_for_session("s1") is False
    assert other.stopped is False


def test_stop_for_session_no_registration_returns_false() -> None:
    reg = ForegroundExecutionRegistry()
    assert reg.stop_for_session("s1") is False


def test_unregister_removes_stopper_so_later_stop_is_noop() -> None:
    """After unregister (e.g. command completed, or handed off to background) a
    later /stop on that session must not fire a stale stopper."""
    reg = ForegroundExecutionRegistry()
    stopper = _RecordingStopper()
    reg.register(session_id="s1", stopper=stopper)
    reg.unregister(session_id="s1", stopper=stopper)

    assert reg.stop_for_session("s1") is False
    assert stopper.stopped is False


def test_concurrent_foreground_tools_in_same_session_all_stopped() -> None:
    """A session could (in principle) have more than one in-flight foreground tool;
    stop_for_session must reap every one and report True."""
    reg = ForegroundExecutionRegistry()
    a = _RecordingStopper()
    b = _RecordingStopper()
    reg.register(session_id="s1", stopper=a)
    reg.register(session_id="s1", stopper=b)

    assert reg.stop_for_session("s1") is True
    assert a.stopped is True
    assert b.stopped is True


def test_unregister_one_of_several_leaves_others_targetable() -> None:
    reg = ForegroundExecutionRegistry()
    a = _RecordingStopper()
    b = _RecordingStopper()
    reg.register(session_id="s1", stopper=a)
    reg.register(session_id="s1", stopper=b)
    reg.unregister(session_id="s1", stopper=a)

    assert reg.stop_for_session("s1") is True
    assert a.stopped is False
    assert b.stopped is True


def test_unregister_unknown_session_is_safe() -> None:
    reg = ForegroundExecutionRegistry()
    stopper = _RecordingStopper()
    # No raise even when nothing was registered.
    reg.unregister(session_id="missing", stopper=stopper)
    assert reg.stop_for_session("missing") is False
