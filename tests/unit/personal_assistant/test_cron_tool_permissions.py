"""Cron action-level permission behavior."""

from __future__ import annotations

from typing import Any

import pytest

from personal_assistant.tools.cron import make_cron_tool


@pytest.mark.parametrize(
    ("tool_input", "expected"),
    [
        ({"action": "list"}, "allow"),
        ({"action": "runs", "jobId": "job-1"}, "allow"),
        ({"action": "add"}, "passthrough"),
        ({"action": "update"}, "passthrough"),
        ({"action": "remove"}, "passthrough"),
        ({"action": "run"}, "passthrough"),
        ({}, "passthrough"),
    ],
)
def test_cron_permissions_follow_action_risk(
    tool_input: dict[str, Any], expected: str
) -> None:
    """Allow local reads and classify every mutating or missing action."""

    decision = make_cron_tool({}).check_permissions(tool_input, object())

    assert decision.behavior == expected


def test_cron_projects_mutating_action_for_classifier() -> None:
    """Give the classifier the current action and job identity."""

    projection = make_cron_tool({}).to_auto_classifier_input(
        {
            "action": "add",
            "job": {
                "name": "daily summary",
                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                "payload": {"kind": "agentTurn", "message": "summarize"},
            },
        }
    )

    assert "action=add" in projection
    assert "daily summary" in projection
