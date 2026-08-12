from pathlib import Path

import pytest

from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.platform.workflows import WorkflowLaunchContext, WorkflowManager


SCRIPT = """
meta = {"name": "resume-restart", "description": "Resume one completed child"}

async def main():
    return await agent(args["prompt"])
"""


def _manager(*, child, registry=None) -> WorkflowManager:
    return WorkflowManager(
        background_registry=registry or BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )


def test_completed_run_resumes_from_durable_cache_after_manager_restart(
    tmp_path: Path,
) -> None:
    live: list[str] = []

    async def child(call):  # noqa: ANN001
        live.append(call.prompt)
        return "fixed result"

    context = WorkflowLaunchContext(
        parent_session_id="session-a", workspace_root=tmp_path
    )
    original_manager = _manager(child=child)
    original = original_manager.launch(
        source=SCRIPT,
        args={"prompt": "return fixed result"},
        context=context,
    )
    first = original_manager.wait(original.run_id, timeout=2)
    original_manager.close()

    restarted_manager = _manager(child=child)
    restarted_manager.load_session_runs(session_id="session-a", workspace_root=tmp_path)
    assert restarted_manager.control(original.run_id, action="pause")["status"] == (
        "completed"
    )
    resumed = restarted_manager.resume(
        original.run_id,
        context=context,
    )
    second = restarted_manager.wait(str(resumed["run_id"]), timeout=2)

    assert live == ["return fixed result"]
    assert second["result"] == first["result"]
    assert second["agents"][0]["replayed"] is True
    restarted_manager.close()


def test_restart_resume_reports_cross_session_owner_instead_of_unknown_run(
    tmp_path: Path,
) -> None:
    async def child(call):  # noqa: ANN001
        return call.prompt

    original_manager = _manager(child=child)
    original = original_manager.launch(
        source=SCRIPT,
        args={"prompt": "return fixed result"},
        context=WorkflowLaunchContext(
            parent_session_id="session-a", workspace_root=tmp_path
        ),
    )
    original_manager.wait(original.run_id, timeout=2)
    original_manager.close()

    restarted_manager = _manager(child=child)
    with pytest.raises(ValueError, match="different parent session"):
        restarted_manager.resume(
            original.run_id,
            context=WorkflowLaunchContext(
                parent_session_id="session-b", workspace_root=tmp_path
            ),
        )
    restarted_manager.close()
