"""Workspace capability scopes are fixed per root within one shared Kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncio
import pytest
import tests.conftest as _conftest

from agent.core.llm.interfaces import LLMMessage
from agent.platform.config.auto_mode import AutoModeConfig
from agent.sdk import LLMConfig, build_kernel


def _kernel(tmp_path: Path, **kwargs: object):
    return build_kernel(
        llm=LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD),
        tools=(),
        hooks=(),
        repo_root=tmp_path,
        **kwargs,
    )


def _write_tool(workspace: Path, dirname: str, *, name: str, marker: str) -> None:
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


def _write_hook(workspace: Path, dirname: str, *, marker: str) -> None:
    path = workspace / dirname / "hooks" / "scope_probe.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def setup(hooks):\n"
        "    def on_input(payload, ctx):\n"
        f"        return {{'action': 'transform', 'text': payload['text'] + {marker!r}}}\n"
        "    hooks.on('input', on_input, mode='intercept')\n",
        encoding="utf-8",
    )


class _CapturingLLM:
    """Complete one turn while recording the user text after scope hooks run."""

    def __init__(self) -> None:
        self.user_texts: list[str] = []

    def generate(self, request: Any):  # noqa: ANN201
        self.user_texts.extend(
            str(message.content)
            for message in request.messages
            if getattr(message, "role", None) == "user"
        )
        return self._stream()

    async def _stream(self):
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


async def _wait_for_terminal(kernel: Any, run_id: str) -> None:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"run did not finish: {run_id}")


def test_workspace_extensions_are_isolated_and_cached_per_root(tmp_path: Path) -> None:
    """One Kernel exposes only the selected workspace's extension snapshot."""

    workspace_a = tmp_path / "a"
    workspace_b = tmp_path / "b"
    _write_tool(workspace_a, ".consumer", name="scope_probe", marker="tool-a")
    _write_tool(workspace_b, ".consumer", name="scope_probe", marker="tool-b")
    _write_hook(workspace_a, ".consumer", marker="-hook-a")
    _write_hook(workspace_b, ".consumer", marker="-hook-b")

    kernel = _kernel(tmp_path, workspace_config_dirname=".consumer")

    scope_a = kernel._scope_for(workspace_a)  # noqa: SLF001
    scope_b = kernel._scope_for(workspace_b)  # noqa: SLF001
    assert scope_a is kernel._scope_for(workspace_a)  # noqa: SLF001
    assert scope_a is not scope_b
    assert scope_a.layout.config_root == workspace_a / ".consumer"
    assert scope_b.layout.config_root == workspace_b / ".consumer"
    assert scope_a.tool_registry.get("scope_probe").description == "tool-a"
    assert scope_b.tool_registry.get("scope_probe").description == "tool-b"
    assert scope_a.hook_runner.registry is not scope_b.hook_runner.registry


def test_default_workspace_directory_remains_nano(tmp_path: Path) -> None:
    """An SDK consumer that omits the option keeps the .nano layout."""

    workspace = tmp_path / "workspace"
    _write_tool(workspace, ".nano", name="default_scope_probe", marker="default")
    kernel = _kernel(tmp_path)

    scope = kernel._scope_for(workspace)  # noqa: SLF001
    assert scope is not None
    assert scope.layout.config_dirname == ".nano"
    assert scope.tool_registry.get("default_scope_probe") is not None


def test_global_auto_mode_root_is_opt_in(tmp_path: Path) -> None:
    """Omitting global_config_root never reads an arbitrary deployment home."""

    workspace = tmp_path / "workspace"
    global_root = tmp_path / "global"
    global_root.mkdir()
    (global_root / "config.yaml").write_text(
        "auto_mode:\n  deny_limit: 9\n", encoding="utf-8"
    )

    no_global = _kernel(tmp_path, workspace_config_dirname=".consumer")
    with_global = _kernel(
        tmp_path,
        workspace_config_dirname=".consumer",
        global_config_root=global_root,
    )

    assert no_global._scope_for(workspace).auto_mode_config_loader() == AutoModeConfig()  # noqa: SLF001
    assert with_global._scope_for(workspace).auto_mode_config_loader().deny_limit == 9  # noqa: SLF001


@pytest.mark.asyncio
async def test_turn_uses_its_workspace_hook_scope(tmp_path: Path) -> None:
    """Two sessions on one Kernel dispatch only their own workspace hook layer."""

    workspace_a = tmp_path / "a"
    workspace_b = tmp_path / "b"
    _write_hook(workspace_a, ".consumer", marker="-a")
    _write_hook(workspace_b, ".consumer", marker="-b")
    llm = _CapturingLLM()
    kernel = _kernel(
        tmp_path,
        workspace_config_dirname=".consumer",
        _llm_client_override=llm,
    )
    try:
        session_a = await kernel.create_session(workspace_root=workspace_a)
        session_b = await kernel.create_session(workspace_root=workspace_b)
        run_a = kernel.submit(
            session_id=session_a.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=workspace_a,
        )
        await _wait_for_terminal(kernel, run_a.run_id)
        run_b = kernel.submit(
            session_id=session_b.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=workspace_b,
        )
        await _wait_for_terminal(kernel, run_b.run_id)
    finally:
        kernel.close()

    assert "hello-a" in llm.user_texts
    assert "hello-b" in llm.user_texts
