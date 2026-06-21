"""Tests for BashTool background/foreground paths."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.core.background_tasks.foreground_registry import ForegroundExecutionRegistry
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool


class _FakeStopper:
    def stop(self) -> None:
        pass


class _FakeBashRunner:
    """Fake bash runner that completes quickly or slowly based on command."""

    def __init__(
        self,
        *,
        delay: float = 0.0,
        exit_code: int = 0,
        fail_error: str | None = None,
    ) -> None:
        self._delay = delay
        self._exit_code = exit_code
        # When set, on_fail is called with this error string instead of the
        # exit-code message — used to simulate ShellRunner's timeout failure
        # ("timed out after Xs"), the production deadline path.
        self._fail_error = fail_error

    def start(self, *, command, cwd, output, task_id, timeout, on_complete, on_fail):
        def _worker() -> None:
            if self._delay > 0:
                time.sleep(self._delay)
            if self._fail_error is not None:
                on_fail(task_id=task_id, error=self._fail_error)
            elif self._exit_code == 0:
                on_complete(
                    task_id=task_id,
                    result_text=None,
                    usage=None,
                    duration_ms=int(self._delay * 1000),
                    tool_use_count=0,
                )
            else:
                on_fail(task_id=task_id, error=f"exit code {self._exit_code}")

        threading.Thread(target=_worker, daemon=True).start()
        return _FakeStopper()


class _FakeOutput:
    def __init__(self, tmpdir: str) -> None:
        self._tmpdir = tmpdir
        self._paths: dict[str, Path] = {}

    def open(self, parent_session_id: str, task_id: str) -> Path:
        path = Path(self._tmpdir) / "tasks" / parent_session_id / f"{task_id}.output"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(f"# Background task {task_id} — output will appear here\n")
        self._paths[task_id] = path
        return path

    def append(self, task_id: str, text: str, *, stream: str = "stdout") -> None:
        path = self._paths.get(task_id)
        if path is None:
            return
        with path.open("a", encoding="utf-8") as f:
            f.write(text)

    def flush(self, task_id: str) -> None:
        pass


def _make_tool(
    *,
    with_wiring: bool = True,
    runner_delay: float = 0.0,
    runner_exit: int = 0,
    runner_fail_error: str | None = None,
) -> BashTool:
    if not with_wiring:
        return BashTool()

    registry = BackgroundTaskRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _FakeBashRunner(
        delay=runner_delay, exit_code=runner_exit, fail_error=runner_fail_error
    )

    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    # bugfix-417-M7: foreground bash registers its killpg handle into the narrow
    # ForegroundExecutionRegistry, not the background registry. Use a real one (not a
    # MagicMock attribute) so register/unregister/stop_for_session behave for real.
    wiring.foreground_registry = ForegroundExecutionRegistry()

    return BashTool(wiring=wiring)


def _make_ctx(tmpdir: str, *, on_event=None) -> ToolContext:
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    safety = ToolSafety(repo_root=Path(tmpdir), config=ToolSafetyConfig())
    return ToolContext(
        repo_root=Path(tmpdir),
        cwd=Path(tmpdir),
        safety=safety,
        session_id="parent_1",
        execution_event_callback=on_event,
    )


# ------------------------------------------------------------------
# Background launch
# ------------------------------------------------------------------


def test_background_launch_returns_async_launched() -> None:
    tool = _make_tool()
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "echo hello",
                "description": "test bg",
                "run_in_background": True,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["task_id"].startswith("b")
        assert "output_file" in result
        assert result["description"] == "test bg"


# ------------------------------------------------------------------
# Foreground completion
# ------------------------------------------------------------------


def test_foreground_completes_within_budget() -> None:
    tool = _make_tool(runner_delay=0.0)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "echo hello",
                "run_in_background": False,
            },
            ctx,
        )
        assert result["exitCode"] == 0
        assert "stdout" in result


# ------------------------------------------------------------------
# Foreground auto-background
# ------------------------------------------------------------------


def test_foreground_auto_backgrounds_on_slow_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch budget to 0.1s so the test completes quickly.
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._DEFAULT_FOREGROUND_BUDGET", 0.1
    )
    tool = _make_tool(runner_delay=0.5)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "command": "sleep 20",
                "run_in_background": False,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["task_id"].startswith("b")
        assert "output_file" in result


# ------------------------------------------------------------------
# Foreground failure within budget
# ------------------------------------------------------------------


def test_foreground_fails_within_budget_raises_tool_error() -> None:
    tool = _make_tool(runner_delay=0.0, runner_exit=1)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="Command exited with code 1"):
            tool.run(
                {
                    "command": "false",
                    "run_in_background": False,
                },
                ctx,
            )


# ------------------------------------------------------------------
# bugfix-417-M5 (#114): interrupt reaps foreground + wakes the waiter promptly
# ------------------------------------------------------------------


class _NeverCompletingStopper:
    """Records that the runner-level stop (killpg) was requested."""

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _NeverCompletingRunner:
    """Runner whose command never completes on its own — only an external stop
    ends it (stands in for a long foreground `sleep`). The runner stopper does
    NOT call on_complete/on_fail (mirrors ShellRunner's silent `_stopped` path),
    so the only way the foreground waiter can return promptly is if the wrapped
    foreground stopper wakes completed_event itself (bugfix-417-M5)."""

    def __init__(self) -> None:
        self.stopper = _NeverCompletingStopper()

    def start(self, *, command, cwd, output, task_id, timeout, on_complete, on_fail):
        return self.stopper


def test_interrupt_wakes_foreground_waiter_promptly_no_thread_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A /stop on an in-flight foreground command must make _run_foreground return
    promptly — NOT linger on completed_event until the 120s budget. The runner's
    silent stop path never sets completed_event, so the foreground stopper wrapper
    must wake the waiter itself; otherwise this to_thread worker is leaked for the
    full budget (the subtlety the team lead flagged).

    bugfix-417-M7: the stop now arrives via ForegroundExecutionRegistry.stop_for_session
    (what the kernel injects as the RunsRegistry foreground stopper port), not the old
    BackgroundTaskRegistry.stop_foreground_for_session — the foreground command never
    enters the background registry at all."""
    # Keep the budget large so a "return promptly" assertion proves the wake came
    # from the stop, not from the budget expiring.
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._DEFAULT_FOREGROUND_BUDGET", 30.0
    )
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._FOREGROUND_HEARTBEAT_INTERVAL", 0.05
    )

    registry = BackgroundTaskRegistry()
    foreground_registry = ForegroundExecutionRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _NeverCompletingRunner()
    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    wiring.foreground_registry = foreground_registry
    tool = BashTool(wiring=wiring)

    ctx = _make_ctx(tmpdir)

    # Stop the in-flight foreground tool shortly after it starts, from another
    # thread (mirrors RunsRegistry.interrupt → foreground_stopper).
    def _interrupt_soon() -> None:
        time.sleep(0.3)
        foreground_registry.stop_for_session("parent_1")

    threading.Thread(target=_interrupt_soon, daemon=True).start()

    start = time.monotonic()
    result = tool.run(
        {"command": "sleep 30", "run_in_background": False},
        ctx,
    )
    elapsed = time.monotonic() - start

    # Returned promptly (well under the 30s budget) — no thread leak.
    assert elapsed < 5.0, f"foreground waiter lingered {elapsed:.1f}s after stop"
    # The runner-level killpg was requested.
    assert runner.stopper.stopped is True
    # The result is classified as interrupted (not a spurious failure/timeout).
    assert result.get("interrupted") is True
    assert result.get("reason_code") == "interrupted"


