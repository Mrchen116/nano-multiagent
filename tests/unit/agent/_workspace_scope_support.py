"""Shared fixtures for workspace execution-scope regressions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import tests.conftest as _conftest

from agent.platform.permissions.broker import PermissionDecision
from agent.sdk import LLMConfig, build_kernel


def kernel(tmp_path: Path, **kwargs: object):
    """Build a minimal kernel configured for one workspace-scope test."""

    return build_kernel(
        llm=LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD),
        tools=(),
        hooks=(),
        repo_root=tmp_path,
        **kwargs,
    )


def write_tool(workspace: Path, dirname: str, *, name: str, marker: str) -> None:
    """Write a lightweight workspace extension tool."""

    path = workspace / dirname / "tools" / f"{name}.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from typing import Any, Mapping\n\n"
        "class Tool:\n"
        f"    name = {name!r}\n"
        f"    description = {marker!r}\n"
        "    input_schema = {'type': 'object', 'properties': {}}\n"
        "    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:\n"
        f"        return {{'marker': {marker!r}}}\n\n"
        "TOOL = Tool()\n",
        encoding="utf-8",
    )


def write_hook(workspace: Path, dirname: str, *, marker: str) -> None:
    """Write an input hook that leaves a workspace-specific marker."""

    path = workspace / dirname / "hooks" / "scope_probe.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def setup(hooks):\n"
        "    def on_input(payload, ctx):\n"
        f"        return {{'action': 'transform', 'text': payload['text'] + {marker!r}}}\n"
        "    hooks.on('input', on_input, mode='intercept')\n",
        encoding="utf-8",
    )


def write_scope_config(workspace: Path, dirname: str, *, marker: str) -> None:
    """Write conflicting tool, policy, and auto-mode capabilities for one scope."""

    config_root = workspace / dirname
    write_tool(
        workspace,
        dirname,
        name=f"scope_probe_{marker}",
        marker=f"tool-{marker}",
    )
    write_hook(workspace, dirname, marker=f"-hook-{marker}")
    (config_root / "config.yaml").write_text(
        f"auto_mode:\n  always_allow_tools: [scope_probe_{marker}]\n",
        encoding="utf-8",
    )
    (config_root / "policy.toml").write_text(
        f'[bash]\nallow_prefixes = ["echo scope-{marker}"]\n',
        encoding="utf-8",
    )


def write_skill(workspace: Path, dirname: str, *, name: str, marker: str) -> None:
    """Write one valid workspace skill."""

    path = workspace / dirname / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {marker}\n---\n\n{marker}\n",
        encoding="utf-8",
    )


async def allow_all(_tool: str, _tool_input: Any, _context: Any) -> PermissionDecision:
    """Approve test tool calls without exercising an interactive client."""

    return PermissionDecision(behavior="allow")


async def wait_for_terminal(kernel: Any, run_id: str) -> None:
    """Wait for one submitted public run to finish."""

    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"run did not finish: {run_id}")


async def run_turn_and_collect(
    kernel: Any, session_id: str, workspace: Path, text: str
) -> list[dict[str, Any]]:
    """Run one real turn and collect its event stream through terminal status."""

    events: list[dict[str, Any]] = []
    run = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=workspace,
    )
    async for event in kernel.stream(session_id):
        events.append(event)
        if (
            event.get("event") == "run_status"
            and event.get("run_id") == run.run_id
            and event.get("status") in {"completed", "failed", "cancelled"}
        ):
            return events
    raise AssertionError(
        f"stream ended before run {run.run_id} reached a terminal status"
    )
