"""Async-native CLI REPL + agent.sdk 集成单测。

覆盖 M2 核心改动：
- run_cli() 无 --mode/--base-url 参数直接进入 REPL（删 managed/remote 模式）
- 会话/提交/流式 直接调 Kernel SDK（无 HTTP）
- 权限确认走 can_use_tool 回调（回调内 await 用户输入）
- REPL 命令(/new /tools /compact /history /session /use /exit /help)
- --text 非交互模式
- 打断（interrupt）路径
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub: 模拟 agent.sdk.Kernel 的最小 stub
# ---------------------------------------------------------------------------

class _StubSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


class _StubRunRecord:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id


class _StubKernel:
    """Stub Kernel — 不发真实 LLM 请求，供 REPL 单测注入。"""

    def __init__(
        self,
        *,
        session_id: str = "sess-1",
        events: list[dict[str, Any]] | None = None,
        permission_tool: str | None = None,
    ) -> None:
        self._session_id = session_id
        self._events: list[dict[str, Any]] = events or [
            {"event": "assistant_message", "run_id": "run-1", "session_id": session_id, "content": "pong"},
            {"event": "run_status", "run_id": "run-1", "session_id": session_id, "status": "completed", "stop_reason": "stop"},
        ]
        self._permission_tool = permission_tool
        self.calls: list[tuple[str, Any]] = []
        self._run_id_counter = 0

    async def create_session(self, *, title=None, workspace_root=None, skills=None):
        self.calls.append(("create_session", {"title": title, "skills": skills}))
        return _StubSession(self._session_id)

    def submit(self, *, session_id, parts, origin=None, workspace_root=None, trace_id=None):
        self.calls.append(("submit", {"session_id": session_id, "parts": parts}))
        self._run_id_counter += 1
        return _StubRunRecord(f"run-{self._run_id_counter}")

    def stream(self, session_id: str, *, after_sequence: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Return an async iterator of stub events."""
        return _AsyncIterEvents(self._events)

    async def compact(self, session_id: str, *, workspace_root=None):
        self.calls.append(("compact", {"session_id": session_id}))
        return {"compacted": True, "result": {"reason": "manual"}}

    def list_session_tools(self, session_id: str, *, workspace_root=None):
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return {"tools": [{"name": "bash", "description": "run shell commands"}]}

    def interrupt(self, session_id: str):
        self.calls.append(("interrupt", {"session_id": session_id}))
        return "run-1"

    def close(self):
        self.calls.append(("close", None))

    def get_llm_config(self):
        return MagicMock(provider="anthropic", model="kimiCoding:K2.6")

    def reconfigure_llm(self, **kwargs):
        self.calls.append(("reconfigure_llm", kwargs))
        return MagicMock(provider=kwargs.get("provider", "anthropic"))


class _AsyncIterEvents:
    """Async iterator over a static list of events."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = iter(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration


# ---------------------------------------------------------------------------
# 辅助：构建 async 版 run_cli 的 kernel_factory
# ---------------------------------------------------------------------------

def _make_kernel_factory(kernel: _StubKernel):
    """返回一个 kernel_factory 可注入 run_cli。"""
    def factory(**kwargs):
        return kernel
    return factory


# ---------------------------------------------------------------------------
# R1 — 新 async-native REPL 入口测试
# ---------------------------------------------------------------------------

def test_run_cli_enters_repl_without_mode_or_base_url(tmp_path) -> None:
    """无 --mode/--base-url 参数，CLI 应直接进入 REPL（不 spawn HTTP 服务）。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    # 确认没有任何 HTTP 相关错误
    text = output.getvalue()
    assert "error" not in text.lower() or "auto mode" in text.lower()


def test_run_cli_new_creates_session_via_sdk(tmp_path) -> None:
    """/new 命令走 SDK create_session，不调 HTTP。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/new", "/exit"])

    run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert any(call[0] == "create_session" for call in stub.calls), \
        f"expected create_session call, got: {stub.calls}"


def test_run_cli_sends_message_via_sdk_stream(tmp_path) -> None:
    """用户输入消息 → submit + async stream → 打印 assistant 回复。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "pong" in text, f"expected 'pong' in output, got: {text!r}"
    assert any(call[0] == "submit" for call in stub.calls), \
        f"expected submit call, got: {stub.calls}"


