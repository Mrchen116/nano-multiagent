from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import (
    LLMConfig,
    PromptSlots,
    SessionRuntimeConfig,
    WorkflowControlAction,
    WorkflowRunInfo,
    WorkflowSaveScope,
    build_kernel,
)


SCRIPT = """
meta = {"name": "sdk-demo", "description": "Wait until stopped"}

async def main():
    while True:
        pass
"""


class _WorkflowCallingClient:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def generate(self, request: Any):  # noqa: ANN201
        self.requests.append(request)
        if len(self.requests) == 1:
            return self._call_workflow()
        return self._finish()

    async def _call_workflow(self):  # noqa: ANN202
        yield LLMMessage(
            role="assistant",
            content="launching",
            tool_calls=(
                LLMToolCall(
                    call_id="call-workflow",
                    name="Workflow",
                    arguments={"script": SCRIPT},
                ),
            ),
        )

    async def _finish(self):  # noqa: ANN202
        yield LLMMessage(role="assistant", content="launched", finish_reason="stop")


async def _allow_all(_tool: str, _input: Any, _context: Any) -> Any:
    from agent.sdk import PermissionDecision

    return PermissionDecision(behavior="allow")


async def _wait_parent(kernel: Any, run_id: str) -> None:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        run = kernel.get_run(run_id)
        if run is not None and run.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("parent run did not finish")


async def _wait_workflow(kernel: Any, session_id: str, status: str) -> WorkflowRunInfo:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        runs = kernel.list_workflow_runs(session_id=session_id)
        if runs and runs[0].status == status:
            return runs[0]
        await asyncio.sleep(0.01)
    raise AssertionError(f"Workflow did not reach {status}")


async def test_kernel_workflow_management_surface_owns_query_control_and_save(
    tmp_path: Path,
) -> None:
    client = _WorkflowCallingClient()
    kernel = build_kernel(
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
    runtime = SessionRuntimeConfig(
        model="test-model",
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=["Workflow"],
        features={},
        workflow_size_guideline="small",
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path, runtime=runtime)
        tools = kernel.list_session_tools(session.session_id, workspace_root=tmp_path)[
            "tools"
        ]
        workflow_spec = next(item for item in tools if item["name"] == "Workflow")
        assert "small — keep workflows under 5 agents" in workflow_spec["description"]

        parent = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "run it"}],
        )
        await _wait_parent(kernel, parent.run_id)
        request_workflow = next(
            tool for tool in client.requests[0].tools if tool.name == "Workflow"
        )
        assert "small — keep workflows under 5 agents" in request_workflow.description
        running = await _wait_workflow(kernel, session.session_id, "running")

        assert isinstance(running, WorkflowRunInfo)
        assert (
            kernel.get_workflow_run(
                session_id=session.session_id, run_id=running.run_id
            )
            == running
        )

        stopped = kernel.control_workflow(
            session_id=session.session_id,
            run_id=running.run_id,
            action=WorkflowControlAction.STOP,
        )
        assert stopped.run_id == running.run_id
        terminal = await _wait_workflow(kernel, session.session_id, "stopped")
        saved = kernel.save_workflow(
            session_id=session.session_id,
            run_id=terminal.run_id,
            scope=WorkflowSaveScope.PROJECT,
            name="saved-sdk-demo",
        )

        assert saved.name == "saved-sdk-demo"
        assert saved in kernel.list_named_workflows(workspace_root=tmp_path)
    finally:
        await kernel.aclose()


def test_inactive_workflow_guideline_does_not_change_runtime_identity() -> None:
    base = dict(
        model="test-model",
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=[],
        features={},
    )
    from agent.sdk.runtime import identify_runtime, runtime_metadata

    small = SessionRuntimeConfig(**base, workflow_size_guideline="small")
    large = SessionRuntimeConfig(**base, workflow_size_guideline="large")

    assert identify_runtime(small) == identify_runtime(large)
    assert (
        "workflow_size_guideline"
        not in runtime_metadata(small)["__nano_internal_runtime_v1__"]
    )


def test_active_workflow_default_and_explicit_medium_have_distinct_identity() -> None:
    from agent.sdk.runtime import identify_runtime, runtime_metadata

    base = dict(
        model="test-model",
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=["Workflow"],
        features={},
    )
    default = SessionRuntimeConfig(**base)
    explicit_medium = SessionRuntimeConfig(**base, workflow_size_guideline="medium")

    default_payload = runtime_metadata(default)["__nano_internal_runtime_v1__"]
    explicit_payload = runtime_metadata(explicit_medium)["__nano_internal_runtime_v1__"]

    assert identify_runtime(default) != identify_runtime(explicit_medium)
    assert "workflow_size_guideline" not in default_payload
    assert explicit_payload["workflow_size_guideline"] == "medium"
