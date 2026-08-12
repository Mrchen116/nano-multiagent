from __future__ import annotations

import asyncio
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.types import SessionRef
from agent.core.types import Message, TurnResult
from agent.core.workflows import AgentCallSpec
from agent.platform.workflows import WorkflowChildRunner, WorkflowLaunchContext


class _TranscriptControl:
    def __init__(self) -> None:
        self.directory = SimpleNamespace(
            get=lambda _ref: SimpleNamespace(tool_allowlist=(), skills=None)
        )
        self.ref = object()
        self.created = 0
        self.files = JsonlSessionFiles(
            data_dir=None, workspace_config_dirname=".nanocode"
        )

    def list_parent_enabled_tool_names(self):
        return ()

    def resolve_run_model(self):
        return "parent-model"

    def resolve_reasoning_effort(self):
        return "high"

    def create_subagent(self, **kwargs):  # noqa: ANN003, ANN201
        self.created += 1
        ref = SessionRef(
            session_id=f"child-{self.created}",
            workspace_root=kwargs["workspace_root"],
            parent_session_id="parent",
        )
        path = self.files.resolve_path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"role":"assistant","content":"child output"}\n',
            encoding="utf-8",
        )
        return ref


class _TerminalHandle:
    def __init__(self, terminal: str) -> None:
        self.terminal = terminal
        self.released = threading.Event()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True
        self.released.set()

    def result(self):  # noqa: ANN201
        self.released.wait(timeout=2)
        if self.stopped:
            raise RuntimeError("attempt stopped")
        if self.terminal == "failed":
            raise RuntimeError("child failed")
        return TurnResult(
            session_id="child",
            turn_id="turn",
            messages=(
                Message(
                    message_id="message",
                    role="assistant",
                    content="child result",
                ),
            ),
        )


class _TerminalRunner:
    def __init__(self, terminal: str) -> None:
        self.handle = _TerminalHandle(terminal)

    def start_workflow_agent(self, **_kwargs):
        return self.handle


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Workflow Test",
            "-c",
            "user.email=workflow@example.invalid",
            "commit",
            "-qm",
            "base",
        ],
        cwd=path,
        check=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", ["completed", "failed", "stopped"])
@pytest.mark.parametrize("dirty", [False, True])
async def test_worktree_transcript_is_archived_and_only_dirty_worktree_is_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
    dirty: bool,
) -> None:
    monkeypatch.setattr(
        "agent.platform.workflows.child.provider_of", lambda _model: "p"
    )
    _init_git_repo(tmp_path)
    control = _TranscriptControl()
    runner = _TerminalRunner(terminal)
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=control,
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
    )
    call = AgentCallSpec(
        prompt="review",
        start_ordinal=0,
        resume_key="key",
        isolation="worktree",
    )

    task = asyncio.create_task(child(call))
    target = (
        tmp_path / ".nanocode/sessions/parent/workflows/runs/wf_1/worktrees/wa_000000"
    )
    for _ in range(100):
        if target.exists():
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("Workflow worktree was not created")
    if dirty:
        (target / "tracked.txt").write_text("changed\n", encoding="utf-8")
    if terminal == "stopped":
        assert child.stop_agent("wa_000000") is True
    else:
        runner.handle.released.set()

    if terminal == "failed":
        with pytest.raises(RuntimeError, match="child failed"):
            await task
    elif terminal == "stopped":
        assert await task is None
    else:
        assert await task == "child result"

    details = child.details_for("wa_000000")
    assert details is not None
    assert details["status"] == terminal
    assert details["session_id"] == "child-1"
    transcript_path = Path(str(details["transcript_path"]))
    assert transcript_path.is_file()
    assert str(transcript_path).startswith(
        str(tmp_path / ".nanocode/sessions/parent/workflows/runs/wf_1/transcripts")
    )
    assert details["duration_ms"] is not None
    assert details["worktree_path"] == (str(target) if dirty else None)
    assert target.exists() is dirty


@pytest.mark.asyncio
async def test_cleanup_failure_retains_worktree_locator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent.platform.workflows.child.provider_of", lambda _model: "p"
    )
    _init_git_repo(tmp_path)
    control = _TranscriptControl()
    runner = _TerminalRunner("completed")
    real_run = subprocess.run

    def fail_remove(command, **kwargs):  # noqa: ANN001, ANN003, ANN201
        if command[:3] == ["git", "worktree", "remove"]:
            return subprocess.CompletedProcess(command, 1, "", "remove failed")
        return real_run(command, **kwargs)

    monkeypatch.setattr("agent.platform.workflows.child.subprocess.run", fail_remove)
    child = WorkflowChildRunner(
        context=WorkflowLaunchContext(
            parent_session_id="parent",
            workspace_root=tmp_path,
            subagent_control=control,
        ),
        workflow_run_id="wf_1",
        subagent_runner=runner,
        config_dirname=".nanocode",
    )
    call = AgentCallSpec(
        prompt="review",
        start_ordinal=0,
        resume_key="key",
        isolation="worktree",
    )

    task = asyncio.create_task(child(call))
    await asyncio.sleep(0)
    runner.handle.released.set()
    assert await task == "child result"

    details = child.details_for("wa_000000")
    assert details is not None
    assert details["worktree_path"] is not None
