"""Workspace scope regressions for forked and terminal observer hooks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage
from tests.unit.agent._workspace_scope_support import (
    kernel,
    run_turn_and_collect,
)


class _StopLLM:
    """Finish a normal turn and a compaction-summary fork."""

    def generate(self, _request: Any):  # noqa: ANN201
        return self._stream()

    async def _stream(self):
        yield LLMMessage(role="assistant", content="summary", finish_reason="stop")


class _FailingLLM:
    """Make the registry publish a terminal run_error event."""

    def generate(self, _request: Any):  # noqa: ANN201
        raise RuntimeError("workspace scope failure")


def _write_observer_hook(workspace: Path, event: str, output: Path) -> None:
    """Install an observer that records the scope it received."""

    path = workspace / ".consumer" / "hooks" / "observe_scope.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def setup(hooks):\n"
        "    def observe(payload, ctx):\n"
        "        del payload\n"
        f"        with open({str(output)!r}, 'a', encoding='utf-8') as stream:\n"
        "            stream.write(str(ctx.metadata['workspace_config_dirname']) + '\\n')\n"
        f"    hooks.on({event!r}, observe)\n",
        encoding="utf-8",
    )


async def _wait_for_output(path: Path) -> str:
    """Wait for the registry's terminal observer task to complete."""

    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        if path.is_file():
            return path.read_text(encoding="utf-8")
        await asyncio.sleep(0.01)
    raise AssertionError(f"observer did not write {path}")


@pytest.mark.asyncio
async def test_manual_compaction_summary_keeps_workspace_hook_scope(
    tmp_path: Path,
) -> None:
    """The summary fork dispatches through the originating workspace hooks."""

    workspace = tmp_path / "workspace"
    output = tmp_path / "compaction-hooks.log"
    _write_observer_hook(workspace, "turn_start", output)
    live_kernel = kernel(
        workspace,
        workspace_config_dirname=".consumer",
        _llm_client_override=_StopLLM(),
    )
    try:
        session = await live_kernel.create_session(workspace_root=workspace)
        live_kernel.append_message(
            session.session_id,
            workspace_root=workspace,
            role="user",
            content="Retain this context.",
            message_id="seed-user",
        )
        result = await live_kernel.compact(
            session.session_id,
            workspace_root=workspace,
            idempotency_key="workspace-hook-scope",
        )
        recorded = await _wait_for_output(output)
    finally:
        live_kernel.close()

    assert result is not None
    assert recorded == ".consumer\n"


@pytest.mark.asyncio
async def test_failed_run_uses_its_workspace_hook_scope(tmp_path: Path) -> None:
    """Terminal run_error dispatch selects the failed run's workspace hooks."""

    workspace = tmp_path / "workspace"
    output = tmp_path / "run-error-hooks.log"
    _write_observer_hook(workspace, "run_error", output)
    live_kernel = kernel(
        workspace,
        workspace_config_dirname=".consumer",
        _llm_client_override=_FailingLLM(),
    )
    try:
        session = await live_kernel.create_session(workspace_root=workspace)
        events = await run_turn_and_collect(
            live_kernel, session.session_id, workspace, "trigger failure"
        )
        recorded = await _wait_for_output(output)
    finally:
        live_kernel.close()

    assert any(
        event.get("event") == "run_status" and event.get("status") == "failed"
        for event in events
    )
    assert recorded == ".consumer\n"
