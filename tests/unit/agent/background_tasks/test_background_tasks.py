"""Tests for agent.core.background_tasks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

import pytest

from agent.core.background_tasks.ids import generate_agent_id, generate_bash_task_id
from agent.core.background_tasks.interfaces import BackgroundTaskStore
from agent.core.background_tasks.models import (
    BackgroundTaskRecord,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from agent.core.background_tasks.notifications import (
    BACKGROUND_TASK_PROMPT_BLOCK,
    build_task_notification_xml,
)
from agent.core.background_tasks.registry import BackgroundTaskRegistry


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def test_generate_agent_id_format() -> None:
    agent_id = generate_agent_id()
    assert agent_id.startswith("a")
    assert len(agent_id) == 17  # 'a' + 16 hex chars
    assert all(c in "0123456789abcdef" for c in agent_id[1:])


def test_generate_bash_task_id_format() -> None:
    task_id = generate_bash_task_id()
    assert task_id.startswith("b")
    assert len(task_id) == 17  # 'b' + 16 hex chars
    assert all(c in "0123456789abcdef" for c in task_id[1:])


# ---------------------------------------------------------------------------
# Registry state transitions
# ---------------------------------------------------------------------------


def test_register_subagent_defaults_to_queued() -> None:
    reg = BackgroundTaskRegistry()
    record = reg.register_subagent(
        task_id="a1234567890abcdef",
        parent_session_id="sess-1",
        agent_id="a1234567890abcdef",
        agent_session_id="sub-1",
        description="test agent",
        prompt="do thing",
        agent_type="explore",
        output_file="/tmp/out.jsonl",
    )
    assert record.status == BackgroundTaskStatus.QUEUED
    assert record.task_type == BackgroundTaskType.SUBAGENT
    assert reg.get(record.task_id) is record


def test_register_bash_defaults_to_queued() -> None:
    reg = BackgroundTaskRegistry()
    record = reg.register_bash(
        task_id="b1234567890abcdef",
        parent_session_id="sess-1",
        description="run tests",
        command="pytest",
        output_file="/tmp/out.output",
    )
    assert record.status == BackgroundTaskStatus.QUEUED
    assert record.task_type == BackgroundTaskType.BASH


def test_mark_running_transitions_from_queued() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    updated = reg.mark_running("b1")
    assert updated.status == BackgroundTaskStatus.RUNNING
    assert updated.started_at is not None
    assert reg.get("b1").status == BackgroundTaskStatus.RUNNING  # type: ignore[union-attr]


def test_complete_transitions_from_running() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")
    updated = reg.complete("b1", result_text="ok", duration_ms=1000, tool_use_count=3)
    assert updated.status == BackgroundTaskStatus.COMPLETED
    assert updated.result_text == "ok"
    assert updated.duration_ms == 1000
    assert updated.tool_use_count == 3


def test_fail_transitions_from_running() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")
    updated = reg.fail("b1", error="boom")
    assert updated.status == BackgroundTaskStatus.FAILED
    assert updated.error == "boom"


def test_kill_transitions_from_running() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")
    updated = reg.kill("b1", reason="user_stopped")
    assert updated.status == BackgroundTaskStatus.KILLED
    assert updated.error == "user_stopped"


def test_terminal_state_is_idempotent() -> None:
    """Terminal transitions are no-ops to prevent races with task_stop."""
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")
    reg.complete("b1")

    # Subsequent transitions are silently ignored.
    reg.fail("b1", error="late")
    reg.kill("b1")

    record = reg.get("b1")
    assert record is not None
    assert record.status == BackgroundTaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Pending messages
# ---------------------------------------------------------------------------


def test_enqueue_and_drain_agent_messages() -> None:
    reg = BackgroundTaskRegistry()
    reg.enqueue_agent_message("a1", "hello")
    reg.enqueue_agent_message("a1", "world")
    assert reg.drain_agent_messages("a1") == ("hello", "world")
    assert reg.drain_agent_messages("a1") == ()


# ---------------------------------------------------------------------------
# Stop handles
# ---------------------------------------------------------------------------


def test_request_stop_invokes_handle() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")

    stopped = []

    class _FakeHandle:
        def stop(self) -> None:
            stopped.append(True)

    reg.set_stop_handle("b1", _FakeHandle())  # type: ignore[arg-type]
    assert reg.request_stop("b1") is True
    assert stopped == [True]


def test_request_stop_on_terminal_returns_false() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    reg.mark_running("b1")
    reg.complete("b1")
    assert reg.request_stop("b1") is False


def test_request_stop_on_missing_task_returns_false() -> None:
    reg = BackgroundTaskRegistry()
    assert reg.request_stop("b-missing") is False


# ---------------------------------------------------------------------------
# Foreground stop-by-session (bugfix-417-M5 / #114)
# ---------------------------------------------------------------------------


class _RecordingHandle:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def test_stop_foreground_for_session_kills_only_foreground_tasks() -> None:
    """interrupt/cancel must kill the in-flight FOREGROUND tool's subprocess but
    leave user-launched background tasks (run_background) running (#114)."""
    reg = BackgroundTaskRegistry()
    # Foreground bash blocking the active run.
    reg.register_bash(
        task_id="fg",
        parent_session_id="s1",
        description="d",
        command="sleep 60",
        output_file="o",
    )
    reg.mark_running("fg")
    fg_handle = _RecordingHandle()
    reg.set_stop_handle("fg", fg_handle, foreground=True)  # type: ignore[arg-type]

    # Background bash explicitly detached by the user — must NOT be touched.
    reg.register_bash(
        task_id="bg",
        parent_session_id="s1",
        description="d",
        command="sleep 999",
        output_file="o",
    )
    reg.mark_running("bg")
    bg_handle = _RecordingHandle()
    reg.set_stop_handle("bg", bg_handle, foreground=False)  # type: ignore[arg-type]

    stopped_any = reg.stop_foreground_for_session("s1")

    assert stopped_any is True
    assert fg_handle.stopped is True
    assert bg_handle.stopped is False


def test_stop_foreground_for_session_scopes_to_session() -> None:
    """A foreground task in another session must not be stopped."""
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="fg-other",
        parent_session_id="other",
        description="d",
        command="sleep 60",
        output_file="o",
    )
    reg.mark_running("fg-other")
    other_handle = _RecordingHandle()
    reg.set_stop_handle("fg-other", other_handle, foreground=True)  # type: ignore[arg-type]

    assert reg.stop_foreground_for_session("s1") is False
    assert other_handle.stopped is False


