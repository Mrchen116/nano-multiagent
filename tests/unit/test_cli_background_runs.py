"""Tests for CLI background-origin run event processing."""

from coding_cli.events.background_runs import BackgroundRunEventProcessor
from coding_cli.events.background_runs import format_origin_header


def test_format_origin_header_background_task() -> None:
    assert (
        format_origin_header({"event": "run_status", "origin": "background_task", "source_task_id": "t1"})
        == "── background wake (task_id=t1) ──"
    )


def test_format_origin_header_heartbeat() -> None:
    assert format_origin_header({"event": "run_status", "origin": "heartbeat"}) == "── heartbeat ──"


def test_format_origin_header_user_returns_none() -> None:
    assert format_origin_header({"event": "run_status", "origin": "user"}) is None


def test_processor_buffers_events_until_origin_is_known() -> None:
    processor = BackgroundRunEventProcessor()

    assert processor.process({"event": "assistant_message", "run_id": "run_bg", "content": "done"}) == []

    assert processor.process(
        {
            "event": "run_status",
            "run_id": "run_bg",
            "origin": "background_task",
            "source_task_id": "task_1",
        }
    ) == [
        "── background wake (task_id=task_1) ──",
        "> done",
    ]


def test_processor_preserves_background_run_state_across_drain_phases() -> None:
    processor = BackgroundRunEventProcessor()

    assert processor.process(
        {
            "event": "run_status",
            "run_id": "run_bg",
            "origin": "background_task",
            "source_task_id": "task_1",
        }
    ) == ["── background wake (task_id=task_1) ──"]

    assert processor.process({"event": "assistant_message", "run_id": "run_bg", "content": "line 1\nline 2\n"}) == [
        "> line 1",
        "> line 2",
    ]
    assert processor.process({"event": "tool_start", "run_id": "run_bg", "name": "read"}) == ["  ▸ read"]
    assert processor.process({"event": "tool_end", "run_id": "run_bg", "name": "read", "duration_ms": 12}) == [
        "  ✓ read (12ms)"
    ]


def test_processor_ignores_user_origin_events() -> None:
    processor = BackgroundRunEventProcessor()

    assert processor.process({"event": "run_status", "run_id": "run_user", "origin": "user"}) == []
    assert processor.process({"event": "assistant_message", "run_id": "run_user", "content": "user run"}) == []
