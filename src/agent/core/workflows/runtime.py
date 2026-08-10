"""Pure Workflow orchestration primitives and restricted executor."""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Mapping

from .compiler import CompiledWorkflow
from .models import (
    AgentCallSpec,
    AgentCompletion,
    ResumeEntry,
    WorkflowExecutionResult,
    WorkflowLimits,
    WorkflowStatus,
    WorkflowStopped,
)
from .resume import chained_resume_key


ChildRunner = Callable[[AgentCallSpec], Awaitable[Any]]
NestedRunner = Callable[
    [str | Mapping[str, Any], Any, "WorkflowRuntime"], Awaitable[Any]
]


class OutputTokenBudget:
    def __init__(self, total: int | None = None) -> None:
        self.total = total
        self._spent = 0
        self._lock = threading.Lock()

    def add(self, tokens: int) -> None:
        with self._lock:
            self._spent += max(0, tokens)

    def spent(self) -> int:
        with self._lock:
            return self._spent

    def remaining(self) -> int | None:
        if self.total is None:
            return None
        return max(0, self.total - self.spent())


class AgentCall:
    def __init__(self, runtime: "WorkflowRuntime", spec: AgentCallSpec) -> None:
        self._runtime = runtime
        self.spec = spec

    @property
    def start_ordinal(self) -> int:
        return self.spec.start_ordinal

    @property
    def prompt(self) -> str:
        return self.spec.prompt

    def __await__(self):  # noqa: ANN204
        return self._runtime._run_call(self.spec).__await__()