def test_stop_foreground_for_session_ignores_terminal_tasks() -> None:
    """A foreground task that already finished must not be re-stopped."""
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="fg",
        parent_session_id="s1",
        description="d",
        command="sleep 60",
        output_file="o",
    )
    reg.mark_running("fg")
    handle = _RecordingHandle()
    reg.set_stop_handle("fg", handle, foreground=True)  # type: ignore[arg-type]
    reg.complete("fg")

    assert reg.stop_foreground_for_session("s1") is False
    assert handle.stopped is False


def test_stop_foreground_for_session_no_tasks_returns_false() -> None:
    reg = BackgroundTaskRegistry()
    assert reg.stop_foreground_for_session("s1") is False


# ---------------------------------------------------------------------------
# Store integration
# ---------------------------------------------------------------------------


class _FakeStore:
    def __init__(self) -> None:
        self.records: dict[str, BackgroundTaskRecord] = {}

    def insert(self, record: BackgroundTaskRecord) -> None:
        self.records[record.task_id] = record

    def update(self, record: BackgroundTaskRecord) -> None:
        self.records[record.task_id] = record

    def get(self, task_id: str) -> BackgroundTaskRecord | None:
        return self.records.get(task_id)

    def list_non_terminal(self) -> Sequence[BackgroundTaskRecord]:
        return [
            r
            for r in self.records.values()
            if r.status not in {"completed", "failed", "killed"}
        ]


