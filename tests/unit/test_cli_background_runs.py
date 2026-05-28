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


# ---------------------------------------------------------------------------
# R5 tests: self_evolution_review event rendering (feat-349-M3)
# ---------------------------------------------------------------------------


def test_processor_renders_self_evolution_review_event() -> None:
    """self_evolution_review session event must render as one system notification line."""
    processor = BackgroundRunEventProcessor()

    lines = processor.process({
        "event": "self_evolution_review",
        "data": {
            "reviewed_skills": True,
            "reviewed_memory": False,
            "tool_names_called": ["skill_manage"],
            "completed": True,
        },
    })
    assert len(lines) == 1
    # Must start with · prefix (system notification style).
    assert lines[0].startswith("·")
    # Must mention self-evolution / review / skills.
    assert "skill" in lines[0].lower() or "evolution" in lines[0].lower()


def test_processor_renders_self_evolution_review_memory_only() -> None:
    """self_evolution_review for memory-only review renders a notification."""
    processor = BackgroundRunEventProcessor()

    lines = processor.process({
        "event": "self_evolution_review",
        "data": {
            "reviewed_skills": False,
            "reviewed_memory": True,
            "tool_names_called": ["memory"],
            "completed": True,
        },
    })
    assert len(lines) == 1
    assert lines[0].startswith("·")
    assert "memory" in lines[0].lower() or "evolution" in lines[0].lower()


def test_processor_renders_self_evolution_review_combined() -> None:
    """Combined review renders a single line covering both skills and memory."""
    processor = BackgroundRunEventProcessor()

    lines = processor.process({
        "event": "self_evolution_review",
        "data": {
            "reviewed_skills": True,
            "reviewed_memory": True,
            "tool_names_called": ["skill_manage", "memory"],
            "completed": True,
        },
    })
    assert len(lines) == 1
    assert lines[0].startswith("·")


# ---------------------------------------------------------------------------
# M5: self_evolution_review event uses flat structure (regression)
# The SSE event dict is flat — reviewed_skills/reviewed_memory are top-level keys,
# NOT nested under a "data" key.  The formatter must read them from event directly.
# ---------------------------------------------------------------------------


def test_format_self_evolution_review_flat_event_reviewed_skills() -> None:
    """self_evolution_review with flat event structure must render 'skills updated'.

    The actual SSE event emitted by self_improvement.py publish_session_event has
    reviewed_skills at the TOP LEVEL of the event dict, not nested under 'data'.
    The formatter must read from event directly, not from event.get('data', {}).
    """
    from coding_cli.events.background_runs import _format_self_evolution_review

    # This is the actual flat structure that arrives from the SSE stream.
    flat_event = {
        "event": "self_evolution_review",
        "session_id": "sess-123",
        "reviewed_skills": True,
        "reviewed_memory": False,
        "tool_names_called": ["skill_manage"],
        "completed": True,
    }
    lines = _format_self_evolution_review(flat_event)
    assert len(lines) == 1
    assert "skill" in lines[0].lower(), (
        f"Expected subject to mention 'skills' but got {lines[0]!r}; "
        "formatter must read reviewed_skills from top-level event keys, not event['data']"
    )
    # The subject portion must be "skills", not the fallback "self-evolution".
    # Format is "· background self-evolution review: <subject> updated".
    # Extract subject after the last ': '.
    subject_part = lines[0].split(": ", 1)[-1] if ": " in lines[0] else lines[0]
    assert "skill" in subject_part.lower(), (
        f"Subject must be 'skills' not fallback 'self-evolution'; subject_part={subject_part!r}, full={lines[0]!r}"
    )


def test_format_self_evolution_review_flat_event_reviewed_memory() -> None:
    """self_evolution_review with flat event must render 'memory updated' for memory-only review."""
    from coding_cli.events.background_runs import _format_self_evolution_review

    flat_event = {
        "event": "self_evolution_review",
        "session_id": "sess-123",
        "reviewed_skills": False,
        "reviewed_memory": True,
        "tool_names_called": ["memory"],
        "completed": True,
    }
    lines = _format_self_evolution_review(flat_event)
    assert len(lines) == 1
    # Subject portion after ': ' must mention memory, not the generic fallback.
    subject_part = lines[0].split(": ", 1)[-1] if ": " in lines[0] else lines[0]
    assert "memory" in subject_part.lower(), (
        f"Subject must be 'memory' not fallback 'self-evolution'; subject_part={subject_part!r}, full={lines[0]!r}"
    )