class WorkflowRuntime:
    """Run-scoped primitive implementation with deterministic admission."""

    def __init__(
        self,
        *,
        child_runner: ChildRunner,
        phases: Sequence[str] = (),
        limits: WorkflowLimits | None = None,
        resume_entries: Sequence[ResumeEntry] = (),
        nested_runner: NestedRunner | None = None,
        nesting_depth: int = 0,
        budget: OutputTokenBudget | None = None,
        phase_callback: Callable[[str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._child_runner = child_runner
        self._known_phases = frozenset(phases)
        self._limits = limits or WorkflowLimits()
        self._resume_entries = tuple(resume_entries)
        self._resume_enabled = bool(resume_entries)
        self._reserved_calls: list[AgentCallSpec] = []
        self._resume_pending_terminals: set[int] = set()
        self._resume_released_starts: set[int] = set()
        self._resume_terminal_condition = asyncio.Condition()
        self._nested_runner = nested_runner
        self._nesting_depth = nesting_depth
        self._semaphore = asyncio.Semaphore(self._limits.max_concurrency)
        self._dispatch_condition = asyncio.Condition()
        self._next_dispatch_ordinal = 0
        self._next_start_ordinal = 0
        self._next_terminal_ordinal = (
            max(
                (entry.terminal_ordinal for entry in self._resume_entries),
                default=-1,
            )
            + 1
        )
        self._resume_previous_key = "v2"
        self._paused = asyncio.Event()
        self._paused.set()
        self._stopped = False
        self.current_phase: str | None = None
        self.logs: list[str] = []
        self.completions: list[AgentCompletion] = []
        self.budget = budget or OutputTokenBudget()
        self._phase_callback = phase_callback
        self._log_callback = log_callback

    def agent(
        self,
        prompt: str,
        *,
        label: str | None = None,
        phase: str | None = None,
        schema: Mapping[str, Any] | None = None,
        model: str | None = None,
        effort: str | None = None,
        isolation: str | None = None,
        agent_type: str | None = None,
    ) -> AgentCall:
        """Reserve a logical Agent call synchronously and return its awaitable."""

        if self._next_start_ordinal >= self._limits.max_agents:
            raise ValueError(
                f"Workflow Agent limit exceeded ({self._limits.max_agents}; upstream 1000)"
            )
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("agent prompt must be a non-empty string")
        resolved_phase = phase if phase is not None else self.current_phase
        if (
            resolved_phase is not None
            and self._known_phases
            and resolved_phase not in self._known_phases
        ):
            raise ValueError(f"unknown Workflow phase: {resolved_phase}")
        options = {
            "schema": schema,
            "model": model,
            "effort": effort,
            "isolation": isolation,
            "agentType": agent_type,
        }
        resume_key = chained_resume_key(self._resume_previous_key, prompt, options)
        self._resume_previous_key = resume_key
        ordinal = self._next_start_ordinal
        self._next_start_ordinal += 1
        spec = AgentCallSpec(
            prompt=prompt,
            start_ordinal=ordinal,
            resume_key=resume_key,
            label=label,
            phase=resolved_phase,
            schema=schema,
            model=model,
            effort=effort,
            isolation=isolation,
            agent_type=agent_type,
        )
        self._reserved_calls.append(spec)
        return AgentCall(self, spec)

    async def parallel(self, thunks: Sequence[Callable[[], Any]]) -> list[Any]:
        if len(thunks) > self._limits.max_items:
            raise ValueError(
                f"Workflow items limit exceeded ({self._limits.max_items}; upstream 4096)"
            )
        awaitables: list[Awaitable[Any]] = []
        for thunk in thunks:
            if inspect.iscoroutinefunction(thunk):
                raise ValueError("parallel requires a synchronous thunk")
            try:
                value = thunk()
            except Exception:
                value = None
            if not inspect.isawaitable(value):

                async def immediate(item=value):  # noqa: ANN202
                    return item

                value = immediate()
            awaitables.append(value)
        return list(
            await asyncio.gather(*(_none_on_error(item) for item in awaitables))
        )

    async def pipeline(
        self, items: Sequence[Any], *stages: Callable[..., Any]
    ) -> list[Any]:
        if len(items) > self._limits.max_items:
            raise ValueError(
                f"Workflow items limit exceeded ({self._limits.max_items}; upstream 4096)"
            )
        if not stages:
            return _json_clone(list(items))
        first_values: list[Any] = []
        for index, item in enumerate(items):
            try:
                first_values.append(stage_call(stages[0], item, item, index))
            except Exception:
                first_values.append(None)

        async def drive(index: int, original: Any, first: Any) -> Any:
            previous = await _none_on_error(_as_awaitable(first))
            if previous is None:
                return None
            for stage in stages[1:]:
                try:
                    current = stage_call(stage, previous, original, index)
                except Exception:
                    return None
                previous = await _none_on_error(_as_awaitable(current))
                if previous is None:
                    return None
            return previous

        return list(
            await asyncio.gather(
                *(
                    drive(index, item, first_values[index])
                    for index, item in enumerate(items)
                )
            )
        )

    async def workflow(
        self, name_or_ref: str | Mapping[str, Any], args: Any = None
    ) -> Any:
        if self._nesting_depth >= 1:
            raise ValueError("Workflow nesting is limited to one level")
        if self._nested_runner is None:
            raise ValueError("nested Workflow runner is not configured")
        self._nesting_depth += 1
        try:
            return await self._nested_runner(name_or_ref, _json_clone(args), self)
        finally:
            self._nesting_depth -= 1

    def phase(self, title: str) -> None:
        if self._known_phases and title not in self._known_phases:
            raise ValueError(f"unknown Workflow phase: {title}")
        self.current_phase = title
        if self._phase_callback is not None:
            self._phase_callback(title)

    def include_phases(self, titles: Sequence[str]) -> None:
        """Add declared phase names from a one-level nested Workflow."""

        self._known_phases = self._known_phases.union(titles)

    def log(self, message: str) -> None:
        rendered = str(message)
        self.logs.append(rendered)
        if self._log_callback is not None:
            self._log_callback(rendered)

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()

    def stop(self) -> None:
        self._stopped = True
        self._paused.set()

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    async def checkpoint(self) -> None:
        if self._stopped:
            raise WorkflowStopped()
        await self._paused.wait()
        if self._stopped:
            raise WorkflowStopped()

    async def _run_call(self, spec: AgentCallSpec) -> Any:
        await self.checkpoint()
        cached: ResumeEntry | None = None
        if self._resume_enabled and spec.start_ordinal < len(self._resume_entries):
            candidate = self._resume_entries[spec.start_ordinal]
            if candidate.key == spec.resume_key:
                cached = candidate
            else:
                self._resume_enabled = False
        else:
            self._resume_enabled = False

        async with self._dispatch_condition:
            await self._dispatch_condition.wait_for(
                lambda: spec.start_ordinal == self._next_dispatch_ordinal
            )
            self._next_dispatch_ordinal += 1
            self._dispatch_condition.notify_all()

        if cached is not None:
            async with self._resume_terminal_condition:
                self._refresh_resume_pending_terminals()
                await self._resume_terminal_condition.wait_for(
                    lambda: (
                        cached.terminal_ordinal == min(self._resume_pending_terminals)
                    )
                )
                result = _json_clone(cached.result)
                self.completions.append(
                    AgentCompletion(
                        call=spec,
                        result=result,
                        terminal_ordinal=cached.terminal_ordinal,
                        replayed=True,
                    )
                )
                self._resume_pending_terminals.remove(cached.terminal_ordinal)
                self._resume_released_starts.add(spec.start_ordinal)
                self._resume_terminal_condition.notify_all()
            return result
        async with self._semaphore:
            await self.checkpoint()
            if self.budget.remaining() == 0:
                raise RuntimeError(
                    "Workflow output token budget exhausted before Agent dispatch"
                )
            try:
                result = await self._child_runner(spec)
            except (Exception, asyncio.CancelledError):
                result = None
        result = _json_clone(result)
        terminal_ordinal = self._next_terminal_ordinal
        self._next_terminal_ordinal += 1
        self.completions.append(
            AgentCompletion(
                call=spec,
                result=result,
                terminal_ordinal=terminal_ordinal,
                replayed=False,
            )
        )
        return result

    def _refresh_resume_pending_terminals(self) -> None:
        for spec in self._reserved_calls:
            if spec.start_ordinal in self._resume_released_starts:
                continue
            if spec.start_ordinal >= len(self._resume_entries):
                break
            entry = self._resume_entries[spec.start_ordinal]
            if entry.key != spec.resume_key:
                break
            self._resume_pending_terminals.add(entry.terminal_ordinal)


def stage_call(
    stage: Callable[..., Any], previous: Any, original: Any, index: int
) -> Any:
    if inspect.iscoroutinefunction(stage):
        raise ValueError("pipeline requires synchronous stage functions")
    return stage(previous, original, index)


async def _none_on_error(awaitable: Awaitable[Any]) -> Any:
    try:
        return await awaitable
    except (Exception, asyncio.CancelledError):
        return None


def _as_awaitable(value: Any) -> Awaitable[Any]:
    if inspect.isawaitable(value):
        return value

    async def immediate() -> Any:
        return value

    return immediate()


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Exception": Exception,
    "RuntimeError": RuntimeError,
    "ValueError": ValueError,
}


async def execute_workflow(
    compiled: CompiledWorkflow,
    *,
    args: Any,
    runtime: WorkflowRuntime | None = None,
) -> WorkflowExecutionResult:
    """Execute compiled Python in restricted globals and classify top-level status."""

    if runtime is None:

        async def no_child(_call: AgentCallSpec) -> Any:
            raise RuntimeError("Workflow has no child runner")

        runtime = WorkflowRuntime(
            child_runner=no_child,
            phases=[phase.title for phase in compiled.meta.phases],
        )

    async def checkpoint_await(awaitable: Awaitable[Any]) -> Any:
        await runtime.checkpoint()
        return await awaitable

    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "__workflow_checkpoint__": runtime.checkpoint,
        "__workflow_checkpoint_await__": checkpoint_await,
        "agent": runtime.agent,
        "parallel": runtime.parallel,
        "pipeline": runtime.pipeline,
        "workflow": runtime.workflow,
        "phase": runtime.phase,
        "log": runtime.log,
        "args": _json_clone(args),
        "budget": runtime.budget,
    }
    try:
        exec(compiled.code, namespace, namespace)
        result = await namespace["main"]()
        if runtime.is_stopped:
            return WorkflowExecutionResult(status=WorkflowStatus.STOPPED, result=result)
        return WorkflowExecutionResult(
            status=WorkflowStatus.COMPLETED,
            result=_json_clone(result),
        )
    except WorkflowStopped:
        return WorkflowExecutionResult(status=WorkflowStatus.STOPPED)
    except Exception as exc:
        return WorkflowExecutionResult(status=WorkflowStatus.FAILED, error=str(exc))