def test_registry_persists_via_store() -> None:
    store = _FakeStore()
    reg = BackgroundTaskRegistry(store=store)
    reg.register_bash(
        task_id="b1",
        parent_session_id="s1",
        description="d",
        command="c",
        output_file="o",
    )
    assert "b1" in store.records
    reg.mark_running("b1")
    assert store.records["b1"].status == BackgroundTaskStatus.RUNNING


# ---------------------------------------------------------------------------
# Notification XML
# ---------------------------------------------------------------------------


def test_build_notification_for_subagent_completed() -> None:
    record = BackgroundTaskRecord(
        task_id="a1",
        task_type=BackgroundTaskType.SUBAGENT,
        parent_session_id="s1",
        agent_id="a1",
        description="research loop",
        status=BackgroundTaskStatus.COMPLETED,
        output_file="/tmp/out.jsonl",
        result_text="found 3 files",
        usage={"total_tokens": 42},
        tool_use_count=5,
        duration_ms=1200,
    )
    xml = build_task_notification_xml(record)
    assert "<task-notification>" in xml
    assert "<task-id>a1</task-id>" in xml
    assert "<agent-id>a1</agent-id>" in xml
    assert "<output-file>/tmp/out.jsonl</output-file>" in xml
    assert "<status>completed</status>" in xml
    assert 'Agent "research loop" completed' in xml
    assert "<result>found 3 files</result>" in xml
    assert "<total-tokens>42</total-tokens>" in xml
    assert "<tool-uses>5</tool-uses>" in xml
    assert "<duration-ms>1200</duration-ms>" in xml
    assert "</task-notification>" in xml


def test_build_notification_for_bash_failed() -> None:
    record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="s1",
        description="run tests",
        status=BackgroundTaskStatus.FAILED,
        output_file="/tmp/out.output",
        error="exit code 1",
        exit_code=1,
    )
    xml = build_task_notification_xml(record)
    assert "<task-id>b1</task-id>" in xml
    assert "<agent-id>" not in xml
    assert "<status>failed</status>" in xml
    assert 'Command "run tests" failed with exit code 1' in xml
    assert "<error>exit code 1</error>" in xml


def test_build_notification_escapes_xml() -> None:
    record = BackgroundTaskRecord(
        task_id="a1",
        task_type=BackgroundTaskType.SUBAGENT,
        parent_session_id="s1",
        agent_id="a1",
        description="research <loop>",
        status=BackgroundTaskStatus.COMPLETED,
        output_file="/tmp/out.jsonl",
        result_text="foo & bar",
    )
    xml = build_task_notification_xml(record)
    assert "research &lt;loop&gt;" in xml
    assert "foo &amp; bar" in xml


# ---------------------------------------------------------------------------
# Prompt block
# ---------------------------------------------------------------------------


def test_prompt_block_contains_rules() -> None:
    assert "<task-notification>" in BACKGROUND_TASK_PROMPT_BLOCK
    assert "not new user requests" in BACKGROUND_TASK_PROMPT_BLOCK
    assert "Do not thank them" in BACKGROUND_TASK_PROMPT_BLOCK


# ---------------------------------------------------------------------------
# workspace_root 携带（bugfix-404-M1 回归）
# ---------------------------------------------------------------------------


def test_register_bash_carries_workspace_root() -> None:
    """register_bash 必须把 workspace_root 存进 record。"""
    reg = BackgroundTaskRegistry()
    record = reg.register_bash(
        task_id="b1234567890abcdef",
        parent_session_id="sess-1",
        description="run tests",
        command="pytest",
        output_file="/tmp/out.output",
        workspace_root="/custom/workspace",
    )
    assert record.workspace_root == "/custom/workspace"


