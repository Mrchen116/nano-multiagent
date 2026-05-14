"""Heartbeat scheduling engine for the personal assistant gateway."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from personal_assistant.client.kernel_api_client import KernelApiClient
from personal_assistant.config.local_store import AgentWorkspaceConfig

_INTERVAL_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_SCHEDULE_PREFIXES = ("interval:", "every:", "cron:", "at:")
_WEEKDAY_NAME_TO_CRON = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


@dataclass(frozen=True, slots=True)
class HeartbeatRunRecord:
    """Describe one heartbeat run submitted to the kernel.

    Args:
        agent_id: Agent workspace whose heartbeat became due.
        due_at: Canonical due instant being executed or caught up.
        run_id: Kernel async run identifier returned by submission.
        session_id: Kernel session created for the heartbeat execution.
    """

    agent_id: str
    due_at: datetime
    run_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class HeartbeatTickSummary:
    """Describe the observable result of one scheduler tick.

    Args:
        triggered_runs: Runs that were submitted during this tick, ordered by due time.
        skipped_agents: Agents whose HEARTBEAT.md had no actionable task.
    """

    triggered_runs: tuple[HeartbeatRunRecord, ...]
    skipped_agents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _AgentState:
    last_due_at: str | None = None


@dataclass(frozen=True, slots=True)
class _SchedulerState:
    agents: dict[str, _AgentState] = field(default_factory=dict)


class HeartbeatSchedulerStateStore:
    """Persist scheduler catch-up state on local disk.

    Args:
        state_path: JSON file used to persist the latest executed due timestamp per agent.

    Side Effects:
        Reads and writes one JSON file below the gateway-controlled filesystem.
    """

    def __init__(self, state_path: str | Path) -> None:
        self._state_path = Path(state_path).expanduser().resolve()

    def load(self) -> _SchedulerState:
        """Load persisted scheduler state.

        Returns:
            Empty state when the file does not exist yet; otherwise the decoded per-agent map.
        """

        if not self._state_path.exists():
            return _SchedulerState()
        raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        agents_payload = raw.get("agents", {}) if isinstance(raw, dict) else {}
        if not isinstance(agents_payload, dict):
            return _SchedulerState()
        agents: dict[str, _AgentState] = {}
        for agent_id, payload in agents_payload.items():
            if not isinstance(agent_id, str) or not isinstance(payload, dict):
                continue
            last_due_at = payload.get("last_due_at")
            if last_due_at is not None and not isinstance(last_due_at, str):
                continue
            agents[agent_id] = _AgentState(last_due_at=last_due_at)
        return _SchedulerState(agents=agents)

    def save(self, state: _SchedulerState) -> None:
        """Persist the given scheduler state atomically enough for local single-process use."""

        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


class _KernelClientLike(Protocol):
    def create_session(self, *, workspace_root: str, product_id: str, title: str | None = None) -> dict[str, object]: ...

    def submit_message(self, *, session_id: str, texts: list[str]) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class _HeartbeatSpec:
    schedule: "_Schedule"
    instructions: str


class HeartbeatScheduler:
    """Evaluate HEARTBEAT.md files and submit due runs to the local kernel.

    Args:
        agents: Managed agent workspaces whose HEARTBEAT.md files should be evaluated.
        kernel_client: HTTP boundary used to create independent heartbeat sessions.
        state_store: Persistence for last executed due timestamps so restart catch-up works.

    Notes:
        The scheduler stays intentionally quiet when HEARTBEAT.md has no actionable body.
        Each due heartbeat creates a fresh kernel session, matching the spec requirement that
        heartbeat execution is independent from normal chat sessions.
    """

    def __init__(
        self,
        *,
        agents: tuple[AgentWorkspaceConfig, ...],
        kernel_client: KernelApiClient | _KernelClientLike,
        state_store: HeartbeatSchedulerStateStore,
    ) -> None:
        self._agents = agents
        self._kernel_client = kernel_client
        self._state_store = state_store

    def tick(self, *, now: datetime | None = None) -> HeartbeatTickSummary:
        """Run one scheduler evaluation pass.

        Args:
            now: Current time used for due calculations. Naive datetimes are treated as UTC.

        Returns:
            Summary of submitted runs and quiet skips observed during this tick.

        Raises:
            ValueError: When a HEARTBEAT.md file declares invalid or conflicting schedule modes.
            RuntimeError: When the kernel returns malformed session or run identifiers.
        """

        current_time = _normalize_datetime(now or datetime.now(tz=UTC))
        state = self._state_store.load()
        state_agents = dict(state.agents)
        triggered_runs: list[HeartbeatRunRecord] = []
        skipped_agents: list[str] = []

        for agent in self._agents:
            heartbeat_path = agent.workspace_root / "HEARTBEAT.md"
            spec = _load_heartbeat_spec(heartbeat_path)
            if spec is None:
                skipped_agents.append(agent.agent_id)
                continue
            agent_state = state_agents.get(agent.agent_id, _AgentState())
            due_times = spec.schedule.due_times_up_to(now=current_time, last_due_at=_parse_optional_datetime(agent_state.last_due_at))
            if not due_times:
                continue
            for due_at in due_times:
                triggered_runs.append(self._submit_run(agent=agent, due_at=due_at, instructions=spec.instructions))
                state_agents[agent.agent_id] = _AgentState(last_due_at=due_at.isoformat())

        self._state_store.save(_SchedulerState(agents=state_agents))
        return HeartbeatTickSummary(triggered_runs=tuple(triggered_runs), skipped_agents=tuple(skipped_agents))

    def _submit_run(self, *, agent: AgentWorkspaceConfig, due_at: datetime, instructions: str) -> HeartbeatRunRecord:
        session_payload = self._kernel_client.create_session(
            workspace_root=str(agent.workspace_root),
            product_id="personal_assistant",
            title=agent.title,
        )
        session_id = str(session_payload.get("session_id", "")).strip()
        if not session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        message = _build_heartbeat_message(agent_id=agent.agent_id, due_at=due_at, instructions=instructions)
        # origin=heartbeat ensures auto_mode_gate detects unattended context and
        # does not park the run waiting for user permission that will never arrive.
        run_payload = self._kernel_client.submit_message(
            session_id=session_id, texts=[message], origin="heartbeat"
        )
        run_id = str(run_payload.get("run_id", "")).strip()
        if not run_id:
            raise RuntimeError("heartbeat submission did not return run_id")
        return HeartbeatRunRecord(agent_id=agent.agent_id, due_at=due_at, run_id=run_id, session_id=session_id)


class _Schedule(Protocol):
    def due_times_up_to(self, *, now: datetime, last_due_at: datetime | None) -> list[datetime]: ...


@dataclass(frozen=True, slots=True)
class _AtSchedule:
    due_at: datetime

    def due_times_up_to(self, *, now: datetime, last_due_at: datetime | None) -> list[datetime]:
        if now < self.due_at:
            return []
        if last_due_at is not None and last_due_at >= self.due_at:
            return []
        return [self.due_at]


@dataclass(frozen=True, slots=True)
class _IntervalSchedule:
    interval: timedelta

    def due_times_up_to(self, *, now: datetime, last_due_at: datetime | None) -> list[datetime]:
        if last_due_at is None:
            return [_floor_datetime(now, self.interval)]
        due_times: list[datetime] = []
        cursor = last_due_at + self.interval
        while cursor <= now:
            due_times.append(cursor)
            cursor += self.interval
        return due_times


@dataclass(frozen=True, slots=True)
class _CronSchedule:
    minute_values: tuple[int, ...]
    hour_values: tuple[int, ...]
    day_values: tuple[int, ...]
    month_values: tuple[int, ...]
    weekday_values: tuple[int, ...]

    def due_times_up_to(self, *, now: datetime, last_due_at: datetime | None) -> list[datetime]:
        current = now.replace(second=0, microsecond=0)
        if last_due_at is None:
            candidates = [current] if self._matches(current) else []
            return candidates
        due_times: list[datetime] = []
        cursor = (last_due_at + timedelta(minutes=1)).replace(second=0, microsecond=0)
        while cursor <= current:
            if self._matches(cursor):
                due_times.append(cursor)
            cursor += timedelta(minutes=1)
        return due_times

    def _matches(self, candidate: datetime) -> bool:
        cron_weekday = (candidate.weekday() + 1) % 7
        return (
            candidate.minute in self.minute_values
            and candidate.hour in self.hour_values
            and candidate.day in self.day_values
            and candidate.month in self.month_values
            and cron_weekday in self.weekday_values
        )


def _load_heartbeat_spec(path: Path) -> _HeartbeatSpec | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return None

    schedule_entries: list[tuple[str, str]] = []
    instruction_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith("#") or lowered.startswith("<!--") and lowered.endswith("-->"):
            continue
        matched_prefix = next((prefix for prefix in _SCHEDULE_PREFIXES if lowered.startswith(prefix)), None)
        if matched_prefix is not None:
            schedule_entries.append((matched_prefix[:-1], line.split(":", 1)[1].strip()))
            continue
        if not line:
            continue
        if line in {"---", "***"}:
            continue
        instruction_lines.append(line)

    if not instruction_lines:
        return None
    if len(schedule_entries) != 1:
        raise ValueError("HEARTBEAT.md must declare exactly one schedule mode")
    schedule_kind, schedule_value = schedule_entries[0]
    return _HeartbeatSpec(schedule=_parse_schedule(schedule_kind, schedule_value), instructions="\n".join(instruction_lines))


def _parse_schedule(kind: str, raw_value: str) -> _Schedule:
    if kind in {"interval", "every"}:
        return _IntervalSchedule(interval=_parse_interval(raw_value))
    if kind == "at":
        return _AtSchedule(due_at=_normalize_datetime(datetime.fromisoformat(raw_value)))
    if kind == "cron":
        return _parse_cron(raw_value)
    raise ValueError(f"unsupported heartbeat schedule mode: {kind}")


def _parse_interval(raw_value: str) -> timedelta:
    match = _INTERVAL_PATTERN.match(raw_value)
    if match is None:
        raise ValueError(f"invalid interval schedule: {raw_value}")
    value = int(match.group(1))
    unit = match.group(2).lower()
    if value <= 0:
        raise ValueError("interval must be > 0")
    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    raise ValueError(f"unsupported interval unit: {unit}")


def _parse_cron(raw_value: str) -> _CronSchedule:
    fields = raw_value.split()
    if len(fields) != 5:
        raise ValueError("cron schedule must contain five fields")
    minute, hour, day, month, weekday = fields
    return _CronSchedule(
        minute_values=_parse_cron_field(minute, minimum=0, maximum=59),
        hour_values=_parse_cron_field(hour, minimum=0, maximum=23),
        day_values=_parse_cron_field(day, minimum=1, maximum=31),
        month_values=_parse_cron_field(month, minimum=1, maximum=12),
        weekday_values=_parse_cron_field(weekday, minimum=0, maximum=6, allow_names=True),
    )


def _parse_cron_field(raw_value: str, *, minimum: int, maximum: int, allow_names: bool = False) -> tuple[int, ...]:
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
            values.update(number for number in range(start, end + 1) if (number - start) % step == 0)
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


def _parse_cron_number(raw_value: str, *, allow_names: bool) -> int:
    if allow_names and raw_value in _WEEKDAY_NAME_TO_CRON:
        return _WEEKDAY_NAME_TO_CRON[raw_value]
    value = int(raw_value)
    if allow_names and value == 7:
        return 0
    return value


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _normalize_datetime(datetime.fromisoformat(value))


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _floor_datetime(value: datetime, interval: timedelta) -> datetime:
    seconds = int(interval.total_seconds())
    if seconds <= 0:
        raise ValueError("interval must be positive")
    timestamp = int(value.timestamp())
    floored = timestamp - (timestamp % seconds)
    return datetime.fromtimestamp(floored, tz=UTC)


def _build_heartbeat_message(*, agent_id: str, due_at: datetime, instructions: str) -> str:
    return (
        "Heartbeat scheduler trigger.\n\n"
        f"Agent: {agent_id}\n"
        f"Due at: {due_at.isoformat()}\n\n"
        "Read the workspace HEARTBEAT.md intent below, perform only valid actionable tasks, and stay quiet if there is nothing useful to report.\n\n"
        f"{instructions}"
    )
