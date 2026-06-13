"""Closure-direct cron tool tests (refactor-406 决策 9).

The migrated cron tool (``src/personal_assistant/tools/cron.py``) talks directly to
the per-agent ``CronExecutionService`` via the factory closure — no
``HostCapabilityDispatcher``. These tests cover:

- job persistence (add/list/remove) byte-compatible with the pre-migration tool,
- the immediate-run path routes by ``agent_id`` to the right service's ``enqueue``,
- per-agent routing isolation (agent A's run never hits agent B's service),
- missing-service → tool-level error dict (no raise).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from personal_assistant.tools.cron import make_cron_tool


class _FakeService:
    """Records enqueue calls; returns a configurable ack."""

    def __init__(self, agent_id: str, *, ack: Mapping[str, Any] | None = None) -> None:
        self._agent_id = agent_id
        self.calls: list[dict[str, Any]] = []
        self._ack = ack or {"accepted": True, "job_id": "", "request_id": "req-1"}

    def enqueue(self, *, job_id: str, trigger: str) -> Mapping[str, Any]:
        self.calls.append({"job_id": job_id, "trigger": trigger})
        return {**self._ack, "job_id": job_id}


class _Ctx:
    """Minimal ToolContext stand-in (repo_root + session_metadata)."""

    def __init__(self, repo_root: Path, agent_id: str) -> None:
        self.repo_root = repo_root
        self.session_metadata = {"agent_id": agent_id}
        self.session_id = "sess-1"


def _add_job(tool, root: Path, agent_id: str) -> str:
    result = tool.run(
        {
            "action": "add",
            "job": {
                "name": "remind",
                "schedule": {"kind": "at", "at": "2026-01-01T00:00:00Z"},
                "payload": {"kind": "agentTurn", "message": "ping"},
            },
        },
        _Ctx(root, agent_id),
    )
    assert result["ok"] is True
    return result["jobId"]


def test_add_list_remove_roundtrip(tmp_path: Path) -> None:
    svc = _FakeService("agent-a")
    tool = make_cron_tool({"agent-a": svc})
    job_id = _add_job(tool, tmp_path, "agent-a")

    listed = tool.run({"action": "list"}, _Ctx(tmp_path, "agent-a"))
    assert listed["count"] == 1
    assert listed["jobs"][0]["id"] == job_id

    removed = tool.run({"action": "remove", "jobId": job_id}, _Ctx(tmp_path, "agent-a"))
    assert removed["removed"] is True
    assert tool.run({"action": "list"}, _Ctx(tmp_path, "agent-a"))["count"] == 0


def test_run_routes_to_agent_service(tmp_path: Path) -> None:
    svc = _FakeService("agent-a")
    tool = make_cron_tool({"agent-a": svc})
    job_id = _add_job(tool, tmp_path, "agent-a")

    result = tool.run({"action": "run", "jobId": job_id}, _Ctx(tmp_path, "agent-a"))
    assert result["ok"] is True
    assert result["accepted"] is True
    assert svc.calls == [{"job_id": job_id, "trigger": "manual"}]


def test_run_per_agent_isolation(tmp_path: Path) -> None:
    """Agent A's run must hit A's service, never B's (决策 9 per-agent routing)."""
    svc_a = _FakeService("agent-a")
    svc_b = _FakeService("agent-b")
    tool = make_cron_tool({"agent-a": svc_a, "agent-b": svc_b})

    # Each agent has its own workspace; add a job under agent-a's workspace.
    root_a = tmp_path / "a"
    root_a.mkdir()
    job_id = _add_job(tool, root_a, "agent-a")

    tool.run({"action": "run", "jobId": job_id}, _Ctx(root_a, "agent-a"))
    assert len(svc_a.calls) == 1
    assert svc_b.calls == [], "agent-b service must not be touched by agent-a run"


def test_run_missing_service_returns_error_dict(tmp_path: Path) -> None:
    tool = make_cron_tool({})  # no service registered
    job_id = _add_job(tool, tmp_path, "agent-x")
    result = tool.run({"action": "run", "jobId": job_id}, _Ctx(tmp_path, "agent-x"))
    assert result["ok"] is False
    assert "cron execution service" in result["error"]


def test_run_declined_ack_surfaces_error(tmp_path: Path) -> None:
    svc = _FakeService("agent-a", ack={"accepted": False, "error_code": "job_disabled"})
    tool = make_cron_tool({"agent-a": svc})
    job_id = _add_job(tool, tmp_path, "agent-a")
    result = tool.run({"action": "run", "jobId": job_id}, _Ctx(tmp_path, "agent-a"))
    assert result["ok"] is False
    assert "disabled" in result["error"]
