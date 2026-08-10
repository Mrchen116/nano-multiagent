"""Long-lived background owner for restricted Python Workflow runs."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_hex
from typing import Any, Callable, Mapping

from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.utils.time import utc_now_iso
from agent.core.workflows import (
    AgentCallSpec,
    OutputTokenBudget,
    ResumeEntry,
    WorkflowRuntime,
    compile_workflow,
    execute_workflow,
)

from .store import WorkflowRunStore, slugify_workflow_name


_GUIDELINE_AGENT_BOUNDARIES = {"small": 5, "medium": 15, "large": 50}
_DEFAULT_LARGE_AGENT_COUNT = 25
_LARGE_TOKEN_ESTIMATE = 1_500_000


@dataclass(frozen=True, slots=True)
class WorkflowLaunchContext:
    parent_session_id: str
    workspace_root: Path
    parent_run_id: str | None = None
    parent_tool_call_id: str | None = None
    subagent_control: Any = None
    workflow_ultracode: bool = False
    parent_run_origin: str = "user"
    parent_runtime_captured: bool = False
    parent_model: str | None = None
    parent_effort: str | None = None
    parent_enabled_tools: tuple[str, ...] | None = None
    parent_skills: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class WorkflowLaunch:
    status: str
    task_id: str
    run_id: str
    name: str
    script_path: str
    diagnostics: str


@dataclass(slots=True)
class _RunHandle:
    launch: WorkflowLaunch
    context: WorkflowLaunchContext
    store: WorkflowRunStore
    snapshot: dict[str, Any]
    child_runner: Callable[[AgentCallSpec], Any]
    runtime: WorkflowRuntime | None = None
    thread: threading.Thread | None = None
    terminal: threading.Event = field(default_factory=threading.Event)
    stop_requested: bool = False
    output_budget: OutputTokenBudget | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class WorkflowManager:
    """Validate synchronously, then run each Workflow in a private daemon loop."""

    def __init__(
        self,
        *,
        background_registry: BackgroundTaskRegistry,
        config_dirname: str,
        child_runner_factory: Callable[
            [WorkflowLaunchContext, str], Callable[[AgentCallSpec], Any]
        ],
        event_publisher: Callable[[str, Mapping[str, Any]], None] | None = None,
        named_source_resolver: Callable[[str, Path], str | None] | None = None,
    ) -> None:
        self._background_registry = background_registry
        self._config_dirname = config_dirname
        self._child_runner_factory = child_runner_factory
        self._event_publisher = event_publisher
        self._named_source_resolver = named_source_resolver
        self._runs: dict[str, _RunHandle] = {}
        self._persisted: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def launch(
        self,
        *,
        source: str,
        args: Any,
        context: WorkflowLaunchContext,
        resume_from_run_id: str | None = None,
        size_guideline: str = "medium",
        size_guideline_explicit: bool = False,
        output_budget: OutputTokenBudget | None = None,
    ) -> WorkflowLaunch:
        """Persist and start one already-authorized Workflow without blocking."""

        if self._closed:
            raise RuntimeError("Workflow manager is closed")
        compiled = compile_workflow(source)
        resume_entries = self._resume_entries(
            resume_from_run_id,
            parent_session_id=context.parent_session_id,
        )
        run_id = _make_id("wf")
        task_id = _make_id("wt")
        store = WorkflowRunStore(
            workspace_root=context.workspace_root,
            config_dirname=self._config_dirname,
            parent_session_id=context.parent_session_id,
            run_id=run_id,
            slug=slugify_workflow_name(compiled.meta.name),
        )
        now = utc_now_iso()
        snapshot: dict[str, Any] = {
            "run_id": run_id,
            "task_id": task_id,
            "parent_session_id": context.parent_session_id,
            "parent_run_id": context.parent_run_id,
            "parent_tool_call_id": context.parent_tool_call_id,
            "revision": 0,
            "status": "queued",
            "name": compiled.meta.name,
            "description": compiled.meta.description,
            "current_phase": None,
            "phases": [
                {
                    "title": phase.title,
                    "detail": phase.detail,
                    "status": "pending",
                    "agent_call_ids": [],
                }
                for phase in compiled.meta.phases
            ],
            "agents": [],
            "logs": [],
            "usage": None,
            "duration_ms": None,
            "size_guideline": size_guideline,
            "size_guideline_explicit": size_guideline_explicit,
            "large_warning": None,
            "script_path": str(store.script_path),
            "journal_path": str(store.journal_path),
            "transcript_dir": str(store.run_dir),
            "resumed_from": resume_from_run_id,
            "result": None,
            "error": None,
            "warnings": [],
            "created_at": now,
            "updated_at": now,
        }
        store.initialize(source=source, snapshot=snapshot)
        launch = WorkflowLaunch(
            status="async_launched",
            task_id=task_id,
            run_id=run_id,
            name=compiled.meta.name,
            script_path=str(store.script_path),
            diagnostics=str(store.run_dir),
        )
        handle = _RunHandle(
            launch=launch,
            context=context,
            store=store,
            snapshot=snapshot,
            child_runner=self._child_runner_factory(context, run_id),
            output_budget=output_budget,
        )
        self._background_registry.register_workflow(
            task_id=task_id,
            parent_session_id=context.parent_session_id,
            workflow_run_id=run_id,
            description=compiled.meta.description,
            output_file=str(store.snapshot_path),
            diagnostics=str(store.run_dir),
            resume_hint=f"/workflows {run_id} resume",
            workspace_root=str(context.workspace_root),
        )
        self._background_registry.set_stop_handle(
            task_id, _WorkflowStopHandle(manager=self, run_id=run_id)
        )
        with self._lock:
            self._runs[run_id] = handle
        thread = threading.Thread(
            target=self._thread_main,
            args=(handle, compiled, args, resume_entries),
            name=f"workflow-{run_id}",
            daemon=True,
        )
        handle.thread = thread
        thread.start()
        return launch

    def list_runs(self, *, session_id: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._lock:
            values = tuple(self._runs.values())
            persisted = tuple(self._persisted.values())
        snapshots_by_id = {
            str(item["run_id"]): _clone_snapshot(item) for item in persisted
        }
        snapshots_by_id.update(
            {handle.launch.run_id: self._snapshot(handle) for handle in values}
        )
        snapshots = list(snapshots_by_id.values())
        if session_id is not None:
            snapshots = [
                item for item in snapshots if item["parent_session_id"] == session_id
            ]
        return tuple(
            sorted(snapshots, key=lambda item: item["created_at"], reverse=True)
        )

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            handle = self._runs.get(run_id)
            persisted = self._persisted.get(run_id)
        if handle is not None:
            return self._snapshot(handle)
        return _clone_snapshot(persisted) if persisted is not None else None

    def load_session_runs(self, *, session_id: str, workspace_root: Path) -> None:
        """Load durable complete snapshots for SDK query after process restart."""

        runs_root = (
            workspace_root.expanduser().resolve()
            / self._config_dirname
            / "sessions"
            / session_id
            / "workflows"
            / "runs"
        )
        loaded: dict[str, dict[str, Any]] = {}
        if not runs_root.is_dir():
            return
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            if not (
                (run_dir / "run.json").is_file()
                or (run_dir / "journal.jsonl").is_file()
            ):
                continue
            value = WorkflowRunStore.load_snapshot(run_dir)
            if (
                isinstance(value, dict)
                and value.get("parent_session_id") == session_id
                and isinstance(value.get("run_id"), str)
            ):
                loaded[str(value["run_id"])] = value
        with self._lock:
            self._persisted.update(loaded)

    def wait(self, run_id: str, *, timeout: float | None = None) -> dict[str, Any]:
        with self._lock:
            handle = self._runs.get(run_id)
        if handle is None:
            raise ValueError(f"unknown Workflow run: {run_id}")
        if not handle.terminal.wait(timeout):
            raise TimeoutError(f"Workflow run did not finish: {run_id}")
        return self._snapshot(handle)

    def control(
        self,
        run_id: str,
        *,
        action: str,
        agent_call_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            handle = self._runs.get(run_id)
        if handle is None:
            raise ValueError(f"unknown Workflow run: {run_id}")
        with handle.lock:
            runtime = handle.runtime
            status = str(handle.snapshot["status"])
            if action == "pause" and status == "running":
                if runtime is not None:
                    runtime.pause()
                self._update(handle, status="paused")
            elif action == "resume" and status == "paused":
                if runtime is not None:
                    runtime.resume()
                self._update(handle, status="running")
            elif action == "stop" and status in {"queued", "running", "paused"}:
                if agent_call_id is not None:
                    stopper = getattr(handle.child_runner, "stop_agent", None)
                    if not callable(stopper) or not stopper(agent_call_id):
                        raise ValueError(
                            f"Workflow Agent is not running: {agent_call_id}"
                        )
                else:
                    handle.stop_requested = True
                    stop_all = getattr(handle.child_runner, "stop_all", None)
                    if callable(stop_all):
                        stop_all()
                    if runtime is not None:
                        runtime.stop()
            elif action == "restart_agent":
                restarter = getattr(handle.child_runner, "restart_agent", None)
                if (
                    agent_call_id is None
                    or not callable(restarter)
                    or not restarter(agent_call_id)
                ):
                    raise ValueError(
                        f"Workflow Agent is not running: {agent_call_id or ''}"
                    )
            elif status not in {"completed", "failed", "stopped"}:
                raise ValueError(f"invalid Workflow control: {action} while {status}")
        return self._snapshot(handle)

    def close(self) -> None:
        self._closed = True
        with self._lock:
            handles = tuple(self._runs.values())
        for handle in handles:
            if not handle.terminal.is_set():
                self.control(handle.launch.run_id, action="stop")
        for handle in handles:
            thread = handle.thread
            if thread is not None:
                thread.join(timeout=2)

    def _thread_main(self, handle, compiled, args, resume_entries) -> None:  # noqa: ANN001
        asyncio.run(self._run(handle, compiled, args, resume_entries))

    async def _run(self, handle, compiled, args, resume_entries) -> None:  # noqa: ANN001
        started = time.monotonic()
        try:

            async def observed_child(call: AgentCallSpec) -> Any:
                agent_info = {
                    "agent_call_id": f"wa_{call.start_ordinal:06d}",
                    "start_ordinal": call.start_ordinal,
                    "status": "running",
                    "prompt": call.prompt,
                    "label": call.label,
                    "phase": call.phase,
                    "terminal_ordinal": None,
                    "result": None,
                    "error": None,
                    "resume_key": call.resume_key,
                }
                with handle.lock:
                    _maybe_add_large_warning(
                        handle,
                        agent_count=call.start_ordinal + 1,
                    )
                    handle.snapshot["agents"].append(agent_info)
                    for phase_info in handle.snapshot["phases"]:
                        if phase_info["title"] == call.phase:
                            phase_info["agent_call_ids"].append(
                                agent_info["agent_call_id"]
                            )
                            break
                    self._journal(handle, "agent_started", **agent_info)
                    self._write(handle)
                try:
                    result = await handle.child_runner(call)
                except Exception as exc:
                    with handle.lock:
                        agent_info["status"] = "failed"
                        agent_info["error"] = str(exc)
                        for warning in getattr(handle.child_runner, "warnings", ()):
                            if warning not in handle.snapshot["warnings"]:
                                handle.snapshot["warnings"].append(warning)
                        self._journal(handle, "agent_error", **agent_info)
                        self._write(handle)
                    raise
                with handle.lock:
                    status_for = getattr(handle.child_runner, "status_for", None)
                    agent_info["status"] = (
                        status_for(agent_info["agent_call_id"])
                        if callable(status_for)
                        else None
                    ) or "completed"
                    agent_info["result"] = result
                    usage_for = getattr(handle.child_runner, "usage_for", None)
                    usage = (
                        usage_for(agent_info["agent_call_id"])
                        if callable(usage_for)
                        else None
                    )
                    if usage:
                        agent_info["usage"] = usage
                        _merge_usage(handle.snapshot, usage)
                        _maybe_add_large_warning(handle)
                        if handle.output_budget is not None:
                            handle.output_budget.add(
                                int(usage.get("completion_tokens", 0))
                            )
                    child_warnings = getattr(handle.child_runner, "warnings", ())
                    for warning in child_warnings:
                        if warning not in handle.snapshot["warnings"]:
                            handle.snapshot["warnings"].append(warning)
                    self._journal(handle, "agent_result", **agent_info)
                    self._write(handle)
                return result

            async def nested_runner(
                name_or_ref: str | Mapping[str, Any],
                nested_args: Any,
                parent_runtime: WorkflowRuntime,
            ) -> Any:
                source = self._resolve_nested_source(name_or_ref, handle.context)
                if source is None:
                    raise ValueError(f"unknown nested Workflow: {name_or_ref}")
                nested = compile_workflow(source)
                parent_runtime.include_phases(
                    [phase.title for phase in nested.meta.phases]
                )
                with handle.lock:
                    known = {
                        phase_info["title"] for phase_info in handle.snapshot["phases"]
                    }
                    for phase_info in nested.meta.phases:
                        if phase_info.title not in known:
                            handle.snapshot["phases"].append(
                                {
                                    "title": phase_info.title,
                                    "detail": phase_info.detail,
                                    "status": "pending",
                                    "agent_call_ids": [],
                                }
                            )
                nested_result = await execute_workflow(
                    nested, args=nested_args, runtime=parent_runtime
                )
                if str(nested_result.status) != "completed":
                    raise RuntimeError(
                        nested_result.error or f"nested Workflow {nested_result.status}"
                    )
                return nested_result.result

            def phase_changed(title: str) -> None:
                with handle.lock:
                    for phase_info in handle.snapshot["phases"]:
                        if phase_info["status"] == "running":
                            phase_info["status"] = "completed"
                        if phase_info["title"] == title:
                            phase_info["status"] = "running"
                    self._update(handle, current_phase=title)
                    self._journal(handle, "phase_changed", title=title)

            def log_added(message: str) -> None:
                with handle.lock:
                    handle.snapshot["logs"].append(message)
                    self._journal(handle, "log", message=message)
                    self._write(handle)

            runtime = WorkflowRuntime(
                child_runner=observed_child,
                phases=[phase.title for phase in compiled.meta.phases],
                resume_entries=resume_entries,
                nested_runner=nested_runner,
                budget=handle.output_budget,
                phase_callback=phase_changed,
                log_callback=log_added,
            )
            handle.runtime = runtime
            if handle.stop_requested:
                runtime.stop()
            self._background_registry.mark_running(handle.launch.task_id)
            with handle.lock:
                self._update(handle, status="running")
                self._journal(handle, "run_started", snapshot=self._snapshot(handle))
            result = await execute_workflow(compiled, args=args, runtime=runtime)
            duration_ms = int((time.monotonic() - started) * 1000)
            with handle.lock:
                self._reconcile_completions(handle, runtime)
                terminal = str(result.status)
                if terminal == "completed":
                    for phase_info in handle.snapshot["phases"]:
                        if phase_info["status"] == "running":
                            phase_info["status"] = "completed"
                else:
                    for phase_info in handle.snapshot["phases"]:
                        if phase_info["status"] == "running":
                            phase_info["status"] = terminal
                self._update(
                    handle,
                    status=terminal,
                    result=result.result,
                    error=result.error,
                    duration_ms=duration_ms,
                    logs=list(runtime.logs),
                    current_phase=runtime.current_phase,
                )
                self._journal(
                    handle,
                    f"run_{terminal}",
                    result=result.result,
                    error=result.error,
                    snapshot=self._snapshot(handle),
                )
            result_text = (
                json.dumps(result.result, ensure_ascii=False)
                if not isinstance(result.result, str)
                else result.result
            )
            if terminal == "completed":
                self._background_registry.complete(
                    handle.launch.task_id,
                    result_text=result_text,
                    duration_ms=duration_ms,
                    tool_use_count=len(runtime.completions),
                )
            elif terminal == "stopped":
                self._background_registry.stop(
                    handle.launch.task_id,
                    result_text=result_text,
                    error=result.error,
                    duration_ms=duration_ms,
                    tool_use_count=len(runtime.completions),
                )
            else:
                self._background_registry.fail(
                    handle.launch.task_id, error=result.error or "Workflow failed"
                )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            with handle.lock:
                self._update(
                    handle,
                    status="failed",
                    error=str(exc),
                    duration_ms=duration_ms,
                )
                self._journal(
                    handle,
                    "run_failed",
                    error=str(exc),
                    snapshot=self._snapshot(handle),
                )
            self._background_registry.fail(handle.launch.task_id, error=str(exc))
        finally:
            handle.terminal.set()

    def _resume_entries(
        self,
        run_id: str | None,
        *,
        parent_session_id: str,
    ) -> tuple[ResumeEntry, ...]:
        if run_id is None:
            return ()
        previous = self.get(run_id)
        if previous is None:
            raise ValueError(f"unknown resume Workflow run: {run_id}")
        if previous.get("parent_session_id") != parent_session_id:
            raise ValueError(
                "resume Workflow run belongs to a different parent session"
            )
        completed_agents = sorted(
            previous.get("agents", ()), key=lambda item: int(item["start_ordinal"])
        )
        return tuple(
            ResumeEntry(
                key=item["resume_key"],
                result=item.get("result"),
                terminal_ordinal=int(
                    index
                    if item.get("terminal_ordinal") is None
                    else item["terminal_ordinal"]
                ),
            )
            for index, item in enumerate(completed_agents)
            if item.get("status") == "completed" and item.get("resume_key")
        )

    def _resolve_nested_source(
        self,
        name_or_ref: str | Mapping[str, Any],
        context: WorkflowLaunchContext,
    ) -> str | None:
        if isinstance(name_or_ref, Mapping):
            raw_path = name_or_ref.get("scriptPath")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError("nested Workflow artifact requires scriptPath")
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = context.workspace_root / path
            try:
                return path.resolve().read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(
                    f"unable to read nested Workflow scriptPath: {path}"
                ) from exc
        if not isinstance(name_or_ref, str):
            raise ValueError("nested Workflow requires a saved name or scriptPath")
        resolver = self._named_source_resolver
        return (
            resolver(name_or_ref, context.workspace_root)
            if resolver is not None
            else None
        )

    def _reconcile_completions(
        self, handle: _RunHandle, runtime: WorkflowRuntime
    ) -> None:
        by_start = {
            int(item["start_ordinal"]): item for item in handle.snapshot["agents"]
        }
        for completion in runtime.completions:
            start = completion.call.start_ordinal
            item = by_start.get(start)
            if item is None:
                item = {
                    "agent_call_id": f"wa_{start:06d}",
                    "start_ordinal": start,
                    "status": "completed",
                    "prompt": completion.call.prompt,
                    "label": completion.call.label,
                    "phase": completion.call.phase,
                    "terminal_ordinal": completion.terminal_ordinal,
                    "result": completion.result,
                    "error": None,
                    "resume_key": completion.call.resume_key,
                    "replayed": True,
                }
                handle.snapshot["agents"].append(item)
                by_start[start] = item
                self._journal(handle, "agent_replayed", **item)
                continue
            item["terminal_ordinal"] = completion.terminal_ordinal
            item["replayed"] = completion.replayed
        handle.snapshot["agents"].sort(key=lambda item: int(item["start_ordinal"]))

    def _journal(self, handle: _RunHandle, event: str, **payload: Any) -> None:
        handle.store.append(
            {
                "event": event,
                "run_id": handle.launch.run_id,
                "revision": handle.snapshot["revision"],
                "created_at": utc_now_iso(),
                **payload,
            }
        )

    def _update(self, handle: _RunHandle, **changes: Any) -> None:
        handle.snapshot.update(changes)
        self._write(handle)

    def _write(self, handle: _RunHandle) -> None:
        handle.snapshot["revision"] = int(handle.snapshot["revision"]) + 1
        handle.snapshot["updated_at"] = utc_now_iso()
        handle.store.write_snapshot(handle.snapshot)
        publisher = self._event_publisher
        if publisher is not None:
            publisher(handle.context.parent_session_id, self._snapshot(handle))

    @staticmethod
    def _snapshot(handle: _RunHandle) -> dict[str, Any]:
        with handle.lock:
            return json.loads(json.dumps(handle.snapshot, ensure_ascii=False))


def _make_id(prefix: str) -> str:
    return f"{prefix}_{token_hex(8)}"


def _clone_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(snapshot, ensure_ascii=False))


def _merge_usage(snapshot: dict[str, Any], usage: Mapping[str, Any]) -> None:
    current = dict(snapshot.get("usage") or {})
    for key, value in usage.items():
        if isinstance(value, int) and not isinstance(value, bool):
            current[key] = int(current.get(key, 0)) + value
    snapshot["usage"] = current or None


def _maybe_add_large_warning(
    handle: _RunHandle, *, agent_count: int | None = None
) -> None:
    if (
        handle.context.workflow_ultracode
        or handle.snapshot["large_warning"] is not None
    ):
        return
    guideline = str(handle.snapshot["size_guideline"])
    explicit = bool(handle.snapshot.get("size_guideline_explicit"))
    count_warning = False
    if agent_count is not None:
        if explicit:
            boundary = _GUIDELINE_AGENT_BOUNDARIES.get(guideline)
            count_warning = boundary is not None and agent_count >= boundary
        else:
            count_warning = agent_count > _DEFAULT_LARGE_AGENT_COUNT
    usage = handle.snapshot.get("usage")
    total_tokens = usage.get("total_tokens") if isinstance(usage, Mapping) else None
    token_warning = (
        isinstance(total_tokens, int)
        and not isinstance(total_tokens, bool)
        and total_tokens >= _LARGE_TOKEN_ESTIMATE
    )
    if not count_warning and not token_warning:
        return
    if token_warning:
        warning = "Large workflow: estimated 1.5M tokens or more"
    elif explicit:
        warning = f"Large workflow: {guideline} guideline boundary reached"
    else:
        warning = "Large workflow: plan exceeds 25 Agent calls"
    handle.snapshot["large_warning"] = warning
    handle.snapshot["warnings"].append(warning)
    handle.store.append(
        {
            "event": "large_workflow_warning",
            "run_id": handle.launch.run_id,
            "revision": handle.snapshot["revision"],
            "created_at": utc_now_iso(),
            "warning": warning,
        }
    )


@dataclass(frozen=True, slots=True)
class _WorkflowStopHandle:
    manager: WorkflowManager
    run_id: str

    def stop(self) -> None:
        self.manager.control(self.run_id, action="stop")
