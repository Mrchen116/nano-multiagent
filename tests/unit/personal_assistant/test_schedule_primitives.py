"""Canonical unit tests for shared schedule primitives.

_AtSchedule, _IntervalSchedule, _CronSchedule are the unique authority for
at/interval/cron scheduling semantics (TESTING_GUIDE §4: one behaviour, one layer).
Higher-layer scheduler tests may keep a single smoke per type; they must NOT
re-assert the timing logic proven here.

Provenance: feat-394-W1 dedup — openclaw/src/cron/schedule.ts:computeNextRunAtMs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from personal_assistant.scheduler._schedule_primitives import (
    _AtSchedule,
    _CronSchedule,
    _IntervalSchedule,
)


# ---------------------------------------------------------------------------
# _AtSchedule
# ---------------------------------------------------------------------------


class TestAtSchedule:
    def test_fires_when_due_now(self) -> None:
        """Fires when now == due_at and job has never run (first-time trigger)."""
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        times = _AtSchedule(due_at=due).due_times_up_to(now=due, last_due_at=None)
        assert times == [due]

    def test_fires_within_60s_grace(self) -> None:
        """Fires when now is up to 60s past due_at — covers normal polling latency."""
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        now = due + timedelta(seconds=3)
        times = _AtSchedule(due_at=due).due_times_up_to(now=now, last_due_at=None)
        assert times == [due]

    def test_no_refire_after_run(self) -> None:
        """Does not fire again when last_due_at >= due_at (already executed)."""
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        later = due + timedelta(hours=7)
        times = _AtSchedule(due_at=due).due_times_up_to(now=later, last_due_at=due)
        assert times == []

    def test_no_fire_when_future(self) -> None:
        """Does not fire when now < due_at (not yet time)."""
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        now = due - timedelta(minutes=5)
        times = _AtSchedule(due_at=due).due_times_up_to(now=now, last_due_at=None)
        assert times == []

    def test_cron_mode_expired_no_fire_on_restart(self) -> None:
        """check_expiry=True: past due_at with no run record older than 60s grace → skip.

        R5-4 scenario: job due at 12:00, gateway offline, restarts at 19:00.
        last_due_at=None (never ran). Cron semantics: missed window = expired, do not fire.
        """
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        now = due + timedelta(hours=7)
        times = _AtSchedule(due_at=due, check_expiry=True).due_times_up_to(
            now=now, last_due_at=None
        )
        assert times == []

    def test_heartbeat_mode_fires_even_when_expired(self) -> None:
        """check_expiry=False: past due_at with no run record fires regardless of gap.

        Heartbeat "at:" lines use this so a one-off task fires even after a gateway
        restart gap longer than the 60s grace (feat-394-M7 R5-4 fix is cron-only).
        """
        due = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        now = due + timedelta(hours=7)
        times = _AtSchedule(due_at=due, check_expiry=False).due_times_up_to(
            now=now, last_due_at=None
        )
        assert times == [due]


# ---------------------------------------------------------------------------
# _IntervalSchedule
# ---------------------------------------------------------------------------


class TestIntervalSchedule:
    def test_first_tick_fires_immediately(self) -> None:
        """First tick (last_due_at=None) fires at floor(now, interval)."""
        interval = timedelta(seconds=60)
        now = datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)  # 10:00:30
        times = _IntervalSchedule(interval=interval).due_times_up_to(
            now=now, last_due_at=None
        )
        assert len(times) == 1
        # floor(10:00:30, 60s) = 10:00:00
        assert times[0].second == 0

    def test_fires_on_interval_with_overhead(self) -> None:
        """elapsed = interval + 2s still triggers (floor semantics, not ceil).

        ceil(17/15)=2 → next=last+30s > now+17s → NOT triggered (the old bug).
        floor(17/15)=1 → next=last+15s ≤ now+17s → triggered (correct).
        """
        interval = timedelta(seconds=15)
        last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = last + timedelta(seconds=17)  # 17s > interval=15s
        times = _IntervalSchedule(interval=interval).due_times_up_to(
            now=now, last_due_at=last
        )
        assert len(times) == 1
        assert times[0] == last + interval  # next slot = last + 15s

    def test_large_gap_fires_only_once(self) -> None:
        """5 missed intervals produce exactly 1 due time — no backfill flood.

        floor(150/30)=5 → next=last+150s=now → fires once (not 5 times).
        """
        interval = timedelta(seconds=30)
        last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = last + timedelta(seconds=150)  # 5 × interval
        times = _IntervalSchedule(interval=interval).due_times_up_to(
            now=now, last_due_at=last
        )
        assert len(times) == 1

    def test_not_due_before_interval(self) -> None:
        """Does not fire when elapsed < interval (interval not yet reached)."""
        interval = timedelta(seconds=60)
        last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = last + timedelta(seconds=30)  # only half the interval has passed
        times = _IntervalSchedule(interval=interval).due_times_up_to(
            now=now, last_due_at=last
        )
        assert times == []


# ---------------------------------------------------------------------------
# _CronSchedule
# ---------------------------------------------------------------------------


def _every_minute_cron(*, tz: str | None = None) -> _CronSchedule:
    """Return a '* * * * *' schedule — fires every minute."""
    return _CronSchedule(
        minute_values=tuple(range(0, 60)),
        hour_values=tuple(range(0, 24)),
        day_values=tuple(range(1, 32)),
        month_values=tuple(range(1, 13)),
        weekday_values=tuple(range(0, 7)),
        tz=tz,
    )


def _daily_at_9am_cron(*, tz: str | None = None) -> _CronSchedule:
    """Return a '0 9 * * *' schedule — fires at 09:00 every day."""
    return _CronSchedule(
        minute_values=(0,),
        hour_values=(9,),
        day_values=tuple(range(1, 32)),
        month_values=tuple(range(1, 13)),
        weekday_values=tuple(range(0, 7)),
        tz=tz,
    )


class TestCronSchedule:
    def test_fires_on_matching_minute(self) -> None:
        """Fires exactly once when the current minute matches the expression."""
        sched = _daily_at_9am_cron()
        now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        times = sched.due_times_up_to(now=now, last_due_at=None)
        assert len(times) == 1
        assert times[0] == now.replace(second=0, microsecond=0)

    def test_no_refire_same_minute(self) -> None:
        """Does not fire a second time within the same clock minute."""
        sched = _daily_at_9am_cron()
        fired_at = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        # Tick 30s later, still minute 9:00
        now = fired_at + timedelta(seconds=30)
        times = sched.due_times_up_to(now=now, last_due_at=fired_at)
        assert times == []

    def test_no_backfill_missed_minutes(self) -> None:
        """After a gap, only the current minute is checked — missed minutes are not replayed.

        openclaw semantics: cron checks whether the present tick matches; it does not
        scan backward from last_due_at to enumerate all skipped slots.
        """
        sched = _daily_at_9am_cron()
        # Fired yesterday at 09:00; now it's today at 09:00 (24h gap).
        last = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC)
        times = sched.due_times_up_to(now=now, last_due_at=last)
        # Fires for today's 09:00 — not a flood of missed slots.
        assert len(times) == 1

    def test_respects_tz(self) -> None:
        """W7: same UTC instant matches 09:00 Shanghai time but not 09:00 UTC.

        Asia/Shanghai is UTC+8, so 01:00 UTC == 09:00 CST. A "0 9 * * *" schedule
        with tz="Asia/Shanghai" must fire at 01:00 UTC, not at 09:00 UTC.
        """
        utc_instant_matches_cst_9am = datetime(2026, 1, 1, 1, 0, 0, tzinfo=UTC)  # 09:00 CST
        utc_instant_at_utc_9am = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)  # 17:00 CST

        sched_cst = _daily_at_9am_cron(tz="Asia/Shanghai")

        # Tick at 01:00 UTC → 09:00 CST → should fire
        times_cst_match = sched_cst.due_times_up_to(
            now=utc_instant_matches_cst_9am, last_due_at=None
        )
        assert len(times_cst_match) == 1, "should fire at UTC 01:00 (= CST 09:00)"

        # Tick at 09:00 UTC → 17:00 CST → should NOT fire
        times_cst_no_match = sched_cst.due_times_up_to(
            now=utc_instant_at_utc_9am, last_due_at=None
        )
        assert times_cst_no_match == [], "must not fire at UTC 09:00 (= CST 17:00)"
