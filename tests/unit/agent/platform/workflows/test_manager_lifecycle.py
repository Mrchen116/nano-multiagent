import json
import asyncio
from pathlib import Path
import threading

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


def test_terminal_snapshot_is_queryable_after_manager_restart(tmp_path: Path) -> None:
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

    recovered = WorkflowManager(
        background_registry=BackgroundTaskRegistry(),
        config_dirname=".nanocode",
        child_runner_factory=lambda _context, _run_id: child,
    )
    recovered.load_session_runs(session_id="sess_parent", workspace_root=tmp_path)

    assert recovered.get(launch.run_id) == expected
    assert recovered.list_runs(session_id="sess_parent") == (expected,)
    recovered.close()


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
