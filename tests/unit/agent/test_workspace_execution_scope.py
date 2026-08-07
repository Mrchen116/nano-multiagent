"""Workspace capability scopes are fixed per root within one shared Kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncio
import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.platform.config.auto_mode import AutoModeConfig
from tests.unit.agent._workspace_scope_support import (
    kernel as make_kernel,
    run_turn_and_collect,
    wait_for_terminal,
    write_hook,
    write_scope_config,
    write_tool,
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


class _ConcurrentScopeLLM:
    """Issue one workspace-specific extension and background bash call per turn."""

    def __init__(self) -> None:
        self.user_texts: list[str] = []

    def generate(self, request: Any):  # noqa: ANN201
        user_text = next(
            (
                str(message.content)
                for message in reversed(request.messages)
                if getattr(message, "role", None) == "user"
            ),
            "",
        )
        self.user_texts.append(user_text)
        if user_text.startswith("<task-notification>"):
            return self._stop()
        if getattr(request.messages[-1], "role", None) == "tool":
            return self._stop()
        marker = "a" if user_text.endswith("-hook-a") else "b"
        return self._tools(marker)

    async def _tools(self, marker: str):
        yield LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id=f"scope-{marker}",
                    name=f"scope_probe_{marker}",
                    arguments={},
                ),
                LLMToolCall(
                    call_id=f"bash-{marker}",
                    name="bash",
                    arguments={
                        "command": f"echo scope-{marker}",
                        "description": f"scope {marker} output",
                        "run_in_background": True,
                    },
                ),
            ),
            finish_reason=None,
        )
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")

    async def _stop(self):
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


def test_workspace_extensions_are_isolated_and_cached_per_root(tmp_path: Path) -> None:
    """One Kernel exposes only the selected workspace's extension snapshot."""

    workspace_a = tmp_path / "a"
    workspace_b = tmp_path / "b"
    write_tool(workspace_a, ".consumer", name="scope_probe", marker="tool-a")
    write_tool(workspace_b, ".consumer", name="scope_probe", marker="tool-b")
    write_hook(workspace_a, ".consumer", marker="-hook-a")
    write_hook(workspace_b, ".consumer", marker="-hook-b")

    kernel = make_kernel(tmp_path, workspace_config_dirname=".consumer")

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
    write_tool(workspace, ".nano", name="default_scope_probe", marker="default")
    kernel = make_kernel(tmp_path)

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

    no_global = make_kernel(tmp_path, workspace_config_dirname=".consumer")
    with_global = make_kernel(
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
    write_hook(workspace_a, ".consumer", marker="-a")
    write_hook(workspace_b, ".consumer", marker="-b")
    llm = _CapturingLLM()
    kernel = make_kernel(
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
        await wait_for_terminal(kernel, run_a.run_id)
        run_b = kernel.submit(
            session_id=session_b.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=workspace_b,
        )
        await wait_for_terminal(kernel, run_b.run_id)
    finally:
        kernel.close()

    assert "hello-a" in llm.user_texts
    assert "hello-b" in llm.user_texts


@pytest.mark.asyncio
async def test_concurrent_pretool_scopes_keep_extensions_policy_config_and_output_isolated(
    tmp_path: Path,
) -> None:
    """Concurrent turns keep every selected pre-tool capability in its workspace."""

    workspace_a = tmp_path / "a"
    workspace_b = tmp_path / "b"
    write_scope_config(workspace_a, ".consumer", marker="a")
    write_scope_config(workspace_b, ".consumer", marker="b")
    llm = _ConcurrentScopeLLM()
    kernel = make_kernel(
        tmp_path,
        workspace_config_dirname=".consumer",
        _llm_client_override=llm,
    )
    try:
        session_a, session_b = await asyncio.gather(
            kernel.create_session(workspace_root=workspace_a),
            kernel.create_session(workspace_root=workspace_b),
        )
        events_a, events_b = await asyncio.gather(
            run_turn_and_collect(kernel, session_a.session_id, workspace_a, "run"),
            run_turn_and_collect(kernel, session_b.session_id, workspace_b, "run"),
        )

        fork_a = await kernel.fork_session(
            session_a.session_id, workspace_root=workspace_a
        )
        fork_events_a = await run_turn_and_collect(
            kernel, fork_a.session_id, workspace_a, "run again"
        )

        tools_a = kernel.list_session_tools(
            session_a.session_id, workspace_root=workspace_a
        )
        tools_b = kernel.list_session_tools(
            session_b.session_id, workspace_root=workspace_b
        )
    finally:
        kernel.close()

    assert "run-hook-a" in llm.user_texts
    assert "run-hook-b" in llm.user_texts
    assert "run again-hook-a" in llm.user_texts
    names_a = {tool["name"] for tool in tools_a["tools"]}
    names_b = {tool["name"] for tool in tools_b["tools"]}
    assert {"scope_probe_a", "bash"} <= names_a
    assert "scope_probe_b" not in names_a
    assert {"scope_probe_b", "bash"} <= names_b
    assert "scope_probe_a" not in names_b

    for marker, events in (("a", events_a), ("b", events_b), ("a", fork_events_a)):
        tool_ends = [event for event in events if event.get("event") == "tool_end"]
        assert any(event.get("name") == f"scope_probe_{marker}" for event in tool_ends)
        assert any(event.get("name") == "bash" for event in tool_ends)

    a_outputs = list((workspace_a / ".consumer" / "background-tasks").rglob("*.output"))
    b_outputs = list((workspace_b / ".consumer" / "background-tasks").rglob("*.output"))
    assert len(a_outputs) == 2
    assert len(b_outputs) == 1
    assert not list((workspace_a / ".nano" / "background-tasks").rglob("*.output"))
    assert not list((workspace_b / ".nano" / "background-tasks").rglob("*.output"))
