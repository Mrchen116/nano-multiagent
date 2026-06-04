"""Red tests for feat-394-M7 R5: _AtSchedule expired-at-on-restart must not fire.

R5-4 root cause: when gateway restarts after a cron 'at' job's due time has passed
but last_due_at was not persisted (due to prior crash), the scheduler sees
last_due_at=None and now >= due_at, and triggers the job. This "expired at" behavior
contradicts openclaw computeNextRunAtMs semantics ("returns undefined when atMs <= nowMs").

Fix: _AtSchedule must NOT trigger when the at time is already past and last_due_at is None,
because the gateway wasn't running when the window opened (missed window = expired).

Note: this means at jobs can ONLY fire if the scheduler ticks at or after the due_at time
without a restart in between. If the gateway restarts and the at time has already passed,
the job is treated as expired (per openclaw semantics).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


def _make_at_schedule(due_at: datetime):
    from personal_assistant.scheduler.cron_scheduler import _AtSchedule  # noqa: PLC2701

    return _AtSchedule(due_at=due_at)


def test_at_schedule_fires_when_due_now() -> None:
    """_AtSchedule must fire when now == due_at and last_due_at is None (first-time trigger).

    This is the normal case: gateway is live and scheduler ticks at the due time.
    """
    due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    schedule = _make_at_schedule(due)

    # now is exactly at due_at → should fire
    times = schedule.due_times_up_to(now=due, last_due_at=None)
    assert times == [due], "at job must fire when now == due_at and not yet run"


def test_at_schedule_fires_when_due_time_just_passed() -> None:
    """_AtSchedule must fire when now is slightly past due_at (normal tick latency).

    The grace period allows up to 60s of latency without treating the job as expired.
    """
    due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    schedule = _make_at_schedule(due)

    now_within_grace = due + timedelta(seconds=3)
    times = schedule.due_times_up_to(now=now_within_grace, last_due_at=None)
    assert times == [due], (
        "at job must still fire when within grace period (3s < 60s); "
        "grace period allows normal scheduler latency"
    )


def test_at_schedule_does_not_refire_when_already_run() -> None:
    """_AtSchedule must not fire again if last_due_at >= due_at (already executed)."""
    due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    schedule = _make_at_schedule(due)

    already_ran_at = due
    now_later = due + timedelta(hours=7)
    times = schedule.due_times_up_to(now=now_later, last_due_at=already_ran_at)
    assert times == [], "at job must not refire after it has been executed"


def test_at_schedule_does_not_fire_when_future() -> None:
    """_AtSchedule must not fire when now < due_at (not yet time)."""
    due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    schedule = _make_at_schedule(due)

    now_before = due - timedelta(minutes=5)
    times = schedule.due_times_up_to(now=now_before, last_due_at=None)
    assert times == [], "at job must not fire before due_at"


def test_at_schedule_expired_means_no_fire_on_restart() -> None:
    """When gateway restarts and at time has passed (by hours), job must not fire.

    R5-4 scenario: job created with at=12:00Z, gateway crashes at 11:59Z,
    restarts at 19:00Z. last_due_at=None (never ran). Without the fix, job fires.
    With the fix (expired at = don't fire), job is silently skipped.
    """
    due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
    schedule = _make_at_schedule(due)

    # Gateway restarted 7 hours after due time; state has no record of the job running
    now_after_restart = due + timedelta(hours=7)
    times = schedule.due_times_up_to(now=now_after_restart, last_due_at=None)
    assert times == [], (
        "R5-4: at job expired while gateway was offline must NOT trigger on restart. "
        "Missed window = expired; user must create a new at job with a future time."
    )
