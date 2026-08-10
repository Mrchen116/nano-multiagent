from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import (
    LLMConfig,
    PromptSlots,
    RunOrigin,
    SessionRuntimeConfig,
    build_kernel,
)
from coding_cli.commands import _run_workflow_tty_controls, run_cli


SCRIPT = """
meta = {"name": "restart-resume", "description": "Resume one cached child"}

async def main():
    return await agent("return the fixed result")
"""


class _SeedClient:
    def __init__(self) -> None:
        self.launched = False
        self.child_calls = 0

    def generate(self, request: Any):  # noqa: ANN201
        tool_names = {tool.name for tool in request.tools}
        if "Workflow" not in tool_names:
            self.child_calls += 1
            return self._child_result()
        if not self.launched:
            self.launched = True
            return self._launch_workflow()
        return self._parent_result()

    async def _launch_workflow(self):  # noqa: ANN202
        yield LLMMessage(
            role="assistant",
            content="launching",
            tool_calls=(
                LLMToolCall(
                    call_id="call-restart-resume",
                    name="Workflow",
                    arguments={"script": SCRIPT},
                ),
            ),
        )

    async def _parent_result(self):  # noqa: ANN202
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")

    async def _child_result(self):  # noqa: ANN202
        yield LLMMessage(role="assistant", content="fixed result", finish_reason="stop")


class _ResumeClient:
    def __init__(self) -> None:
        self.child_calls = 0

    def generate(self, request: Any):  # noqa: ANN201
        if "Workflow" not in {tool.name for tool in request.tools}:
            self.child_calls += 1
            raise AssertionError("completed Workflow child should replay from cache")
        return self._parent_result()

    async def _parent_result(self):  # noqa: ANN202
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


async def _allow_all(_tool: str, _input: Any, _context: Any) -> Any:
    from agent.sdk import PermissionDecision

    return PermissionDecision(behavior="allow")


def _build_kernel(tmp_path: Path, client: Any):
    return build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        workspace_config_dirname=".nanocode",
        global_config_root=tmp_path / "global",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=client,
    )


def _runtime() -> SessionRuntimeConfig:
    return SessionRuntimeConfig(
        model="test-model",
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=["Workflow"],
        features={},
    )


async def _wait_for_completed_run(kernel: Any, session_id: str) -> str:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        runs = kernel.list_workflow_runs(session_id=session_id)
        if runs and runs[0].status == "completed":
            return runs[0].run_id
        await asyncio.sleep(0.01)
    raise AssertionError("seed Workflow did not complete")


async def _seed_completed_run(tmp_path: Path) -> tuple[str, str, str, int]:
    client = _SeedClient()
    kernel = _build_kernel(tmp_path, client)
    try:
        owner = await kernel.create_session(workspace_root=tmp_path, runtime=_runtime())
        other = await kernel.create_session(workspace_root=tmp_path, runtime=_runtime())
        parent = kernel.submit(
            session_id=owner.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "run the Workflow"}],
            origin=RunOrigin.HUMAN,
        )
        deadline = asyncio.get_running_loop().time() + 3
        while asyncio.get_running_loop().time() < deadline:
            record = kernel.get_run(parent.run_id)
            if record is not None and record.status in {
                "completed",
                "failed",
                "cancelled",
            }:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("seed parent run did not complete")
        run_id = await _wait_for_completed_run(kernel, owner.session_id)
        return owner.session_id, other.session_id, run_id, client.child_calls
    finally:
        await kernel.aclose()


class _ResumeInputs:
    def __init__(self, *, kernel: Any, session_id: str, run_id: str) -> None:
        self._kernel = kernel
        self._session_id = session_id
        self._run_id = run_id
        self._index = 0

    def __call__(self, _prompt: str) -> str:
        self._index += 1
        if self._index == 1:
            return f"/workflows {self._run_id} resume"
        if self._index == 2:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                runs = self._kernel.list_workflow_runs(session_id=self._session_id)
                if len(runs) == 2 and all(run.status == "completed" for run in runs):
                    return "/workflows"
                time.sleep(0.01)
            raise AssertionError("resumed Workflow did not complete")
        return "/exit"


def test_cli_restart_restores_workflow_query_control_and_resume_scope(
    tmp_path: Path,
) -> None:
    owner_id, other_id, original_run_id, seed_child_calls = asyncio.run(
        _seed_completed_run(tmp_path)
    )
    assert seed_child_calls == 1

    resume_client = _ResumeClient()
    resumed_kernel = _build_kernel(tmp_path, resume_client)
    same_session_out = io.StringIO()
    exit_code = run_cli(
        ["--resume", owner_id],
        stdout=same_session_out,
        kernel_factory=lambda: resumed_kernel,
        input_fn=_ResumeInputs(
            kernel=resumed_kernel,
            session_id=owner_id,
            run_id=original_run_id,
        ),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert "failed to run /workflows" not in same_session_out.getvalue()
    assert original_run_id in same_session_out.getvalue()
    assert resume_client.child_calls == 0

    inspected_kernel = _build_kernel(tmp_path, _ResumeClient())
    try:
        inspected_kernel.list_session_tools(owner_id, workspace_root=tmp_path)
        runs = inspected_kernel.list_workflow_runs(session_id=owner_id)
        assert len(runs) == 2
        resumed = next(run for run in runs if run.resumed_from == original_run_id)
        assert resumed.status == "completed"
        assert resumed.agents[0].result == "fixed result"
        assert resumed.agents[0].status == "completed"

        tty_out = io.StringIO()
        keys = iter(["p", "q"])
        _run_workflow_tty_controls(
            out=tty_out,
            kernel=inspected_kernel,
            session_id=owner_id,
            key_reader=lambda: next(keys),
        )
        assert "Workflow control failed" not in tty_out.getvalue()
        assert original_run_id in tty_out.getvalue()
    finally:
        asyncio.run(inspected_kernel.aclose())

    cross_session_kernel = _build_kernel(tmp_path, _ResumeClient())
    cross_session_out = io.StringIO()
    commands = iter([f"/workflows {original_run_id} resume", "/exit"])
    cross_exit_code = run_cli(
        ["--resume", other_id],
        stdout=cross_session_out,
        kernel_factory=lambda: cross_session_kernel,
        input_fn=lambda _prompt: next(commands),
        workspace_root=tmp_path,
    )

    assert cross_exit_code == 0
    assert "different parent session" in cross_session_out.getvalue()
    assert "failed to run /workflows" not in cross_session_out.getvalue()
