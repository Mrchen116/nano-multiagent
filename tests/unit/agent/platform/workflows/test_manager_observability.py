import json
from pathlib import Path
import time

import pytest

from agent.core.background_tasks.notifications import build_background_notification
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.platform.workflows import WorkflowLaunchContext, WorkflowManager


@pytest.mark.parametrize(
    ("guideline", "explicit", "agent_count", "expects_warning"),
    [
        ("medium", False, 25, False),
        ("medium", False, 26, True),
        ("small", True, 5, True),
        ("medium", True, 15, True),
        ("large", True, 50, True),
        ("unrestricted", True, 60, False),
    ],
)
def test_large_workflow_agent_advisory_uses_default_or_explicit_boundary(
    tmp_path: Path,
    guideline: str,
    explicit: bool,
    agent_count: int,
    expects_warning: bool,
) -> None:
    async def child(call):  # noqa: ANN001
        return call.prompt

    manager = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    source = """
meta = {"name": "scale", "description": "Exercise advisory boundaries"}
async def main():
    return await parallel([
        lambda index=index: agent(str(index))
        for index in range(args["agent_count"])
    ])
"""

    launch = manager.launch(
        source=source,
        args={"agent_count": agent_count},
        context=WorkflowLaunchContext(
            parent_session_id="sess_parent", workspace_root=tmp_path
        ),
        size_guideline=guideline,
        size_guideline_explicit=explicit,
    )
    snapshot = manager.wait(launch.run_id, timeout=5)

    assert (snapshot["large_warning"] is not None) is expects_warning
    manager.close()


def test_large_workflow_token_advisory_and_ultracode_suppression(
    tmp_path: Path,
) -> None:
    class Child:
        async def __call__(self, call):  # noqa: ANN001
            return call.prompt

        def usage_for(self, _agent_call_id):  # noqa: ANN001, ANN201
            return {
                "prompt_tokens": 1_499_999,
                "completion_tokens": 1,
                "total_tokens": 1_500_000,
            }

    def run(*, ultracode: bool, root: Path) -> dict:
        manager = WorkflowManager(
            background_registry=BackgroundTaskRegistry(),
            config_dirname=".nanocode",
            child_runner_factory=lambda _context, _run_id: Child(),
        )
        launch = manager.launch(
            source="""
meta = {"name": "tokens", "description": "Exercise token advisory"}
async def main():
    return await agent("one")
""",
            args=None,
            context=WorkflowLaunchContext(
                parent_session_id="sess_parent",
                workspace_root=root,
                workflow_ultracode=ultracode,
            ),
        )
        snapshot = manager.wait(launch.run_id, timeout=2)
        manager.close()
        return snapshot

    regular = run(ultracode=False, root=tmp_path / "regular")
    ultracode = run(ultracode=True, root=tmp_path / "ultracode")

    assert "estimated 1.5M tokens" in regular["large_warning"]
    assert ultracode["large_warning"] is None


class _ObservableChild:
    def __init__(self) -> None:
        self._details: dict[str, dict[str, object]] = {}

    async def __call__(self, call):  # noqa: ANN001, ANN201
        agent_call_id = f"wa_{call.start_ordinal:06d}"
        self._details[agent_call_id] = {
            "status": "completed",
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 4,
                "total_tokens": 11,
            },
            "duration_ms": 9,
            "session_id": f"child-{call.start_ordinal}",
            "transcript_path": f"/artifacts/{agent_call_id}.jsonl",
            "worktree_path": f"/retained/{agent_call_id}",
        }
        return f"done:{call.prompt}"

    def details_for(self, agent_call_id: str) -> dict[str, object] | None:
        return self._details.get(agent_call_id)

    def status_for(self, agent_call_id: str) -> str | None:
        details = self.details_for(agent_call_id)
        return str(details["status"]) if details else None

    def usage_for(self, agent_call_id: str) -> dict[str, int] | None:
        details = self.details_for(agent_call_id)
        return details.get("usage") if details else None  # type: ignore[return-value]


def _wait_until_agent_completed(manager: WorkflowManager, run_id: str) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        snapshot = manager.get(run_id)
        agents = snapshot["agents"] if snapshot is not None else ()
        if agents and agents[0]["status"] == "completed":
            return
        time.sleep(0.01)
    raise AssertionError("Workflow child did not complete")


def test_manager_terminal_records_preserve_observability_for_all_states(
    tmp_path: Path,
) -> None:
    scripts = {
        "completed": """
meta = {"name": "complete", "description": "Complete after one child", "phases": [{"title": "Work"}]}
async def main():
    phase("Work")
    return await agent("complete-child", phase="Work")
""",
        "failed": """
meta = {"name": "fail", "description": "Fail after one child", "phases": [{"title": "Work"}]}
async def main():
    phase("Work")
    partial = await agent("failed-child", phase="Work")
    raise RuntimeError("top-level boom")
""",
        "stopped": """
meta = {"name": "stop", "description": "Stop after one child", "phases": [{"title": "Work"}]}
async def main():
    phase("Work")
    partial = await agent("stopped-child", phase="Work")
    while True:
        pass
""",
    }

    for terminal, source in scripts.items():
        registry = BackgroundTaskRegistry()
        child = _ObservableChild()
        manager = WorkflowManager(
            background_registry=registry,
            config_dirname=".nanocode",
            child_runner_factory=lambda _context, _run_id, child=child: child,
        )
        launch = manager.launch(
            source=source,
            args=None,
            context=WorkflowLaunchContext(
                parent_session_id=f"sess_{terminal}",
                workspace_root=tmp_path / terminal,
            ),
        )
        if terminal == "stopped":
            _wait_until_agent_completed(manager, launch.run_id)
            manager.control(launch.run_id, action="stop")
        snapshot = manager.wait(launch.run_id, timeout=2)
        task = registry.get(launch.task_id)
        assert task is not None
        notification = build_background_notification(task)
        assert notification.background_return is not None

        assert snapshot["status"] == terminal
        assert task.status == terminal
        assert (
            task.usage
            == snapshot["usage"]
            == {
                "prompt_tokens": 7,
                "completion_tokens": 4,
                "total_tokens": 11,
            }
        )
        assert task.duration_ms == snapshot["duration_ms"]
        assert task.tool_use_count == 1
        assert notification.background_return.usage == snapshot["usage"]
        assert notification.background_return.duration_ms == snapshot["duration_ms"]
        assert notification.background_return.tool_use_count == 1

        agent = snapshot["agents"][0]
        assert agent["duration_ms"] == 9
        assert agent["session_id"] == "child-0"
        assert agent["transcript_path"] == "/artifacts/wa_000000.jsonl"
        assert agent["worktree_path"] == "/retained/wa_000000"
        phase_info = snapshot["phases"][0]
        assert phase_info["usage"] == snapshot["usage"]
        assert phase_info["duration_ms"] is not None

        if terminal == "completed":
            assert notification.background_return.result == "done:complete-child"
            assert notification.background_return.error is None
        else:
            assert notification.background_return.result == json.dumps(
                [f"done:{terminal}-child"], ensure_ascii=False
            )
            if terminal == "failed":
                assert "top-level boom" in (notification.background_return.error or "")
        manager.close()
