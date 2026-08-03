"""Public cron tool shape and structured run-history behavior."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.scheduler.cron_execution_service import (
    CronRunRecord,
    CronRunsStore,
)
from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore
from personal_assistant.tools.cron import make_cron_tool


class _Context:
    def __init__(self, workspace_root: Path) -> None:
        self.repo_root = workspace_root
        self.session_metadata: dict[str, object] = {}


def test_cron_tool_exposes_current_actions_and_arguments() -> None:
    """Expose the actions and fields the model needs, without pinning prose."""

    tool = make_cron_tool({})
    properties = tool.input_schema["properties"]

    assert tool.name == "cron"
    assert tool.input_schema["required"] == ["action"]
    assert set(properties["action"]["enum"]) == {
        "list",
        "add",
        "update",
        "remove",
        "run",
        "runs",
    }
    assert {"job", "jobId", "patch"} <= set(properties)


def test_runs_returns_structured_history_newest_first(tmp_path: Path) -> None:
    """Return manual and scheduled records through the public tool result."""

    job_id = "job-history"
    CronJobStore(workspace_root=tmp_path).add(
        CronJob(
            id=job_id,
            name="history",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="report",
        )
    )
    runs = CronRunsStore(workspace_root=tmp_path)
    runs.append(
        CronRunRecord(
            request_id="older",
            job_id=job_id,
            trigger="scheduled",
            status="completed",
            accepted_at="2026-06-01T09:00:00+00:00",
        )
    )
    runs.append(
        CronRunRecord(
            request_id="newer",
            job_id=job_id,
            trigger="manual",
            status="failed",
            accepted_at="2026-06-01T10:00:00+00:00",
            error="failed",
        )
    )

    result = make_cron_tool({}).run(
        {"action": "runs", "jobId": job_id},
        _Context(tmp_path),  # type: ignore[arg-type]
    )

    assert result["ok"] is True
    assert [record["request_id"] for record in result["runs"]] == ["newer", "older"]
    assert result["runs"][0]["trigger"] == "manual"
    assert result["runs"][0]["status"] == "failed"
