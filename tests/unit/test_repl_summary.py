import io
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from coding_cli.render.repl_render import print_repl_turn_summary
from coding_cli.render.repl_summary import format_turn_summary, print_turn_summary


def test_format_turn_summary_minimal_completed() -> None:
    payload = {
        "status": "completed",
        "stop_reason": "stop",
        "run_id": "run_123",
        "session_id": "sess_456",
    }
    summary = format_turn_summary(payload=payload)
    assert "State: completed | stop=stop" in summary
    assert "run_123" not in summary
    assert "sess_456" not in summary
    assert "Usage: unavailable" in summary


def test_format_turn_summary_omits_run_and_session_ids() -> None:
    payload = {
        "completed": True,
        "run_id": "run_secret",
        "session_id": "sess_secret",
    }
    summary = format_turn_summary(payload=payload)
    assert "run_secret" not in summary
    assert "sess_secret" not in summary
    assert "State: completed" in summary


def test_format_turn_summary_with_usage() -> None:
    payload = {
        "status": "completed",
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 35,
            "total_tokens": 155,
        },
    }
    summary = format_turn_summary(payload=payload)
    assert "Usage: prompt=120, completion=35, total=155" in summary


def test_format_turn_summary_with_repl_view() -> None:
    payload = {
        "status": "completed",
        "_repl_view": {
            "status_updates": ["status=queued", "attempt 2", "status=completed"],
            "tool_updates": [
                "Tool: bash start",
                "Tool: bash output",
                "Tool: bash start",
            ],
        },
    }
    summary = format_turn_summary(payload=payload)
    assert "Progress: attempt 2" in summary
    assert "Tool: bash start" in summary
    assert "Tool: bash output" in summary


def test_format_turn_summary_limits_tool_updates() -> None:
    updates = [f"tool{i}" for i in range(10)]
    payload = {
        "status": "completed",
        "_repl_view": {
            "status_updates": [],
            "tool_updates": updates,
        },
    }
    summary = format_turn_summary(payload=payload)
    for i in range(6, 10):
        assert f"Tool: tool{i}" in summary
    for i in range(6):
        assert f"Tool: tool{i}" not in summary


def test_print_turn_summary_writes_output_and_budget() -> None:
    out = io.StringIO()
    payload = {
        "status": "completed",
        "session_id": "sess_123",
    }
    mock_client = MagicMock()

    with patch(
        "coding_cli.render.repl_summary.print_context_budget_snapshot"
    ) as mock_budget:
        print_turn_summary(out=out, payload=payload, context_budget_client=mock_client)

    text = out.getvalue()
    assert "State: completed" in text
    mock_budget.assert_called_once_with(
        out=out, client=mock_client, session_id="sess_123"
    )


def test_print_turn_summary_skips_budget_when_no_session_id() -> None:
    out = io.StringIO()
    payload = {"status": "completed"}
    mock_client = MagicMock()

    with patch(
        "coding_cli.render.repl_summary.print_context_budget_snapshot"
    ) as mock_budget:
        print_turn_summary(out=out, payload=payload, context_budget_client=mock_client)

    mock_budget.assert_not_called()


def test_print_repl_turn_summary_renders_ordered_updates_before_state() -> None:
    out = io.StringIO()
    payload = {
        "status": "completed",
        "stop_reason": "stop",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "_repl_view": {
            "status_updates": [],
            "tool_updates": ["Tool: read output={...}"],
            "ordered_updates": [
                {
                    "kind": "assistant",
                    "text": "Let's check the README file to learn about the project.",
                },
                {"kind": "tool", "text": "Tool: read output={...}"},
                {"kind": "assistant", "text": "Okay, I've checked the README!"},
            ],
        },
    }

    print_repl_turn_summary(out=out, payload=payload)
    text = out.getvalue()

    assert text.index("Let's check the README file") < text.index(
        "Tool: read output={...}"
    )
    assert text.index("Tool: read output={...}") < text.index(
        "Okay, I've checked the README!"
    )
    assert text.count("Tool: read output={...}") == 1
    assert "State: completed | stop=stop" in text
