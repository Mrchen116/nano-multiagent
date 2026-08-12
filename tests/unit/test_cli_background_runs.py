"""Tests for CLI background-origin run event processing."""

import pytest

from coding_cli.events.background_runs import BackgroundRunEventProcessor
from coding_cli.events.background_runs import format_origin_header


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            {
                "event": "run_status",
                "origin": "background_task",
                "source_task_id": "t1",
            },
            "── background wake (task_id=t1) ──",
        ),
        ({"event": "run_status", "origin": "heartbeat"}, "── heartbeat ──"),
        ({"event": "run_status", "origin": "user"}, None),
    ],
)
def test_format_origin_header_distinguishes_background_runs(event, expected) -> None:
    assert format_origin_header(event) == expected


def test_processor_buffers_events_until_origin_is_known() -> None:
    processor = BackgroundRunEventProcessor()

    assert (
        processor.process(
            {"event": "assistant_message", "run_id": "run_bg", "content": "done"}
        )
        == []
    )

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

    assert processor.process(
        {
            "event": "assistant_message",
            "run_id": "run_bg",
            "content": "line 1\nline 2\n",
        }
    ) == [
        "> line 1",
        "> line 2",
    ]
    assert processor.process(
        {"event": "tool_start", "run_id": "run_bg", "name": "read"}
    ) == ["  ▸ read"]
    assert processor.process(
        {"event": "tool_end", "run_id": "run_bg", "name": "read", "duration_ms": 12}
    ) == ["  ✓ read (12ms)"]


def test_processor_ignores_user_origin_events() -> None:
    processor = BackgroundRunEventProcessor()

    assert (
        processor.process(
            {"event": "run_status", "run_id": "run_user", "origin": "user"}
        )
        == []
    )
    assert (
        processor.process(
            {"event": "assistant_message", "run_id": "run_user", "content": "user run"}
        )
        == []
    )


@pytest.mark.parametrize(
    ("reviewed_skills", "reviewed_memory", "subject"),
    [
        (True, False, "skills"),
        (False, True, "memory"),
        (True, True, "skills + memory"),
    ],
)
def test_processor_renders_flat_self_evolution_review_subject(
    reviewed_skills: bool, reviewed_memory: bool, subject: str
) -> None:
    processor = BackgroundRunEventProcessor()

    lines = processor.process(
        {
            "event": "self_evolution_review",
            "session_id": "sess-123",
            "updated_targets": [
                target
                for target, updated in (
                    ("skills", reviewed_skills),
                    ("memory", reviewed_memory),
                )
                if updated
            ],
            "reviewed_skills": reviewed_skills,
            "reviewed_memory": reviewed_memory,
            "completed": True,
        }
    )

    assert lines == [f"· background self-evolution review: {subject} updated"]


def test_processor_renders_revisioned_workflow_progress_once() -> None:
    processor = BackgroundRunEventProcessor()
    event = {
        "event": "workflow_run_updated",
        "workflow_run_id": "wf_1",
        "revision": 3,
        "name": "review",
        "status": "running",
        "current_phase": "Verify",
        "agents": [
            {"status": "completed"},
            {"status": "running"},
        ],
    }

    assert processor.process(event) == [
        "Workflow wf_1 · review · running · Agents 1/2 · Verify"
    ]
    assert processor.process(event) == []


def test_processor_does_not_render_an_empty_self_evolution_receipt() -> None:
    processor = BackgroundRunEventProcessor()

    lines = processor.process(
        {
            "event": "self_evolution_review",
            "session_id": "sess-123",
            "updated_targets": [],
            "reviewed_skills": False,
            "reviewed_memory": False,
            "completed": True,
        }
    )

    assert lines == []
