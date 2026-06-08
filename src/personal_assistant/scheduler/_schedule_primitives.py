"""Shared schedule primitives for heartbeat and cron schedulers.

W1 dedup: these types and helpers were duplicated in heartbeat_scheduler.py and
cron_scheduler.py.  Both now import from here.

All schedule types implement the _Schedule protocol and use non-backfill semantics
(openclaw computeNextRunAtMs): a restart never replays missed ticks; only the next
future slot fires.  feat-394 decision 4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_INTERVAL_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)

# Maps lowercase weekday abbreviations to cron weekday numbers (Sun=0 ... Sat=6).
_WEEKDAY_NAME_TO_CRON: dict[str, int] = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

# Maximum latency between an 'at' job's due time and a tick before it is treated as expired.
# 60 seconds covers any reasonable polling interval; anything longer means the gateway
# missed the window (was offline or heavily loaded) and the job should not fire.
# feat-394-M7 R5-4 fix.
_AT_SCHEDULE_EXPIRED_GRACE: timedelta = timedelta(seconds=60)


class _Schedule(Protocol):
    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]: ...


@dataclass(frozen=True, slots=True)
class _AtSchedule:
    """One-shot schedule: fires once when time arrives, never after already executed.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "at" branch —
    returns undefined when atMs <= nowMs (meaning job is not future, skip).
    feat-394 decision 4: expired 'at' jobs are not re-run after gateway restart.

    Attributes:
        due_at: The single instant when this schedule fires.
        check_expiry: When True (cron path), a past due_at with no run record is treated
            as expired if it fell outside _AT_SCHEDULE_EXPIRED_GRACE.  The heartbeat
            path keeps this False so a one-off HEARTBEAT.md "at:" line still fires even
            if the gateway was offline for a while (feat-394-M7 R5-4 fix was cron-only).
    """

    due_at: datetime
    # False = heartbeat semantics (fire even if at-time is far past and no run recorded);
    # True = cron semantics (feat-394-M7 R5-4: treat old at-jobs as expired after 60s gap).
    # Default True preserves the expiry behavior that cron_scheduler tests expect when
    # constructing _AtSchedule without an explicit flag.
    check_expiry: bool = True

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        if now < self.due_at:
            return []
        if last_due_at is not None and last_due_at >= self.due_at:
            return []
        # feat-394-M7 R5-4 fix (cron path): reject expired at jobs.
        # If the at time passed more than the grace period ago and we have no run record,
        # the gateway missed the window (e.g. was offline).  Do not fire retroactively.
        # Heartbeat "at:" lines intentionally skip this check so they fire even after a gap.
        if (
            self.check_expiry
            and last_due_at is None
            and (now - self.due_at) > _AT_SCHEDULE_EXPIRED_GRACE
        ):
            return []
        return [self.due_at]


@dataclass(frozen=True, slots=True)
class _IntervalSchedule:
    """Recurring interval schedule with no backfill.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "every" branch —
    original used ceil(elapsed / everyMs); this implementation uses floor to allow
    LLM execution overhead without skipping subsequent ticks.  The semantics match
    openclaw's intent (next aligned slot at-or-before now fires), adapted for the
    reality that elapsed is rarely a perfect multiple of interval.
    feat-394 decision 4: only ONE run emitted per tick regardless of missed intervals.
    feat-394-M8 R6-1 fix: ceil → floor so elapsed=interval+overhead still triggers.
    """

    interval: timedelta

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        # First-ever tick (last_due_at is None): trigger immediately at floor(now, interval).
        if last_due_at is None:
            return [_floor_datetime(now, self.interval)]
        elapsed = now - last_due_at
        if elapsed <= timedelta(0):
            return []
        interval_secs = int(self.interval.total_seconds())
        elapsed_secs = int(elapsed.total_seconds())
        # floor(elapsed / interval): gives the most-recent aligned slot at-or-before now.
        # ceil would give the next future slot, causing a skip when elapsed is not a perfect
        # multiple (e.g. elapsed=32s, interval=30s → ceil=2 → next=last+60s > now → NOT
        # triggered (bug)).  floor fix: 32/30=1 → next=last+30s ≤ now → triggered.
        # Large-gap invariant: floor(150/30)=5 → next=last+150s=now → fires exactly once
        # (due_times_up_to returns at most one datetime per call, no backfill flood).
        steps = max(1, elapsed_secs // interval_secs)
        next_due_at = last_due_at + self.interval * steps
        if next_due_at > now:
            return []
        return [next_due_at]


@dataclass(frozen=True, slots=True)
class _CronSchedule:
    """Cron-expression schedule; fires at most once per matching minute, no backfill.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "cron" branch —
    openclaw checks now >= next_run_at per tick then immediately advances to the next
    future match.  Net effect: only the current minute fires if it matches AND hasn't
    already fired.  A restart never replays past matching minutes.
    feat-394 decision 4.

    Attributes:
        tz: IANA timezone name (e.g. "Asia/Shanghai") for evaluating cron fields.
            When None, evaluation falls back to UTC.  W7 fix.
    """

    minute_values: tuple[int, ...]
    hour_values: tuple[int, ...]
    day_values: tuple[int, ...]
    month_values: tuple[int, ...]
    weekday_values: tuple[int, ...]
    tz: str | None = None  # W7: per-job timezone; None → UTC

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        current = now.replace(second=0, microsecond=0)
        if not self._matches(current):
            return []
        if (
            last_due_at is not None
            and last_due_at.replace(second=0, microsecond=0) == current
        ):
            return []
        return [current]

    def _matches(self, candidate: datetime) -> bool:
        # W7: convert candidate to target timezone before comparing cron fields.
        # candidate is always UTC-aware; convert to local wall clock for the configured tz
        # so that "0 9 * * *" fires at 9am local time, not 9am UTC.
        if self.tz is not None:
            try:
                local = candidate.astimezone(ZoneInfo(self.tz))
            except ZoneInfoNotFoundError:
                # Unknown tz: fall back to UTC rather than silently misfiring.
                local = candidate
        else:
            local = candidate
        cron_weekday = (local.weekday() + 1) % 7
        return (
            local.minute in self.minute_values
            and local.hour in self.hour_values
            and local.day in self.day_values
            and local.month in self.month_values
            and cron_weekday in self.weekday_values
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_cron(raw_value: str, *, tz: str | None = None) -> _CronSchedule:
    """Parse a 5-field cron expression string into a _CronSchedule.

    Args:
        raw_value: Five-field cron expression ("minute hour day month weekday").
        tz: Optional IANA timezone for field evaluation (W7).

    Raises:
        ValueError: When the expression does not have exactly 5 fields.
    """
    parts = raw_value.split()
    if len(parts) != 5:
        raise ValueError(f"cron expression must have 5 fields: {raw_value!r}")
    minute, hour, day, month, weekday = parts
    return _CronSchedule(
        minute_values=_parse_cron_field(minute, minimum=0, maximum=59),
        hour_values=_parse_cron_field(hour, minimum=0, maximum=23),
        day_values=_parse_cron_field(day, minimum=1, maximum=31),
        month_values=_parse_cron_field(month, minimum=1, maximum=12),
        weekday_values=_parse_cron_field(
            weekday, minimum=0, maximum=6, allow_names=True
        ),
        tz=tz,
    )


def _parse_cron_field(
    raw_value: str,
    *,
    minimum: int,
    maximum: int,
    allow_names: bool = False,
) -> tuple[int, ...]:
    """Parse one cron field (e.g. "*/5", "1-5", "mon,fri") into sorted values.

    Raises:
        ValueError: When the field is syntactically invalid or produces no valid values.
    """
    values: set[int] = set()
    for part in raw_value.split(","):
        item = part.strip().lower()
        if not item:
            raise ValueError(f"invalid cron field: {raw_value}")
        if item == "*":
            values.update(range(minimum, maximum + 1))
            continue
        if "/" in item:
            base, step_text = item.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError(f"invalid cron step: {raw_value}")
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                start = _parse_cron_number(start_text, allow_names=allow_names)
                end = _parse_cron_number(end_text, allow_names=allow_names)
            else:
                start = _parse_cron_number(base, allow_names=allow_names)
                end = maximum
            values.update(
                number
                for number in range(start, end + 1)
                if (number - start) % step == 0
            )
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = _parse_cron_number(start_text, allow_names=allow_names)
            end = _parse_cron_number(end_text, allow_names=allow_names)
            values.update(range(start, end + 1))
            continue
        values.add(_parse_cron_number(item, allow_names=allow_names))

    filtered = tuple(sorted(value for value in values if minimum <= value <= maximum))
    if not filtered:
        raise ValueError(f"cron field has no valid values: {raw_value}")
    return filtered


def _parse_cron_number(raw_value: str, *, allow_names: bool = False) -> int:
    """Convert a cron field token to an integer.

    Handles weekday name aliases (sun, mon …) and the Sunday=7 alias.
    """
    text = raw_value.strip().lower()
    if allow_names and text in _WEEKDAY_NAME_TO_CRON:
        return _WEEKDAY_NAME_TO_CRON[text]
    value = int(text)
    # Cron Sunday alias: some tools use 7 for Sunday, map to 0.
    if allow_names and value == 7:
        return 0
    return value


def _normalize_datetime(value: datetime) -> datetime:
    """Return value as UTC-aware datetime; attach UTC if naive."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_optional_datetime(text: str | None) -> datetime | None:
    """Parse an optional ISO-8601 string to UTC datetime, or return None."""
    if text is None:
        return None
    return _normalize_datetime(datetime.fromisoformat(text))


def _floor_datetime(value: datetime, interval: timedelta) -> datetime:
    """Return the most-recent interval-aligned UTC datetime at-or-before value."""
    seconds = int(interval.total_seconds())
    if seconds <= 0:
        raise ValueError("interval must be positive")
    timestamp = int(value.timestamp())
    floored = timestamp - (timestamp % seconds)
    return datetime.fromtimestamp(floored, tz=UTC)