def test_register_subagent_carries_workspace_root() -> None:
    """register_subagent 必须把 workspace_root 存进 record。"""
    reg = BackgroundTaskRegistry()
    record = reg.register_subagent(
        task_id="a1234567890abcdef",
        parent_session_id="sess-1",
        agent_id="a1234567890abcdef",
        agent_session_id="sub-1",
        description="test agent",
        prompt="do thing",
        agent_type="explore",
        output_file="/tmp/out.jsonl",
        workspace_root="/custom/workspace",
    )
    assert record.workspace_root == "/custom/workspace"


def test_register_bash_workspace_root_defaults_none() -> None:
    """不传 workspace_root 时默认 None，向后兼容。"""
    reg = BackgroundTaskRegistry()
    record = reg.register_bash(
        task_id="b1234567890abcdef",
        parent_session_id="sess-1",
        description="run tests",
        command="pytest",
        output_file="/tmp/out.output",
    )
    assert record.workspace_root is None


# ---------------------------------------------------------------------------
# BashTool / AgentTool 注册时传入 workspace_root（bugfix-404-M1 R2 回归）
# ---------------------------------------------------------------------------


def _make_fake_wiring(registry: BackgroundTaskRegistry) -> Any:
    """构造最小 BackgroundTaskWiring stub，让 BashTool._run_background 能运行。"""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock
    from agent.platform.background_tasks.file_output import BashFileOutput

    tmpdir = tempfile.mkdtemp()
    output = BashFileOutput(workspace_root=Path(tmpdir))

    runner_stub = MagicMock()

    class _FakeStopper:
        def stop(self) -> None:
            pass

    runner_stub.start.return_value = _FakeStopper()

    wiring = MagicMock()
    wiring.registry = registry
    wiring.output = output
    wiring.bash_runner = runner_stub
    return wiring


# ---------------------------------------------------------------------------
# _deliver_notification 投递逻辑（bugfix-404-M1 R3 回归）
# ---------------------------------------------------------------------------


def _make_runs_registry_stub(
    *,
    session_exists: bool = True,
    session_kind: str | None = None,
    active_run_id: str | None = None,
    submit_raises: Exception | None = None,
) -> Any:
    """构造最小 RunsRegistry stub。"""
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from agent.core.session.models import Session

    registry_stub = MagicMock()
    registry_stub.get_active_run_id.return_value = active_run_id

    if session_exists:
        session = Session(
            session_id="parent-sess",
            status="active",
            created_at="2026-01-01T00:00:00",
            workspace_root=Path("/custom/workspace"),
            metadata={"kind": session_kind} if session_kind else {},
        )
    else:
        session = None

    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    registry_stub._session_manager = session_manager

    if submit_raises:
        registry_stub.submit.side_effect = submit_raises
    else:
        submit_record = MagicMock()
        registry_stub.submit.return_value = submit_record

    return registry_stub


def test_deliver_notification_skips_subagent_parent_session() -> None:
    """parent 为 subagent session（kind='subagent'）时，跳过，不调用 submit。"""
    from agent.core.background_tasks.models import (
        BackgroundTaskRecord,
        BackgroundTaskType,
        BackgroundTaskStatus,
    )
    from agent.platform.background_tasks.wiring import _deliver_notification

    runs_registry = _make_runs_registry_stub(
        session_exists=True,
        session_kind="subagent",  # subagent session
        active_run_id=None,
    )

    record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="parent-sess",
        status=BackgroundTaskStatus.COMPLETED,
        output_file="/tmp/out.output",
        workspace_root="/custom/workspace",
    )

    _deliver_notification(record, runs_registry, runs_registry._session_manager)

    runs_registry.submit.assert_not_called()