# ------------------------------------------------------------------
# bugfix-417-M7 (decision 12): foreground bash exits BackgroundTaskRegistry
# ------------------------------------------------------------------


def test_foreground_completion_does_not_enter_background_registry() -> None:
    """A foreground command that completes within budget must NOT leave a record in
    BackgroundTaskRegistry — it never registered there. This is the structural fix:
    with the task physically absent from the background registry, the _NotifyingStore
    has nothing to fire a <task-notification> for (dual-channel impossible)."""
    registry = BackgroundTaskRegistry()
    foreground_registry = ForegroundExecutionRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _FakeBashRunner(delay=0.0, exit_code=0)
    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    wiring.foreground_registry = foreground_registry
    tool = BashTool(wiring=wiring)

    ctx = _make_ctx(tmpdir)
    result = tool.run({"command": "echo hi", "run_in_background": False}, ctx)

    assert result["exitCode"] == 0
    # No background-task records were created for the foreground command — not just
    # "no non-terminal records" but ZERO records (the task never registered there).
    assert registry._records == {}  # type: ignore[attr-defined]
    # The foreground stopper was cleaned up (no stale handle to reap later).
    assert foreground_registry.stop_for_session("parent_1") is False


def test_foreground_failure_does_not_enter_background_registry() -> None:
    """Same structural guarantee on the failure path (the original on_fail-missing-
    notified=True dual-channel trigger): a foreground failure stays out of the
    background registry entirely."""
    registry = BackgroundTaskRegistry()
    foreground_registry = ForegroundExecutionRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _FakeBashRunner(delay=0.0, exit_code=1)
    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    wiring.foreground_registry = foreground_registry
    tool = BashTool(wiring=wiring)

    ctx = _make_ctx(tmpdir)
    with pytest.raises(ToolError):
        tool.run({"command": "false", "run_in_background": False}, ctx)

    assert registry._records == {}  # type: ignore[attr-defined]
    assert foreground_registry.stop_for_session("parent_1") is False


