"""Heartbeat scheduling engine for the personal assistant gateway."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

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
        stream_anchor: Event sequence number captured immediately before the run
            was submitted.  Used as ``after_sequence`` when streaming events for
            this run so the consumer skips replaying history from prior runs
            (perf: avoids O(history) scan on each tick).  0 = no anchor captured
            (legacy / test path) — stream from the beginning.
    """

    agent_id: str
    due_at: datetime
    run_id: str
    session_id: str
    stream_anchor: int = 0


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
    # feat-394 decision 3: per-task last_due_at for tasks: multi-sub-rhythm
    # Key = task name; value = ISO8601 UTC timestamp of last execution.
    per_task_last_due: dict[str, str] = field(default_factory=dict)


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
            # feat-394 decision 3: per-task last_due map (backward compatible — missing key → empty dict)
            raw_per_task = payload.get("per_task_last_due", {})
            per_task_last_due: dict[str, str] = (
                {k: v for k, v in raw_per_task.items() if isinstance(k, str) and isinstance(v, str)}
                if isinstance(raw_per_task, dict)
                else {}
            )
            agents[agent_id] = _AgentState(last_due_at=last_due_at, per_task_last_due=per_task_last_due)
        return _SchedulerState(agents=agents)

    def save(self, state: _SchedulerState) -> None:
        """Persist the given scheduler state atomically enough for local single-process use."""

        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8"
        )


class _KernelClientLike(Protocol):
    # create_session is async — the gateway runs an asyncio event loop and
    # run_until_complete on an already-running loop raises RuntimeError.
    async def create_session(
        self, *, workspace_root: str, product_id: str, title: str | None = None
    ) -> dict[str, object]: ...

    def submit_message(
        self, *, session_id: str, texts: list[str], workspace_root: str | None = None
    ) -> dict[str, object]: ...

    def current_event_sequence(self) -> int:
        """Return the current max published event sequence (0 when no events yet).

        Capturing this before submitting a run lets the consumer skip replaying
        history that predates the run (see HeartbeatRunRecord.stream_anchor).
        Optional: implementations may return 0 to fall back to full-history scan.
        """
        return 0


@dataclass(frozen=True, slots=True)
class _HeartbeatTask:
    """One sub-rhythm task entry from HEARTBEAT.md tasks: block.

    Provenance: openclaw/src/auto-reply/heartbeat.ts HeartbeatTask type (feat-394 decision 3).

    Args:
        name: Stable task name used as the per-task state key.
        interval: Human-readable interval string (e.g. "30m", "2h").
        prompt: Task-specific instruction text appended to the heartbeat message.
    """

    name: str
    interval: timedelta
    prompt: str


@dataclass(frozen=True, slots=True)
class _HeartbeatSpec:
    schedule: "_Schedule"
    instructions: str
    # feat-394 decision 3: multi-sub-rhythm tasks parsed from tasks: block.
    # When present, each task is evaluated independently with its own last_due_at.
    # When empty, the legacy single-schedule mode is used.
    tasks: tuple["_HeartbeatTask", ...] = ()


