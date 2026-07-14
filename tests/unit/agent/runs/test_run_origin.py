"""Unit tests for the public run-origin schema."""

from agent.core.runs.origin import RunOrigin
from agent.core.runs.registry import RunRecord, RunStatus


def test_run_origin_enum_values() -> None:
    assert RunOrigin.USER == "user"
    assert RunOrigin.BACKGROUND_TASK == "background_task"
    assert RunOrigin.HEARTBEAT == "heartbeat"


def test_run_record_defaults() -> None:
    record = RunRecord(
        run_id="run_1",
        session_id="sess_1",
        status=RunStatus.QUEUED,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    assert record.origin is RunOrigin.USER
    assert record.source_task_id is None


def test_run_record_explicit_origin() -> None:
    record = RunRecord(
        run_id="run_1",
        session_id="sess_1",
        status=RunStatus.QUEUED,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        origin=RunOrigin.BACKGROUND_TASK,
        source_task_id="task_123",
    )
    assert record.origin is RunOrigin.BACKGROUND_TASK
    assert record.source_task_id == "task_123"