def test_auto_background_hands_off_into_background_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the foreground budget is exceeded, the task is explicitly handed off into
    BackgroundTaskRegistry (the single foreground→background transition) and the
    foreground registry no longer tracks it — so a subsequent completion notifies as
    a background task and a later /stop targets the background stopper."""
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._DEFAULT_FOREGROUND_BUDGET", 0.1
    )
    registry = BackgroundTaskRegistry()
    foreground_registry = ForegroundExecutionRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    # Completes after the (patched) budget so it auto-backgrounds, then finishes.
    runner = _FakeBashRunner(delay=0.4, exit_code=0)
    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    wiring.foreground_registry = foreground_registry
    tool = BashTool(wiring=wiring)

    ctx = _make_ctx(tmpdir)
    result = tool.run({"command": "sleep 20", "run_in_background": False}, ctx)

    assert result["status"] == "async_launched"
    task_id = result["task_id"]
    # The task is now owned by the background registry.
    record = registry.get(task_id)
    assert record is not None
    # Foreground registry released it on hand-off (no stale foreground stopper).
    assert foreground_registry.stop_for_session("parent_1") is False

    # Let the runner thread finish and fire the (now background) completion.
    time.sleep(0.6)
    final = registry.get(task_id)
    assert final is not None
    assert final.status == "completed"
    # A real background task must NOT be marked as already-notified (it must still
    # get its one <task-notification>): notified stays False on hand-off completion.
    assert final.notified is False


class _ControllableRunner:
    """Runner that fires its completion callback only when the test releases a gate —
    lets a test drive the exact race between 'foreground budget elapsed → hand-off'
    and 'command completed → callback fires'."""

    def __init__(self) -> None:
        self.stopper = _NeverCompletingStopper()
        self._gate = threading.Event()
        self._on_complete = None
        self._task_id = None

    def start(self, *, command, cwd, output, task_id, timeout, on_complete, on_fail):
        self._on_complete = on_complete
        self._task_id = task_id

        def _worker() -> None:
            self._gate.wait()
            on_complete(
                task_id=task_id,
                result_text=None,
                usage=None,
                duration_ms=0,
                tool_use_count=0,
            )

        threading.Thread(target=_worker, daemon=True).start()
        return self.stopper

    def fire_completion(self) -> None:
        self._gate.set()


def test_auto_background_handoff_race_with_completion_no_double_notify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The budget-elapsed hand-off and the runner's completion callback can race. The
    result must neither be lost nor double-delivered: exactly one terminal record,
    and after hand-off the completion notifies as a background task (notified False),
    never as a suppressed-foreground duplicate."""
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._DEFAULT_FOREGROUND_BUDGET", 0.15
    )
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._FOREGROUND_HEARTBEAT_INTERVAL", 0.05
    )
    registry = BackgroundTaskRegistry()
    foreground_registry = ForegroundExecutionRegistry()
    tmpdir = tempfile.mkdtemp()
    output = _FakeOutput(tmpdir)
    runner = _ControllableRunner()
    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner
    wiring.foreground_registry = foreground_registry
    tool = BashTool(wiring=wiring)

    ctx = _make_ctx(tmpdir)

    # Fire the completion right as the budget elapses, racing the hand-off.
    def _fire_at_budget() -> None:
        time.sleep(0.15)
        runner.fire_completion()

    threading.Thread(target=_fire_at_budget, daemon=True).start()

    result = tool.run({"command": "sleep 20", "run_in_background": False}, ctx)

    # Either it completed within budget (single tool-result, no record left) or it
    # auto-backgrounded (handed off, one background record). Both are correct; what
    # must NOT happen is two terminal transitions / a lost result.
    task_records = registry.list_non_terminal()
    assert task_records == []  # no task left dangling in non-terminal

    if result.get("status") == "async_launched":
        # Handed off: exactly one completed background record, notifiable once.
        record = registry.get(result["task_id"])
        assert record is not None
        # Give the worker a beat in case completion landed just after hand-off.
        for _ in range(20):
            if registry.get(result["task_id"]).status == "completed":
                break
            time.sleep(0.02)
        record = registry.get(result["task_id"])
        assert record.status == "completed"
        assert record.notified is False
    else:
        # Completed within budget: synchronous tool result, never in the registry.
        assert result["exitCode"] == 0
        assert registry.list_non_terminal() == []


