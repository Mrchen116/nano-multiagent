from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from coding_cli.product import open_cli_session


class _Kernel:
    def __init__(self) -> None:
        self.maintenance_roots: list[Path] = []
        self.created_sessions: list[dict[str, object]] = []
        self.submitted_parts: list[dict[str, object]] = []
        self.drained = False
        self.scheduler = None
        self.drain_roots: list[Path | None] = []

    def run_skill_maintenance(self, *, workspace_root: Path) -> None:
        self.maintenance_roots.append(workspace_root)

    def set_skill_batch_review_drain_scheduler(self, scheduler):
        self.scheduler = scheduler

    async def run_queued_skill_batch_reviews(self, *, run_background_analysis, skill_root=None):
        self.drained = True
        self.drain_roots.append(skill_root)
        await run_background_analysis(
            "batch prompt",
            tool_allowlist=("skill_view", "skill_manage"),
            metadata={"background_task": "skill_batch_review"},
        )
        return (SimpleNamespace(completed=True),)

    async def create_session(self, **kwargs):
        self.created_sessions.append(dict(kwargs))
        return SimpleNamespace(session_id=f"session-{len(self.created_sessions)}")

    def submit(self, **kwargs):
        self.submitted_parts.append(dict(kwargs))
        return SimpleNamespace(run_id="run-1", status="queued")

    def get_run(self, run_id: str):
        return SimpleNamespace(run_id=run_id, status="completed")


@pytest.mark.asyncio
async def test_open_cli_session_drains_queued_skill_batch_reviews(
    tmp_path: Path,
) -> None:
    kernel = _Kernel()

    session = await open_cli_session(kernel, workspace_root=tmp_path)

    assert session.session_id == "session-2"
    assert kernel.maintenance_roots == [tmp_path]
    assert kernel.drained is True
    assert kernel.drain_roots == [tmp_path / ".nano" / "skills"]
    assert kernel.created_sessions[0] == {
        "workspace_root": tmp_path,
        "enabled_tools": ["skill_view", "skill_manage"],
        "metadata": {"background_task": "skill_batch_review"},
    }
    assert kernel.submitted_parts == [
        {
            "session_id": "session-1",
            "parts": [{"type": "text", "text": "batch prompt"}],
            "workspace_root": tmp_path,
        }
    ]
    assert callable(kernel.scheduler)


@pytest.mark.asyncio
async def test_open_cli_session_drains_live_skill_batch_enqueue(tmp_path: Path) -> None:
    kernel = _Kernel()
    await open_cli_session(kernel, workspace_root=tmp_path)
    kernel.drained = False
    kernel.created_sessions.clear()
    kernel.submitted_parts.clear()

    kernel.scheduler(SimpleNamespace(skill_name="auto-skill"))
    await asyncio.sleep(0)

    assert kernel.drained is True
    assert kernel.drain_roots[-1] == tmp_path / ".nano" / "skills"
    assert kernel.created_sessions == [
        {
            "workspace_root": tmp_path,
            "enabled_tools": ["skill_view", "skill_manage"],
            "metadata": {"background_task": "skill_batch_review"},
        }
    ]
