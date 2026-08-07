"""Workspace capability scopes are fixed per root within one shared Kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncio
import pytest
import tests.conftest as _conftest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.session.types import SessionRef
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.permissions.broker import PermissionDecision
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


def _write_scope_config(
    workspace: Path,
    dirname: str,
    *,
    marker: str,
) -> None:
    """Write conflicting tool, policy, and auto-mode capabilities for one scope."""

    config_root = workspace / dirname
    _write_tool(
        workspace,
        dirname,
        name=f"scope_probe_{marker}",
        marker=f"tool-{marker}",
    )
    _write_hook(workspace, dirname, marker=f"-hook-{marker}")
    (config_root / "config.yaml").write_text(
        f"auto_mode:\n  always_allow_tools: [scope_probe_{marker}]\n",
        encoding="utf-8",
    )
    (config_root / "policy.toml").write_text(
        f'[bash]\nallow_prefixes = ["echo scope-{marker}"]\n',
        encoding="utf-8",
    )


def _write_skill(workspace: Path, dirname: str, *, name: str, marker: str) -> None:
    path = workspace / dirname / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {marker}\n---\n\n{marker}\n",
        encoding="utf-8",
    )


async def _allow_all(_tool: str, _tool_input: Any, _context: Any) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


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


class _EntryPointScopeLLM:
    """Drive slash-skill and child-agent entry points through real turns."""

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
        if getattr(request.messages[-1], "role", None) == "tool":
            return self._stop()
        if user_text.startswith("launch child"):
            return self._launch_child()
        if user_text.startswith("child scope"):
            return self._run_child_extension()
        return self._stop()

    async def _launch_child(self):
        yield LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id="launch-child",
                    name="agent",
                    arguments={
                        "description": "Run scoped child",
                        "prompt": "child scope",
                        "run_in_background": False,
                    },
                ),
            ),
            finish_reason=None,
        )
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")

    async def _run_child_extension(self):
        yield LLMMessage(
            role="assistant",
            content="",
            tool_calls=(
                LLMToolCall(
                    call_id="child-extension",
                    name="scope_probe_child",
                    arguments={},
                ),
            ),
            finish_reason=None,
        )
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")

    async def _stop(self):
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


class _CompactionSummary:
    async def summarize(self, **_kwargs: object) -> str:
        return "scope compaction summary"


async def _wait_for_terminal(kernel: Any, run_id: str) -> None:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"run did not finish: {run_id}")


async def _run_turn_and_collect(
    kernel: Any, session_id: str, workspace: Path, text: str
) -> list[dict[str, Any]]:
    """Run one real turn and collect the stream through its terminal event."""

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


@pytest.mark.asyncio
async def test_concurrent_pretool_scopes_keep_extensions_policy_config_and_output_isolated(
    tmp_path: Path,
) -> None:
    """Concurrent turns keep every selected pre-tool capability in its workspace."""

    workspace_a = tmp_path / "a"
    workspace_b = tmp_path / "b"
    _write_scope_config(workspace_a, ".consumer", marker="a")
    _write_scope_config(workspace_b, ".consumer", marker="b")
    llm = _ConcurrentScopeLLM()
    kernel = _kernel(
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
            _run_turn_and_collect(kernel, session_a.session_id, workspace_a, "run"),
            _run_turn_and_collect(kernel, session_b.session_id, workspace_b, "run"),
        )

        fork_a = await kernel.fork_session(
            session_a.session_id, workspace_root=workspace_a
        )
        fork_events_a = await _run_turn_and_collect(
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


@pytest.mark.asyncio
async def test_scope_is_preserved_by_slash_skill_subagent_and_compaction(
    tmp_path: Path,
) -> None:
    """Every side entry point keeps the originating custom workspace scope."""

    workspace_a = tmp_path / "skills-a"
    workspace_b = tmp_path / "skills-b"
    child_workspace = tmp_path / "child"
    _write_skill(
        workspace_a,
        ".consumer",
        name="scope-a",
        marker="scope-a skill content",
    )
    _write_skill(
        workspace_b,
        ".consumer",
        name="scope-b",
        marker="scope-b skill content",
    )
    _write_scope_config(child_workspace, ".consumer", marker="child")
    llm = _EntryPointScopeLLM()
    kernel = _kernel(
        tmp_path,
        workspace_config_dirname=".consumer",
        can_use_tool=_allow_all,
        _llm_client_override=llm,
    )
    try:
        session_a, session_b, parent = await asyncio.gather(
            kernel.create_session(workspace_root=workspace_a),
            kernel.create_session(workspace_root=workspace_b),
            kernel.create_session(workspace_root=child_workspace),
        )
        slash_events_a, slash_events_b = await asyncio.gather(
            _run_turn_and_collect(
                kernel, session_a.session_id, workspace_a, "/skill:scope-a"
            ),
            _run_turn_and_collect(
                kernel, session_b.session_id, workspace_b, "/skill:scope-b"
            ),
        )
        parent_events = await _run_turn_and_collect(
            kernel, parent.session_id, child_workspace, "launch child"
        )

        kernel._c.engine_services._compaction_summarizer = _CompactionSummary()  # noqa: SLF001
        compacted = await kernel.compact(
            session_a.session_id,
            workspace_root=workspace_a,
            idempotency_key="scope-compaction",
        )
        transcript_a = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session_a.session_id, workspace_root=workspace_a)
        )._transcript  # noqa: SLF001
        transcript_b = kernel._c.directory.open(  # noqa: SLF001
            SessionRef(session_id=session_b.session_id, workspace_root=workspace_b)
        )._transcript  # noqa: SLF001
        messages_a = [str(message.content) for message in transcript_a.load().messages]
        messages_b = [str(message.content) for message in transcript_b.load().messages]
        child_ref = kernel._c.directory.find_by_metadata(  # noqa: SLF001
            workspace_root=child_workspace,
            parent_session_id=parent.session_id,
            query={"kind": "subagent"},
        )
        assert child_ref is not None
        child_messages = [
            (message.role, str(message.content))
            for message in kernel._c.directory.open(child_ref)
            ._transcript.load()
            .messages  # noqa: SLF001
        ]
    finally:
        kernel.close()

    assert compacted is not None
    slash_a_results = [
        event for event in slash_events_a if event.get("event") == "tool_end"
    ]
    slash_b_results = [
        event for event in slash_events_b if event.get("event") == "tool_end"
    ]
    assert any(event.get("name") == "skill_view" for event in slash_a_results)
    assert any(event.get("name") == "skill_view" for event in slash_b_results)

    assert any(
        "system-reminder" in content and "scope-a skill content" in content
        for content in messages_a
    )
    assert not any(
        "system-reminder" in content and "scope-b skill content" in content
        for content in messages_a
    )
    assert any("scope-b skill content" in content for content in messages_b)
    assert not any("scope-a skill content" in content for content in messages_b)

    assert any(
        event.get("event") == "tool_end" and event.get("name") == "agent"
        for event in parent_events
    )
    assert any(
        role == "tool" and "tool-child" in content for role, content in child_messages
    )
    assert "child scope-hook-child" in llm.user_texts