# ------------------------------------------------------------------
# bugfix-417-M4 R2: foreground heartbeat polling + timeout reason_code
# ------------------------------------------------------------------


def test_foreground_emits_running_heartbeats_during_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """While the foreground command runs, _run_foreground must emit periodic
    phase:running execution events via ctx.emit_execution_event.

    This is the bash liveness source: M3's executor bridges ctx.emit_execution_event
    → run_coroutine_threadsafe → tool_execution_update → run_heartbeat → both
    watchdogs. Pre-fix _run_foreground just blocks on completed_event.wait with zero
    events → a silent long command produces no liveness → watchdog reaps the live run
    (bugfix-417 B1). Heartbeat interval is patched small so the test is fast.
    """
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._FOREGROUND_HEARTBEAT_INTERVAL", 0.1
    )
    # Command completes after ~0.45s → several heartbeat ticks at 0.1s interval,
    # but well within the 120s foreground budget (no auto-background).
    tool = _make_tool(runner_delay=0.45)
    events: list[dict] = []

    def _on_event(payload) -> None:
        events.append(dict(payload))

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir, on_event=_on_event)
        result = tool.run(
            {"command": "sleep 1", "run_in_background": False},
            ctx,
        )
        assert result["exitCode"] == 0
    running = [e for e in events if e.get("phase") == "running"]
    assert running, f"no phase:running heartbeat emitted; events={events}"


def test_foreground_timeout_within_budget_carries_tool_timeout_reason() -> None:
    """When the bash command hits its OWN deadline (ShellRunner on_fail 'timed out
    after Xs') within the foreground budget, the raised ToolError must carry
    details['reason_code']='tool_timeout' so IM renders the '执行超时' badge.

    Pre-fix the production _run_foreground failure path set no reason_code (only the
    dead _run_legacy_sync did) → C1: tool_call.reason=null in live.
    """
    tool = _make_tool(runner_delay=0.0, runner_fail_error="timed out after 5.0s")
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {"command": "sleep 200", "timeout": 5, "run_in_background": False},
                ctx,
            )
        assert exc_info.value.details.get("reason_code") == "tool_timeout", (
            f"expected tool_timeout reason_code, got {exc_info.value.details!r}"
        )


# ------------------------------------------------------------------
# No-wiring path removed (bugfix-417-M4 decision 8)
# ------------------------------------------------------------------


def test_foreground_without_wiring_raises_clear_error() -> None:
    """A BashTool built without wiring has no engine to run on — the dead no-wiring
    `_run_legacy_sync` path was deleted in bugfix-417-M4. Production always wires bash
    via build_kernel; a no-wiring construction must fail loudly rather than silently
    fall back to a parallel engine.
    """
    tool = _make_tool(with_wiring=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError, match="wiring is not configured"):
            tool.run(
                {"command": "echo hello", "run_in_background": False},
                ctx,
            )


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


def test_serialize_async_launched() -> None:
    tool = _make_tool()
    text = tool.serialize_result(
        {
            "status": "async_launched",
            "task_id": "b1234",
            "output_file": "/tmp/out.txt",
        }
    )
    assert "b1234" in text
    assert "/tmp/out.txt" in text


def test_serialize_completed() -> None:
    tool = _make_tool()
    text = tool.serialize_result(
        {
            "stdout": "hello world",
            "exitCode": 0,
        }
    )
    assert text == "hello world"


def test_serialize_no_output() -> None:
    tool = _make_tool()
    text = tool.serialize_result(
        {
            "stdout": "",
            "exitCode": 0,
        }
    )
    assert text == "(no output)"
