import json
import asyncio
from pathlib import Path
import threading

import pytest

from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.platform.workflows import WorkflowLaunchContext, WorkflowManager


SCRIPT = """
meta = {"name": "demo", "description": "Run two agents"}

async def main():
    values = await parallel([
        lambda: agent("one"),
        lambda: agent("two"),
    ])
    return {"values": values}
"""


def test_launch_persists_script_journal_snapshot_and_completes_task(
    tmp_path: Path,
) -> None:
    registry = BackgroundTaskRegistry()

    async def child(call):  # noqa: ANN001
        return f"done:{call.prompt}"

    manager = WorkflowManager(
        background_registry=registry,
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    launch = manager.launch(
        source=SCRIPT,
        args={"target": "repo"},
        size_guideline="large",
        context=WorkflowLaunchContext(
            parent_session_id="sess_parent",
            workspace_root=tmp_path,
            parent_run_id="run_parent",
            parent_tool_call_id="call_parent",
        ),
    )

    snapshot = manager.wait(launch.run_id, timeout=2)

    assert launch.status == "async_launched"
    assert snapshot["status"] == "completed"
    assert snapshot["result"] == {"values": ["done:one", "done:two"]}
    assert snapshot["size_guideline"] == "large"
    assert Path(snapshot["script_path"]).read_text(encoding="utf-8") == SCRIPT
    journal = [
        json.loads(line)
        for line in Path(snapshot["journal_path"])
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [item["event"] for item in journal][0] == "run_started"
    assert [item["event"] for item in journal][-1] == "run_completed"
    task = registry.get(launch.task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.workflow_run_id == launch.run_id
    manager.close()


def test_top_level_exception_fails_and_cooperative_stop_is_terminal(
    tmp_path: Path,
) -> None:
    registry = BackgroundTaskRegistry()

    async def child(call):  # noqa: ANN001
        return call.prompt

    manager = WorkflowManager(
        background_registry=registry,
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    context = WorkflowLaunchContext(
        parent_session_id="sess_parent", workspace_root=tmp_path
    )
    failed = manager.launch(
        source=SCRIPT.replace(
            'return {"values": values}', "raise RuntimeError('boom')"
        ),
        args=None,
        context=context,
    )
    assert manager.wait(failed.run_id, timeout=2)["status"] == "failed"

    stopped = manager.launch(
        source="""
meta = {"name": "loop", "description": "Loop until stopped"}
async def main():
    while True:
        pass
""",
        args=None,
        context=context,
    )
    manager.control(stopped.run_id, action="stop")
    assert manager.wait(stopped.run_id, timeout=2)["status"] == "stopped"
    manager.close()


def test_resume_rehydrates_complete_agent_prefix_without_live_dispatch(
    tmp_path: Path,
) -> None:
    registry = BackgroundTaskRegistry()
    live: list[str] = []

    async def child(call):  # noqa: ANN001
        live.append(call.prompt)
        return f"done:{call.prompt}"

    manager = WorkflowManager(
        background_registry=registry,
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    context = WorkflowLaunchContext(
        parent_session_id="sess_parent", workspace_root=tmp_path
    )
    original = manager.launch(source=SCRIPT, args=None, context=context)
    first = manager.wait(original.run_id, timeout=2)
    resumed = manager.launch(
        source=SCRIPT,
        args=None,
        context=context,
        resume_from_run_id=original.run_id,
    )
    second = manager.wait(resumed.run_id, timeout=2)

    assert live == ["one", "two"]
    assert first["result"] == second["result"]
    assert all(item["terminal_ordinal"] is not None for item in first["agents"])
    assert [item["status"] for item in second["agents"]] == ["completed", "completed"]
    manager.close()


def test_resume_rejects_a_run_owned_by_another_parent_session(
    tmp_path: Path,
) -> None:
    async def child(call):  # noqa: ANN001
        return call.prompt

    manager = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    original = manager.launch(
        source=SCRIPT,
        args=None,
        context=WorkflowLaunchContext(
            parent_session_id="session-a", workspace_root=tmp_path
        ),
    )
    manager.wait(original.run_id, timeout=2)

    with pytest.raises(ValueError, match="parent session"):
        manager.launch(
            source=SCRIPT,
            args=None,
            context=WorkflowLaunchContext(
                parent_session_id="session-b", workspace_root=tmp_path
            ),
            resume_from_run_id=original.run_id,
        )

    manager.close()


def test_resume_preserves_observed_terminal_order_instead_of_start_order(
    tmp_path: Path,
) -> None:
    async def child(call):  # noqa: ANN001
        if call.prompt == "one":
            await asyncio.sleep(0.02)
        return call.prompt

    manager = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    context = WorkflowLaunchContext(
        parent_session_id="sess_parent", workspace_root=tmp_path
    )
    original = manager.launch(source=SCRIPT, args=None, context=context)
    first = manager.wait(original.run_id, timeout=2)
    resumed = manager.launch(
        source=SCRIPT,
        args=None,
        context=context,
        resume_from_run_id=original.run_id,
    )
    second = manager.wait(resumed.run_id, timeout=2)

    assert [item["terminal_ordinal"] for item in first["agents"]] == [1, 0]
    assert [item["terminal_ordinal"] for item in second["agents"]] == [1, 0]
    manager.close()


@pytest.mark.parametrize("snapshot_state", ["missing", "corrupt"])
def test_terminal_snapshot_is_queryable_after_manager_restart(
    tmp_path: Path, snapshot_state: str
) -> None:
    registry = BackgroundTaskRegistry()

    async def child(call):  # noqa: ANN001
        return call.prompt

    context = WorkflowLaunchContext(
        parent_session_id="sess_parent", workspace_root=tmp_path
    )
    first = WorkflowManager(
        background_registry=registry,
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    launch = first.launch(source=SCRIPT, args=None, context=context)
    expected = first.wait(launch.run_id, timeout=2)
    first.close()
    snapshot_path = Path(expected["transcript_dir"]) / "run.json"
    if snapshot_state == "missing":
        snapshot_path.unlink()
    else:
        snapshot_path.write_text("{broken", encoding="utf-8")

    recovered = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    recovered.load_session_runs(session_id="sess_parent", workspace_root=tmp_path)

    assert recovered.get(launch.run_id) == expected
    assert recovered.list_runs(session_id="sess_parent") == (expected,)
    recovered.close()


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


def test_named_nested_workflow_uses_same_agent_admission_stream(tmp_path: Path) -> None:
    registry = BackgroundTaskRegistry()

    async def child(call):  # noqa: ANN001
        return f"done:{call.prompt}"

    inner = """
meta = {"name": "inner", "description": "Nested work"}
async def main():
    return await agent("nested")
"""
    outer = """
meta = {"name": "outer", "description": "Outer work"}
async def main():
    first = await agent("first")
    second = await workflow("inner")
    return [first, second]
"""
    manager = WorkflowManager(
        background_registry=registry,
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
        named_source_resolver=lambda name, _root: inner if name == "inner" else None,
    )
    launch = manager.launch(
        source=outer,
        args=None,
        context=WorkflowLaunchContext(
            parent_session_id="sess_parent", workspace_root=tmp_path
        ),
    )

    snapshot = manager.wait(launch.run_id, timeout=2)

    assert snapshot["result"] == ["done:first", "done:nested"]
    assert [item["start_ordinal"] for item in snapshot["agents"]] == [0, 1]
    manager.close()


def test_nested_script_artifact_uses_the_parent_workspace(
    tmp_path: Path,
) -> None:
    inner_path = tmp_path / "inner.py"
    inner_path.write_text(
        """
meta = {"name": "inner", "description": "Nested artifact"}
async def main():
    return await agent("artifact child")
""",
        encoding="utf-8",
    )

    async def child(call):  # noqa: ANN001
        return f"done:{call.prompt}"

    manager = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    launch = manager.launch(
        source="""
meta = {"name": "outer", "description": "Nested artifact caller"}
async def main():
    return await workflow({"scriptPath": "inner.py"})
""",
        args=None,
        context=WorkflowLaunchContext(
            parent_session_id="sess_parent", workspace_root=tmp_path
        ),
    )

    snapshot = manager.wait(launch.run_id, timeout=2)

    assert snapshot["status"] == "completed"
    assert snapshot["result"] == "done:artifact child"
    manager.close()


def test_whole_run_stop_wins_when_last_child_returns_after_request(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    release = threading.Event()

    async def child(_call):  # noqa: ANN001
        started.set()
        await asyncio.to_thread(release.wait)
        return "late result"

    manager = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    launch = manager.launch(
        source="""
meta = {"name": "stop-wins", "description": "Stop the final child"}
async def main():
    return await agent("last")
""",
        args=None,
        context=WorkflowLaunchContext(
            parent_session_id="sess_parent", workspace_root=tmp_path
        ),
    )
    assert started.wait(timeout=2)
    manager.control(launch.run_id, action="stop")
    release.set()

    assert manager.wait(launch.run_id, timeout=2)["status"] == "stopped"
    manager.close()