class HeartbeatScheduler:
    """Evaluate HEARTBEAT.md files and submit due runs to the local kernel.

    Args:
        agents: Managed agent workspaces whose HEARTBEAT.md files should be evaluated.
        kernel_client: HTTP boundary used to create independent heartbeat sessions.
        state_store: Persistence for last executed due timestamps so restart catch-up works.
        canonical_session_store: Optional shared mutable dict mapping agent_id to the
            kernel session_id of the (owner, agent) canonical direct chat.  When present
            and a session is found for the agent, heartbeat runs use that session instead
            of creating a fresh one (feat-394 decision 3: heartbeat runs in the canonical
            direct chat session, carrying user conversation context).  PollingHeartbeatRunner
            populates this dict after the first successful turn_start delivery.

    Notes:
        The scheduler stays intentionally quiet when HEARTBEAT.md has no actionable body.
        When canonical_session_store is populated, heartbeat reuses the canonical direct chat
        kernel session so the model has conversation context (like an openclaw "main-session turn").
        On first heartbeat (before any direct chat), a fresh session is created; the runner
        promotes it to canonical after the first delivery establishes the IM conversation.
    """

    def __init__(
        self,
        *,
        agents: tuple[AgentWorkspaceConfig, ...],
        kernel_client: _KernelClientLike,
        state_store: HeartbeatSchedulerStateStore,
        canonical_session_store: dict[str, str] | None = None,
    ) -> None:
        self._agents = agents
        self._kernel_client = kernel_client
        self._state_store = state_store
        # feat-394 decision 3: canonical direct chat kernel session per agent_id.
        # Populated by PollingHeartbeatRunner after first delivery; None key → fresh session.
        # Falls back to the legacy _heartbeat_sessions dict when canonical_session_store is None.
        self._canonical_session_store: dict[str, str] = (
            canonical_session_store if canonical_session_store is not None else {}
        )
        # Legacy fallback session store (for when canonical_session_store is not provided).
        # In feat-393 mode, one stable :heartbeat session per agent was used.
        # In feat-394 mode, canonical_session_store takes precedence.
        self._heartbeat_sessions: dict[str, str] = {}

    async def tick(self, *, now: datetime | None = None) -> HeartbeatTickSummary:
        """Run one scheduler evaluation pass.

        Args:
            now: Current time used for due calculations. Naive datetimes are treated as UTC.

        Returns:
            Summary of submitted runs and quiet skips observed during this tick.

        Raises:
            ValueError: When a HEARTBEAT.md file declares invalid or conflicting schedule modes.
            RuntimeError: When the kernel returns malformed session or run identifiers.

        Notes:
            async because create_session on the in-process Kernel SDK is a coroutine;
            run_until_complete on an already-running loop raises RuntimeError (refactor-387 M4 fix).
        """

        current_time = _normalize_datetime(now or datetime.now(tz=UTC))
        state = self._state_store.load()
        state_agents = dict(state.agents)
        triggered_runs: list[HeartbeatRunRecord] = []
        skipped_agents: list[str] = []

        for agent in self._agents:
            # feat-394 decision 5: per-agent heartbeat gate — skip without reading HEARTBEAT.md
            # when the agent's heartbeat_enabled flag is False (synced from IM via ConfigSyncNotifier).
            if not agent.heartbeat_enabled:
                skipped_agents.append(agent.agent_id)
                continue
            heartbeat_path = agent.workspace_root / "HEARTBEAT.md"
            spec = _load_heartbeat_spec(heartbeat_path)
            if spec is None:
                skipped_agents.append(agent.agent_id)
                continue
            agent_state = state_agents.get(agent.agent_id, _AgentState())
            if spec.tasks:
                # feat-394 decision 3: tasks: multi-sub-rhythm — each task runs independently.
                # Per-task last_due_at is stored in agent_state.per_task_last_due.
                any_due = False
                per_task_last_due = dict(agent_state.per_task_last_due)
                for task in spec.tasks:
                    task_last_due = _parse_optional_datetime(per_task_last_due.get(task.name))
                    task_schedule = _IntervalSchedule(interval=task.interval)
                    due_times = task_schedule.due_times_up_to(
                        now=current_time, last_due_at=task_last_due
                    )
                    for due_at in due_times:
                        any_due = True
                        triggered_runs.append(
                            await self._submit_run(
                                agent=agent, due_at=due_at, instructions=task.prompt
                            )
                        )
                        per_task_last_due[task.name] = due_at.isoformat()
                if any_due:
                    state_agents[agent.agent_id] = _AgentState(
                        last_due_at=agent_state.last_due_at,
                        per_task_last_due=per_task_last_due,
                    )
                # If no task is due this tick, don't append to skipped_agents;
                # the absence of triggered_runs is sufficient signal.
            else:
                # Legacy single-schedule mode.
                due_times = spec.schedule.due_times_up_to(
                    now=current_time,
                    last_due_at=_parse_optional_datetime(agent_state.last_due_at),
                )
                if not due_times:
                    continue
                for due_at in due_times:
                    triggered_runs.append(
                        await self._submit_run(
                            agent=agent, due_at=due_at, instructions=spec.instructions
                        )
                    )
                    state_agents[agent.agent_id] = _AgentState(
                        last_due_at=due_at.isoformat(),
                        per_task_last_due=agent_state.per_task_last_due,
                    )

        self._state_store.save(_SchedulerState(agents=state_agents))
        return HeartbeatTickSummary(
            triggered_runs=tuple(triggered_runs), skipped_agents=tuple(skipped_agents)
        )

    async def _get_or_create_heartbeat_session(
        self, *, agent: AgentWorkspaceConfig
    ) -> str:
        """Return the session to use for one agent's heartbeat run.

        feat-394 decision 3: prefer the canonical direct-chat kernel session when available
        (set by PollingHeartbeatRunner after first delivery), so heartbeat runs accumulate
        conversation context like a "main-session turn" in openclaw.  Falls back to the
        per-agent :heartbeat session (feat-393 behaviour) when no canonical session is known.

        Returns:
            session_id to use for this tick's heartbeat run.

        Raises:
            RuntimeError: When the kernel session creation returns an empty or malformed session_id.
        """
        # Check canonical session first (feat-394 decision 3: run in owner direct-chat session).
        canonical_id = self._canonical_session_store.get(agent.agent_id)
        if canonical_id:
            return canonical_id

        # Fallback: legacy per-agent :heartbeat session (feat-393 behaviour, or first heartbeat).
        session_id = self._heartbeat_sessions.get(agent.agent_id)
        if session_id:
            return session_id
        session_payload = await self._kernel_client.create_session(
            workspace_root=str(agent.workspace_root),
            product_id="personal_assistant",
            title=agent.title,
        )
        new_session_id = str(session_payload.get("session_id", "")).strip()
        if not new_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        self._heartbeat_sessions[agent.agent_id] = new_session_id
        return new_session_id

    async def _submit_run(
        self, *, agent: AgentWorkspaceConfig, due_at: datetime, instructions: str
    ) -> HeartbeatRunRecord:
        # feat-393 decision 4: stable :heartbeat session reused across ticks instead of
        # fresh session per tick.  Reuse preserves standing-task context continuity and
        # ensures heartbeat runs are never detached from a resolvable IM conversation target.
        session_id = await self._get_or_create_heartbeat_session(agent=agent)
        message = _build_heartbeat_message(
            agent_id=agent.agent_id, due_at=due_at, instructions=instructions
        )
        # feat-393 fix-r2 Fix B: capture the event sequence before submitting so the
        # consumer can stream from this anchor instead of replaying all history.
        # This avoids an O(history) re-scan on each tick as the :heartbeat session grows.
        # getattr fallback: test fakes and legacy callers that don't implement
        # current_event_sequence get anchor=0 (full-history scan, functionally correct).
        _get_seq = getattr(self._kernel_client, "current_event_sequence", None)
        stream_anchor = _get_seq() if callable(_get_seq) else 0
        # The stateless kernel needs workspace_root to locate the session JSONL;
        # origin=heartbeat lets auto_mode_gate detect unattended context and skip
        # blocking permission requests that nobody is around to answer.
        run_payload = self._kernel_client.submit_message(
            session_id=session_id,
            texts=[message],
            workspace_root=str(agent.workspace_root),
            origin="heartbeat",
        )
        run_id = str(run_payload.get("run_id", "")).strip()
        if not run_id:
            raise RuntimeError("heartbeat submission did not return run_id")
        return HeartbeatRunRecord(
            agent_id=agent.agent_id,
            due_at=due_at,
            run_id=run_id,
            session_id=session_id,
            stream_anchor=stream_anchor,
        )


