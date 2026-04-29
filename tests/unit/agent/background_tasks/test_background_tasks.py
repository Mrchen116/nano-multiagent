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
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
    )
    updated = reg.mark_running("b1")
    assert updated.status == BackgroundTaskStatus.RUNNING
    assert updated.started_at is not None
    assert reg.get("b1").status == BackgroundTaskStatus.RUNNING  # type: ignore[union-attr]


def test_complete_transitions_from_running() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
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
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
    )
    reg.mark_running("b1")
    updated = reg.fail("b1", error="boom")
    assert updated.status == BackgroundTaskStatus.FAILED
    assert updated.error == "boom"


def test_kill_transitions_from_running() -> None:
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
    )
    reg.mark_running("b1")
    updated = reg.kill("b1", reason="user_stopped")
    assert updated.status == BackgroundTaskStatus.KILLED
    assert updated.error == "user_stopped"


def test_terminal_state_is_idempotent() -> None:
    """Terminal transitions are no-ops to prevent races with task_stop."""
    reg = BackgroundTaskRegistry()
    reg.register_bash(
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
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
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
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
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
    )
    reg.mark_running("b1")
    reg.complete("b1")
    assert reg.request_stop("b1") is False


def test_request_stop_on_missing_task_returns_false() -> None:
    reg = BackgroundTaskRegistry()
    assert reg.request_stop("b-missing") is False


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
        return [r for r in self.records.values() if r.status not in {"completed", "failed", "killed"}]


def test_registry_persists_via_store() -> None:
    store = _FakeStore()
    reg = BackgroundTaskRegistry(store=store)
    reg.register_bash(
        task_id="b1", parent_session_id="s1", description="d", command="c", output_file="o"
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