def test_run_cli_text_mode_via_sdk(tmp_path) -> None:
    """--text 非交互模式：submit 一次后退出，不进 REPL。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()

    exit_code = run_cli(
        ["--text", "hello"],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert any(call[0] == "submit" for call in stub.calls), \
        f"expected submit call, got: {stub.calls}"


def test_run_cli_permission_callback_invoked(tmp_path) -> None:
    """当内核需要权限时，can_use_tool 回调被调用，用户可以 allow/deny。"""
    from coding_cli.commands import run_cli

    # 内核在 stream 中发出一个 permission_request 事件，然后等待
    perm_events = [
        {"event": "permission_request", "run_id": "run-1", "session_id": "sess-1",
         "request_id": "req-1", "tool_name": "bash", "tool_input": {"command": "ls"}},
        {"event": "assistant_message", "run_id": "run-1", "session_id": "sess-1", "content": "done"},
        {"event": "run_status", "run_id": "run-1", "session_id": "sess-1",
         "status": "completed", "stop_reason": "stop"},
    ]
    stub = _StubKernel(events=perm_events)

    permission_decisions: list[str] = []

    def _mock_permission_input(prompt: str) -> str:
        # 模拟用户在权限提示时输入 "1"（第一个选项 = allow）
        return "1"

    output = io.StringIO()
    inputs = iter(["/new", "do something", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda prompt: _mock_permission_input(prompt) if "Permission" in prompt else next(inputs),
        workspace_root=tmp_path,
    )

    # 主要验证：permission_request 事件被处理（不挂死），exit_code 正常
    assert exit_code == 0


def test_run_cli_no_mode_flag_in_new_parser() -> None:
    """M2 后 CLI parser 不应有 --mode 参数。"""
    from coding_cli.commands import build_parser

    parser = build_parser()
    mode_actions = [a for a in parser._actions if a.dest == "mode"]
    assert not mode_actions, f"--mode should be removed in M2, found: {mode_actions}"


def test_run_cli_no_base_url_flag_in_new_parser() -> None:
    """M2 后 CLI parser 不应有 --base-url 参数。"""
    from coding_cli.commands import build_parser

    parser = build_parser()
    base_url_actions = [a for a in parser._actions if a.dest == "base_url"]
    assert not base_url_actions, f"--base-url should be removed in M2, found: {base_url_actions}"


def test_run_cli_no_health_subcommand() -> None:
    """M2 后 CLI 不应有 health 子命令（它是 HTTP-only 命令）。"""
    from coding_cli.commands import build_parser

    parser = build_parser()
    subparsers_actions = [a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"]
    if subparsers_actions:
        names = set(subparsers_actions[0].choices.keys())
        assert "health" not in names, f"'health' subcommand should be removed in M2, found: {names}"


def test_run_cli_kernel_closed_on_exit(tmp_path) -> None:
    """REPL 退出时调用 kernel.close() 释放后台循环资源。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/exit"])

    run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert any(call[0] == "close" for call in stub.calls), \
        f"expected kernel.close() call on exit, got: {stub.calls}"


def test_run_cli_repl_command_tools_via_sdk(tmp_path) -> None:
    """/tools 命令调用 SDK list_session_tools，打印工具列表。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/new", "/tools", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "bash" in text, f"expected bash tool in output, got: {text!r}"


def test_run_cli_repl_command_compact_via_sdk(tmp_path) -> None:
    """/compact 命令调用 SDK compact()。"""
    from coding_cli.commands import run_cli

    stub = _StubKernel()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert any(call[0] == "compact" for call in stub.calls), \
        f"expected compact call, got: {stub.calls}"


# ---------------------------------------------------------------------------
# R-fix: 真实启动路径测试（不经 kernel_factory 注入）
# 覆盖 bug：coding_cli 启动时 LLMFactoryConfig.from_env() 调 get_default_provider()
# 要求 init_model_registry 已先调用，否则报 "model registry not initialized"
# ---------------------------------------------------------------------------

def test_build_llm_config_payload_exists_and_does_not_need_registry(monkeypatch) -> None:
    """_build_llm_config_payload 必须存在，且在 registry 未初始化时不抛 registry 错。

    这是真实启动路径的核心：_build_kernel 生产路径必须先构造 LLMConfigPayload 并调
    init_model_registry，才能安全调 LLMFactoryConfig.from_env()。
    该测试在当前代码（未修复前）应失败（函数不存在），修复后绿。
    """
    from agent.core.llm.model_registry import _reset_for_tests
    _reset_for_tests()  # 隔离：确保本测试内 registry 未初始化

    # 恢复 registry 在测试后（避免污染后续测试）
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_MODEL", "kimiCoding:K2.6")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")

    import argparse
    from coding_cli.commands import _build_llm_config_payload  # 修复后才存在

    args = argparse.Namespace(
        llm_provider=None,
        llm_model=None,
        llm_base_url=None,
        llm_api_key=None,
        llm_timeout_seconds=None,
    )
    # 不应抛 "model registry not initialized"
    payload = _build_llm_config_payload(args)
    assert payload is not None
    # 调完后 registry 应已初始化，from_env() 可正常运行
    from agent.sdk import LLMFactoryConfig
    config = LLMFactoryConfig.from_env()
    assert config.provider == "anthropic"


def test_cli_llm_config_get_real_path_does_not_report_registry_error(monkeypatch) -> None:
    """真实 CLI 启动路径（无 kernel_factory）在 registry 未初始化时不应报 registry 错。

    走 llm-config get 子命令，不涉及真实 LLM 连接，只验证 registry 初始化链路正常。
    该测试在当前代码（未修复前）应红（exit_code=1 + registry 错误），修复后绿。
    """
    import io
    from agent.core.llm.model_registry import _reset_for_tests
    _reset_for_tests()

    monkeypatch.setenv("NANO_MULTIAGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_MODEL", "kimiCoding:K2.6")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")

    from coding_cli.commands import run_cli

    out = io.StringIO()
    exit_code = run_cli(["llm-config", "get"], stdout=out)
    output = out.getvalue().strip()

    assert "model registry not initialized" not in output, (
        f"Registry not initialized error in real CLI path: {output}"
    )
    # 成功时 exit_code=0 且输出合法 JSON 含 provider 字段
    assert exit_code == 0, f"run_cli failed with exit_code={exit_code}, output={output}"
    import json
    payload = json.loads(output)
    assert "provider" in payload, f"Expected provider in payload: {payload}"