class _Schedule(Protocol):
    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]: ...


@dataclass(frozen=True, slots=True)
class _AtSchedule:
    due_at: datetime

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        if now < self.due_at:
            return []
        if last_due_at is not None and last_due_at >= self.due_at:
            return []
        return [self.due_at]


@dataclass(frozen=True, slots=True)
class _IntervalSchedule:
    interval: timedelta

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        # Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "every" branch —
        # steps = ceil(elapsed / everyMs), next = anchor + steps * everyMs.
        # Result is always strictly in the future relative to anchor; we only trigger
        # when that future point has actually arrived (next_due_at <= now).
        # This means a restart after a gap never catches up past due-times — it waits
        # for the next aligned future slot.  (feat-394 decision 3/4, replaces feat-393
        # fix-r2 "fold to most-recent" semantics)
        #
        # First-ever tick (last_due_at is None): trigger immediately at floor(now, interval).
        # The first execution is always the clock-aligned slot at or before now; this is the
        # anchor that subsequent ticks use to compute the next future slot.
        if last_due_at is None:
            return [_floor_datetime(now, self.interval)]
        elapsed = now - last_due_at
        if elapsed <= timedelta(0):
            return []
        interval_secs = int(self.interval.total_seconds())
        elapsed_secs = int(elapsed.total_seconds())
        # steps = ceil(elapsed / interval) — gives the first step that is strictly after anchor.
        steps = max(1, (elapsed_secs + interval_secs - 1) // interval_secs)
        next_due_at = last_due_at + self.interval * steps
        if next_due_at > now:
            return []
        return [next_due_at]


@dataclass(frozen=True, slots=True)
class _CronSchedule:
    minute_values: tuple[int, ...]
    hour_values: tuple[int, ...]
    day_values: tuple[int, ...]
    month_values: tuple[int, ...]
    weekday_values: tuple[int, ...]

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        # Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "cron" branch —
        # openclaw's scheduler checks "now >= job.next_run_at" per tick, and after firing
        # immediately updates next_run_at = computeNextRunAtMs(schedule, now) which is always
        # strictly in the future.  The net effect: only the minute that cron matches AND has
        # not already been executed triggers a run.  A restart after a gap does NOT replay
        # missed cron slots — the first future-matching minute is the next run.
        # (feat-394 decision 3/4; replaces feat-393 fix-r2 "most-recent" backfill semantics)
        #
        # Implementation: trigger when the current minute matches the cron expression AND
        # differs from last_due_at (dedup guard prevents double-fire in the same minute).
        current = now.replace(second=0, microsecond=0)
        if not self._matches(current):
            return []
        if last_due_at is not None and last_due_at.replace(second=0, microsecond=0) == current:
            return []
        return [current]

    def _matches(self, candidate: datetime) -> bool:
        cron_weekday = (candidate.weekday() + 1) % 7
        return (
            candidate.minute in self.minute_values
            and candidate.hour in self.hour_values
            and candidate.day in self.day_values
            and candidate.month in self.month_values
            and cron_weekday in self.weekday_values
        )


def _is_heartbeat_content_effectively_empty(content: str) -> bool:
    """Return True if HEARTBEAT.md has no actionable tasks (only headers, empty list items, fences).

    Provenance: openclaw/src/auto-reply/heartbeat.ts:isHeartbeatContentEffectivelyEmpty
    Mirrors the openclaw check so that a workspace-default empty HEARTBEAT.md template
    does not trigger a heartbeat run (which would just output HEARTBEAT_OK every tick).
    """
    import re as _re  # noqa: PLC0415 — local import: this function is called rarely, avoids top-level dep
    _HEADER_RE = _re.compile(r"^#+(\s|$)")
    _EMPTY_LIST_RE = _re.compile(r"^[-*+]\s*(\[[\sXx]?\]\s*)?$")
    _FENCE_RE = _re.compile(r"^```[A-Za-z0-9_-]*$")
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADER_RE.match(stripped):
            continue
        if _EMPTY_LIST_RE.match(stripped):
            continue
        if _FENCE_RE.match(stripped):
            continue
        return False  # found at least one non-empty, non-comment line
    return True  # all lines were blank or structural decoration


def _parse_heartbeat_tasks(content: str) -> list[_HeartbeatTask]:
    """Parse a HEARTBEAT.md ``tasks:`` block into a list of HeartbeatTask objects.

    Provenance: openclaw/src/auto-reply/heartbeat.ts:parseHeartbeatTasks
    Supports YAML-like task definitions:

        tasks:
          - name: inbox-check
            interval: 30m
            prompt: "Check for urgent unread emails"
          - name: schedule-review
            interval: 2h
            prompt: "Review upcoming schedule"

    Args:
        content: Full HEARTBEAT.md content string.

    Returns:
        Parsed task list; empty list when no tasks: block is found or tasks are malformed.
    """
    tasks: list[_HeartbeatTask] = []
    lines = content.split("\n")
    in_tasks_block = False

    i = 0
    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()

        if trimmed == "tasks:":
            in_tasks_block = True
            i += 1
            continue

        if not in_tasks_block:
            i += 1
            continue

        # Exit tasks block on non-indented, non-task-field content.
        is_task_field = (
            trimmed.startswith("interval:")
            or trimmed.startswith("prompt:")
            or trimmed.startswith("- name:")
        )
        if (
            not is_task_field
            and not line.startswith(" ")
            and not line.startswith("\t")
            and trimmed
            and not trimmed.startswith("-")
        ):
            in_tasks_block = False
            i += 1
            continue

        if trimmed.startswith("- name:"):
            name = trimmed[len("- name:"):].strip().strip("\"'")
            interval_str = ""
            prompt = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                next_trimmed = next_line.strip()
                if next_trimmed.startswith("- name:"):
                    break
                if next_trimmed.startswith("interval:") and (
                    next_line.startswith(" ") or next_line.startswith("\t")
                ):
                    interval_str = next_trimmed[len("interval:"):].strip().strip("\"'")
                elif next_trimmed.startswith("prompt:") and (
                    next_line.startswith(" ") or next_line.startswith("\t")
                ):
                    prompt = next_trimmed[len("prompt:"):].strip().strip("\"'")
                elif (
                    not next_trimmed.startswith(" ")
                    and not next_trimmed.startswith("\t")
                    and next_trimmed
                ):
                    in_tasks_block = False
                    break
                j += 1

            if name and interval_str and prompt:
                try:
                    interval = _parse_interval(interval_str)
                    tasks.append(_HeartbeatTask(name=name, interval=interval, prompt=prompt))
                except ValueError:
                    pass  # skip malformed tasks silently (raises hard if block is corrupt)

        i += 1

    return tasks


def _load_heartbeat_spec(path: Path) -> _HeartbeatSpec | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return None
    # Provenance: openclaw/src/auto-reply/heartbeat.ts:isHeartbeatContentEffectivelyEmpty —
    # skip heartbeat execution entirely when the file has no actionable tasks.
    if _is_heartbeat_content_effectively_empty(content):
        return None

    # feat-394 decision 3: try tasks: multi-sub-rhythm format first.
    # If a tasks: block is found and valid, it takes precedence over the legacy single-schedule format.
    tasks = _parse_heartbeat_tasks(content)
    if tasks:
        # tasks: format uses a sentinel schedule (irrelevant — each task has its own interval)
        # and aggregated instructions from all task prompts.
        aggregated_instructions = "\n".join(f"- [{t.name}] {t.prompt}" for t in tasks)
        # Use a 1-second interval sentinel that is immediately overridden by per-task scheduling.
        _SENTINEL_SCHEDULE = _IntervalSchedule(interval=timedelta(seconds=1))
        return _HeartbeatSpec(
            schedule=_SENTINEL_SCHEDULE,
            instructions=aggregated_instructions,
            tasks=tuple(tasks),
        )

    schedule_entries: list[tuple[str, str]] = []
    instruction_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if (
            lowered.startswith("#")
            or lowered.startswith("<!--")
            and lowered.endswith("-->")
        ):
            continue
        matched_prefix = next(
            (prefix for prefix in _SCHEDULE_PREFIXES if lowered.startswith(prefix)),
            None,
        )
        if matched_prefix is not None:
            schedule_entries.append(
                (matched_prefix[:-1], line.split(":", 1)[1].strip())
            )
            continue
        if not line:
            continue
        if line in {"---", "***"}:
            continue
        # Skip tasks: block lines in legacy mode (tasks: is handled above)
        if line.lower() == "tasks:":
            continue
        instruction_lines.append(line)

    if not instruction_lines:
        return None
    if len(schedule_entries) != 1:
        raise ValueError("HEARTBEAT.md must declare exactly one schedule mode")
    schedule_kind, schedule_value = schedule_entries[0]
    return _HeartbeatSpec(
        schedule=_parse_schedule(schedule_kind, schedule_value),
        instructions="\n".join(instruction_lines),
    )


def _parse_schedule(kind: str, raw_value: str) -> _Schedule:
    if kind in {"interval", "every"}:
        return _IntervalSchedule(interval=_parse_interval(raw_value))
    if kind == "at":
        return _AtSchedule(
            due_at=_normalize_datetime(datetime.fromisoformat(raw_value))
        )
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
        weekday_values=_parse_cron_field(
            weekday, minimum=0, maximum=6, allow_names=True
        ),
    )


def _parse_cron_field(
    raw_value: str, *, minimum: int, maximum: int, allow_names: bool = False
) -> tuple[int, ...]:
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


def _build_heartbeat_message(
    *, agent_id: str, due_at: datetime, instructions: str
) -> str:
    return (
        "Heartbeat scheduler trigger.\n\n"
        f"Agent: {agent_id}\n"
        f"Due at: {due_at.isoformat()}\n\n"
        "Read the workspace HEARTBEAT.md intent below, perform only valid actionable tasks, and stay quiet if there is nothing useful to report.\n\n"
        f"{instructions}"
    )