def test_deliver_notification_logs_error_on_submit_failure() -> None:
    """submit 失败（如 ValueError: session does not exist）时，触发 log_error，不吞掉。"""
    from agent.core.background_tasks.models import (
        BackgroundTaskRecord,
        BackgroundTaskType,
        BackgroundTaskStatus,
    )
    from agent.platform.background_tasks.wiring import _deliver_notification
    import agent.core.observability.logger as logger_module

    runs_registry = _make_runs_registry_stub(
        session_exists=True,
        session_kind=None,
        active_run_id=None,
        submit_raises=ValueError("session does not exist: parent-sess"),
    )

    record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="parent-sess",
        status=BackgroundTaskStatus.COMPLETED,
        output_file="/tmp/out.output",
        workspace_root="/custom/workspace",
    )

    logged_errors = []
    original_log_error = logger_module.log_error

    def _capture_log_error(event: str, **kwargs: Any) -> None:
        logged_errors.append((event, kwargs))

    import unittest.mock

    with unittest.mock.patch.object(logger_module, "log_error", _capture_log_error):
        _deliver_notification(record, runs_registry, runs_registry._session_manager)

    assert any(
        "notify" in event or "deliver" in event or "background" in event
        for event, _ in logged_errors
    ), f"Expected a log_error call, got: {logged_errors}"


def test_notifying_store_skips_deliver_when_notified_true() -> None:
    """notified=True（前台完成已抑制）时 _NotifyingStore.update 不调用 _deliver_notification（#19 不回归）。"""
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from agent.core.background_tasks.models import (
        BackgroundTaskRecord,
        BackgroundTaskType,
        BackgroundTaskStatus,
    )
    from agent.platform.background_tasks.wiring import _wire_notification_callbacks
    from agent.core.background_tasks.registry import BackgroundTaskRegistry
    from agent.platform.background_tasks.task_store import InMemoryTaskStore

    delivered: list[Any] = []

    runs_registry = MagicMock()

    store = InMemoryTaskStore()
    reg = BackgroundTaskRegistry(store=store)
    _wire_notification_callbacks(reg, runs_registry)

    record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="parent-sess",
        status=BackgroundTaskStatus.QUEUED,
        output_file="/tmp/out.output",
        workspace_root="/custom/workspace",
    )
    store.insert(record)

    # 模拟前台完成：notified=True
    completed_record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="parent-sess",
        status=BackgroundTaskStatus.COMPLETED,
        output_file="/tmp/out.output",
        workspace_root="/custom/workspace",
        notified=True,
    )

    import agent.platform.background_tasks.wiring as wiring_mod

    with patch.object(wiring_mod, "_deliver_notification") as mock_deliver:
        reg._store.update(completed_record)  # type: ignore[attr-defined]
        mock_deliver.assert_not_called()


def test_agent_tool_run_background_passes_workspace_root_to_registry() -> None:
    """AgentTool._run_background 调用 register_subagent 时必须传 workspace_root。"""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock

    from agent.platform.tools.builtins.agent import AgentTool

    reg = BackgroundTaskRegistry()

    workspace = Path(tempfile.mkdtemp())

    # 构造 wiring stub
    wiring = MagicMock()
    wiring.registry = reg

    class _FakeStopper:
        def stop(self) -> None:
            pass

    wiring.subagent_runner.start.return_value = _FakeStopper()

    # runtime stub：create_session 返回带 session_id 的对象
    runtime_stub = MagicMock()
    session_stub = MagicMock()
    session_stub.session_id = "sub-sess-1"

    import asyncio

    async def _create_session(**kwargs: Any) -> Any:
        return session_stub

    runtime_stub.create_session = _create_session

    store_stub = MagicMock()
    store_stub.resolve_path.return_value = workspace / "out.jsonl"
    runtime_stub._session_manager.store = store_stub

    tool = AgentTool(runtime=runtime_stub, wiring=wiring)

    ctx = MagicMock()
    ctx.session_id = "parent-sess"
    ctx.repo_root = workspace
    ctx.cwd = workspace

    args = {
        "description": "test agent",
        "prompt": "do something",
        "subagent_type": "explore",
        "load_skills": [],
    }

    tool._run_background(args=args, ctx=ctx)

    # 取到注册的 record，断言 workspace_root 传入
    records = list(reg._records.values())
    assert len(records) == 1
    assert records[0].workspace_root == str(workspace)
