"""Heartbeat scheduling engine for the personal assistant gateway."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Protocol
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.scheduler._schedule_primitives import (
    _INTERVAL_PATTERN,
    _AtSchedule,
    _IntervalSchedule,
    _Schedule,
    _normalize_datetime,
    _parse_cron,
    _parse_optional_datetime,
)

_SCHEDULE_PREFIXES = ("interval:", "every:", "cron:", "at:")
# feat-394-M11 decision E: default heartbeat cadence when agent.heartbeat_every is not set.
# Provenance: openclaw/src/auto-reply/heartbeat.ts DEFAULT_HEARTBEAT_EVERY = "30m".
_DEFAULT_HEARTBEAT_EVERY = "30m"


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
                {
                    k: v
                    for k, v in raw_per_task.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
                if isinstance(raw_per_task, dict)
                else {}
            )
            agents[agent_id] = _AgentState(
                last_due_at=last_due_at, per_task_last_due=per_task_last_due
            )
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
    # feat-394-M11 decision E: schedule is None when no explicit at:/cron: is present in md.
    # In that case the top-level cadence comes from AgentWorkspaceConfig.heartbeat_every (config).
    # every:/interval: lines are no longer parsed from md; they are silently skipped.
    schedule: "_Schedule | None"
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
        busy_sessions: set[str] | None = None,
        session_store: object | None = None,
        agents_getter: "Callable[[], Iterable[AgentWorkspaceConfig]] | None" = None,
        run_queue: "object | None" = None,
    ) -> None:
        self._agents = agents
        # feat-394-M4 R3 S1.3 fix: when provided, agents_getter() is called on
        # each tick to read the live agent configuration from pipeline._agents.
        # This allows toggle changes (heartbeat_enabled=False) to take effect on
        # the next tick without requiring a gateway restart.
        # When None, tick falls back to the frozen self._agents tuple (backward compat).
        self._agents_getter = agents_getter
        self._kernel_client = kernel_client
        self._state_store = state_store
        # feat-394-M4 R2-3 cron/heartbeat busy-skip: SessionRunQueue reference.
        # When provided, tick checks run_queue._active_sessions for the agent's
        # canonical session_key before submitting a heartbeat run.
        # This prevents heartbeat from stacking while user messages are in flight.
        self._run_queue = run_queue
        # feat-394 decision 3: canonical direct chat kernel session per agent_id.
        # Updated by _refresh_canonical_sessions before each tick submission.
        # Falls back to the legacy _heartbeat_sessions dict when no binding is found.
        self._canonical_session_store: dict[str, str] = (
            canonical_session_store if canonical_session_store is not None else {}
        )
        # feat-394 decision 3: busy session set — kernel sessions currently running a turn.
        # Heartbeat skips when the agent's canonical session is busy to avoid concurrent runs.
        # Shared with PollingHeartbeatRunner / InboundPipeline; updated externally.
        self._busy_sessions: set[str] = (
            busy_sessions if busy_sessions is not None else set()
        )
        # feat-394 decision 3: gateway session store for tick-time canonical session lookup.
        # find_direct_by_agent reads the SQLite session_bindings table (pure gateway read,
        # no IM HTTP call) and updates canonical_session_store before each heartbeat run.
        # This replaces the prior reactive approach (turn_start ack → fill) which failed for
        # first-tick / restart / silent polling (chicken-egg: silent polling never acks → never fills).
        self._session_store: object | None = session_store
        # Legacy fallback session store (for when no canonical session binding is found yet).
        # In feat-394 mode, session_store lookup takes precedence.
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

        # feat-394-M4 R3 S1.3 fix: read live agent config on each tick when a
        # getter is available, so toggle changes take effect without restart.
        # Falls back to the frozen _agents tuple when no getter is configured.
        active_agents = (
            self._agents_getter() if self._agents_getter is not None else self._agents
        )

        for agent in active_agents:
            # feat-394 decision 5: per-agent heartbeat gate — skip without reading HEARTBEAT.md
            # when the agent's heartbeat_enabled flag is False (synced from IM via ConfigSyncNotifier).
            if not agent.heartbeat_enabled:
                skipped_agents.append(agent.agent_id)
                continue
            # feat-394 decision 3: activeHours gate — skip when outside the configured active window.
            if not _is_within_active_hours(
                now=current_time,
                start_hhmm=agent.heartbeat_active_hours_start,
                end_hhmm=agent.heartbeat_active_hours_end,
                timezone_name=agent.heartbeat_active_hours_timezone,
            ):
                skipped_agents.append(agent.agent_id)
                continue
            # feat-394 decision 3: tick-time canonical session refresh.
            # Read the agent's oldest direct-chat binding from the gateway SQLite store
            # BEFORE checking busy-skip or submitting a run.  This replaces the prior
            # reactive approach (turn_start ack → fill) which failed for first-tick,
            # restart, and silent-polling scenarios (silent polls never ack → never fill).
            # Pure gateway read — no IM HTTP call required.
            _find_fn = getattr(self._session_store, "find_direct_by_agent", None)
            _canonical_session_key: str | None = None
            if _find_fn is not None:
                _binding = _find_fn(channel_name="web_relay", agent_id=agent.agent_id)
                if _binding is not None and _binding.kernel_session_id:
                    self._canonical_session_store[agent.agent_id] = (
                        _binding.kernel_session_id
                    )
                    _canonical_session_key = _binding.session_key
            # feat-394 decision 3: busy-session gate — skip when canonical session is running
            # a turn (avoid concurrent runs in the same direct-chat kernel session).
            canonical_session = self._canonical_session_store.get(agent.agent_id)
            if canonical_session and canonical_session in self._busy_sessions:
                skipped_agents.append(agent.agent_id)
                continue
            # feat-394-M4 R2-3: run_queue busy-skip — skip when the canonical direct-chat
            # session_key has an active run in the gateway SessionRunQueue.
            # This prevents heartbeat from executing while user messages are in flight,
            # which would force user messages to wait behind the heartbeat LLM call.
            if self._run_queue is not None and _canonical_session_key is not None:
                _active_sessions = getattr(self._run_queue, "_active_sessions", None)
                if (
                    _active_sessions is not None
                    and _canonical_session_key in _active_sessions
                ):
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
                any_due = False
                per_task_last_due = dict(agent_state.per_task_last_due)
                for task in spec.tasks:
                    task_last_due = _parse_optional_datetime(
                        per_task_last_due.get(task.name)
                    )
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
                # feat-394-M11 decision E: when spec.schedule is None (no explicit at:/cron: in md),
                # derive the top-level cadence from agent.heartbeat_every (config).
                # Falls back to DEFAULT_HEARTBEAT_EVERY ("30m") when the config field is absent,
                # matching openclaw's DEFAULT_HEARTBEAT_EVERY constant.
                # Provenance: openclaw/src/config/zod-schema.agent-runtime.ts HeartbeatSchema.every
                # (default "30m") and infra/heartbeat-summary.ts:resolveHeartbeatIntervalMs.
                effective_schedule: "_Schedule"
                if spec.schedule is not None:
                    effective_schedule = spec.schedule
                else:
                    _every_str = agent.heartbeat_every or _DEFAULT_HEARTBEAT_EVERY
                    effective_schedule = _IntervalSchedule(
                        interval=_parse_interval(_every_str)
                    )
                due_times = effective_schedule.due_times_up_to(
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
            name = trimmed[len("- name:") :].strip().strip("\"'")
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
                    interval_str = next_trimmed[len("interval:") :].strip().strip("\"'")
                elif next_trimmed.startswith("prompt:") and (
                    next_line.startswith(" ") or next_line.startswith("\t")
                ):
                    prompt = next_trimmed[len("prompt:") :].strip().strip("\"'")
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
                    tasks.append(
                        _HeartbeatTask(name=name, interval=interval, prompt=prompt)
                    )
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
        # tasks: format — each task has its own interval; no top-level schedule applies.
        # C2 fix: use schedule=None instead of a 1-second sentinel.  The sentinel was
        # harmless only while tasks was non-empty, but if _parse_heartbeat_tasks strips
        # all malformed entries the returned spec would have tasks=() with schedule=1s,
        # causing the tick's else branch to fire at 1-second intervals — never intended.
        # With schedule=None the tick's else branch falls through to config.every safely.
        aggregated_instructions = "\n".join(f"- [{t.name}] {t.prompt}" for t in tasks)
        return _HeartbeatSpec(
            schedule=None,
            instructions=aggregated_instructions,
            tasks=tuple(tasks),
        )

    # feat-394-M11 decision E: every:/interval: lines in md are retired as a top-level
    # cadence source.  They are silently ignored here — the scheduler reads cadence from
    # AgentWorkspaceConfig.heartbeat_every (config, default 30m).  Only at: and cron:
    # schedules in md are still collected (they express a specific point in time, not a
    # simple recurrence — keeping them allows advanced md-authored scheduling if ever needed,
    # though the canonical path for cadence is now config).
    _RETIRED_PREFIXES = {"interval", "every"}
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
            kind = matched_prefix[:-1]
            if kind in _RETIRED_PREFIXES:
                # Silently skip every:/interval: — cadence is now the config's responsibility.
                continue
            schedule_entries.append((kind, line.split(":", 1)[1].strip()))
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
    if len(schedule_entries) > 1:
        raise ValueError(
            "HEARTBEAT.md must declare at most one explicit schedule mode (at:/cron:)"
        )
    if schedule_entries:
        schedule_kind, schedule_value = schedule_entries[0]
        return _HeartbeatSpec(
            schedule=_parse_schedule(schedule_kind, schedule_value),
            instructions="\n".join(instruction_lines),
        )
    # No explicit at:/cron: in md — top-level cadence comes from config (decision E).
    return _HeartbeatSpec(
        schedule=None,
        instructions="\n".join(instruction_lines),
    )


def _parse_schedule(kind: str, raw_value: str) -> _Schedule:
    if kind in {"interval", "every"}:
        return _IntervalSchedule(interval=_parse_interval(raw_value))
    if kind == "at":
        # Heartbeat at-lines fire even if the at-time is past (no expiry check);
        # cron at-jobs use check_expiry=True (feat-394-M7 R5-4 is cron-only).
        return _AtSchedule(
            due_at=_normalize_datetime(datetime.fromisoformat(raw_value)),
            check_expiry=False,
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


def _is_within_active_hours(
    *,
    now: datetime,
    start_hhmm: str | None,
    end_hhmm: str | None,
    timezone_name: str | None,
) -> bool:
    """Return True when ``now`` falls inside the configured active-hours window.

    feat-394 decision 3: activeHours gate mirrors openclaw's "activeHours" check —
    heartbeat is suppressed outside the window so agents don't wake users at night.
    If no window is configured (all params None/empty), always returns True.

    Args:
        now: Current UTC datetime for the tick.
        start_hhmm: Window start in "HH:MM" (local time).  None → no gate.
        end_hhmm: Window end in "HH:MM" (local time).  None → no gate.
        timezone_name: IANA timezone string (e.g. "Asia/Shanghai").  None → UTC.

    Returns:
        True when the current local time is at-or-after start AND before end,
        or when no window is configured.
    """
    if not start_hhmm or not end_hhmm:
        return True  # no window configured → always active

    try:
        import zoneinfo as _zoneinfo  # noqa: PLC0415 — stdlib, lazy import avoids startup cost

        tz = _zoneinfo.ZoneInfo(timezone_name) if timezone_name else UTC
    except Exception:  # noqa: BLE001 — invalid timezone → treat as UTC to avoid silent skip
        tz = UTC

    local_now = now.astimezone(tz)
    local_hhmm = local_now.strftime("%H:%M")

    # Simple HH:MM string comparison works for non-midnight-crossing windows.
    # For midnight-crossing windows (e.g. 22:00-06:00), logic would be inverted;
    # nano spec only documents daytime windows so we keep this simple for now.
    return start_hhmm <= local_hhmm < end_hhmm


# Provenance: openclaw/src/auto-reply/heartbeat.ts:14 HEARTBEAT_PROMPT
# Text is verbatim from that constant (the default heartbeat trigger instruction).
# feat-394 decision 6: heartbeat trigger message must use this verbatim text so model
# behaviour matches openclaw expectations (HEARTBEAT_OK silence + HEARTBEAT.md follow).
# feat-394-M3 WARNING-2 fix: replace custom rewording with the openclaw original.
_OPENCLAW_HEARTBEAT_PROMPT = (
    "Read HEARTBEAT.md if it exists (workspace context). "
    "Follow it strictly. "
    "Do not infer or repeat old tasks from prior chats. "
    "If nothing needs attention, reply HEARTBEAT_OK."
)


def _build_heartbeat_message(
    *, agent_id: str, due_at: datetime, instructions: str
) -> str:
    """Build the heartbeat trigger message for a scheduled heartbeat run.

    The base instruction text is the verbatim openclaw HEARTBEAT_PROMPT
    (openclaw/src/auto-reply/heartbeat.ts:14).  When the task has explicit
    HEARTBEAT.md instructions they are appended after the base prompt.
    """
    parts = [_OPENCLAW_HEARTBEAT_PROMPT]
    if instructions and instructions.strip():
        parts.append(f"\n\n{instructions.strip()}")
    return "\n".join(parts)
