"""Tests for AgentTool background/foreground/continuation paths."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.agent import AgentTool


class _FakeSession:
    def __init__(self, session_id: str):
        self.session_id = session_id


class _FakeTurnResult:
    def __init__(self, content: str = "hello result"):
        self.messages = (_FakeMessage(content),)
        self.usage = None
        self.tool_calls = ()


class _FakeMessage:
    def __init__(self, content: str):
        self.role = "assistant"
        self.content = content


class _FakeStopper:
    def stop(self) -> None:
        pass


class _FakeRunner:
    def start(
        self,
        *,
        agent_session_id,
        parent_session_id,
        prompt,
        on_complete,
        on_fail,
        workspace_root=None,
    ):
        def _worker():
            time.sleep(0.05)
            on_complete(
                task_id=agent_session_id,
                result_text="done",
                usage=None,
                duration_ms=50,
                tool_use_count=0,
            )

        import threading

        threading.Thread(target=_worker, daemon=True).start()
        return _FakeStopper()

    def submit_foreground(self, coro):
        """Run the bare runtime.run(...) coroutine and return a Future.

        Mirrors the real RuntimeRunner.submit_foreground contract (bugfix-418):
        the foreground path goes through this method instead of bare asyncio.run
        inside AgentTool, so the subagent turn runs on the kernel's dedicated
        loop rather than a transient one.
        """
        import asyncio
        import threading
        from concurrent.futures import Future

        future: Future = Future()

        def _runner():
            try:
                future.set_result(asyncio.run(coro))
            except BaseException as exc:  # noqa: BLE001
                future.set_exception(exc)

        threading.Thread(target=_runner, daemon=True).start()
        return future


async def _fake_create_session(*args, **kwargs):
    return _FakeSession("sess_123")


def _make_tool(*, with_wiring: bool = True) -> AgentTool:
    runtime = MagicMock()
    runtime.create_session = _fake_create_session
    runtime._session_manager.store.resolve_path.return_value = Path(
        "/tmp/sess_123.jsonl"
    )
    runtime._session_manager.store.find_session_by_metadata.return_value = None

    wiring = None
    if with_wiring:
        registry = BackgroundTaskRegistry()
        wiring = MagicMock()
        wiring.registry = registry
        wiring.subagent_runner = _FakeRunner()

    tool = AgentTool(runtime=runtime, wiring=wiring)
    return tool


def _make_ctx(tmpdir: str) -> ToolContext:
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    safety = ToolSafety(repo_root=Path(tmpdir), config=ToolSafetyConfig())
    return ToolContext(
        repo_root=Path(tmpdir), cwd=Path(tmpdir), safety=safety, session_id="parent_1"
    )


# ------------------------------------------------------------------
# Background launch
# ------------------------------------------------------------------


def test_background_launch_returns_async_launched() -> None:
    tool = _make_tool()
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "description": "test task",
                "prompt": "do something",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": True,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["agent_id"].startswith("a")
        assert "output_file" in result


# ------------------------------------------------------------------
# Foreground completion
# ------------------------------------------------------------------


async def _fake_run_fast(*args, **kwargs):
    return _FakeTurnResult("sync result")


def test_foreground_completes_within_budget() -> None:
    tool = _make_tool(with_wiring=True)
    # Mock the runtime.run to return a coroutine
    tool._runtime.run = _fake_run_fast

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "description": "test task",
                "prompt": "do something",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
            },
            ctx,
        )
        assert result["status"] == "completed"
        assert result["content"] == "sync result"


def test_foreground_in_budget_does_not_register_subagent() -> None:
    """bugfix-418 decision 2 / bugfix-417 invariant: in-budget foreground
    completion must NOT register into BackgroundTaskRegistry — registration is
    what would later emit a <task-notification>, so an in-budget call that both
    returns inline AND notifies would be the double-channel regression.
    """
    tool = _make_tool(with_wiring=True)
    tool._runtime.run = _fake_run_fast

    registry = tool._wiring.registry
    register_calls: list[str] = []
    original_register = registry.register_subagent

    def _spy_register(*args, **kwargs):
        register_calls.append(kwargs.get("agent_id", "?"))
        return original_register(*args, **kwargs)

    registry.register_subagent = _spy_register  # type: ignore[method-assign]

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "description": "test task",
                "prompt": "do something",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
            },
            ctx,
        )
        assert result["status"] == "completed"
        assert register_calls == [], (
            "in-budget foreground subagent must not register into the "
            "background-task registry (would trigger a <task-notification>)"
        )


# ------------------------------------------------------------------
# Foreground auto-background
# ------------------------------------------------------------------


def test_foreground_auto_backgrounds_on_timeout() -> None:
    tool = _make_tool()
    # Make runtime.run sleep longer than the budget
    slow_result = _FakeTurnResult("slow result")

    async def _slow_run(*args, **kwargs):
        time.sleep(2.0)
        return slow_result

    tool._runtime.run = _slow_run

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        # Use a very short timeout
        result = tool.run(
            {
                "description": "slow task",
                "prompt": "do something slow",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
                "timeout_seconds": 0.1,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["agent_id"].startswith("a")


# ------------------------------------------------------------------
# Continuation: running agent
# ------------------------------------------------------------------


def test_continuation_to_running_agent_queues_message() -> None:
    tool = _make_tool()
    registry = tool._wiring.registry

    # Pre-register a running agent
    agent_id = "a1234567890abcdef"
    registry.register_subagent(
        task_id=agent_id,
        parent_session_id="parent_1",
        agent_id=agent_id,
        agent_session_id="sess_running",
        description="existing",
        prompt="original",
        agent_type="explore",
        output_file="/tmp/out.jsonl",
    )
    registry.mark_running(agent_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "agent_id": agent_id,
                "prompt": "follow up",
                "load_skills": [],
                "description": "existing",
            },
            ctx,
        )
        assert result["status"] == "message_queued"
        assert result["agent_id"] == agent_id
        messages = registry.drain_agent_messages(agent_id)
        assert messages == ("follow up",)


# ------------------------------------------------------------------
# Continuation: terminal agent in memory
# ------------------------------------------------------------------


def test_continuation_to_terminal_agent_resumes() -> None:
    tool = _make_tool()
    registry = tool._wiring.registry

    agent_id = "a1234567890abcdef"
    registry.register_subagent(
        task_id=agent_id,
        parent_session_id="parent_1",
        agent_id=agent_id,
        agent_session_id="sess_terminal",
        description="existing",
        prompt="original",
        agent_type="explore",
        output_file="/tmp/out.jsonl",
    )
    registry.mark_running(agent_id)
    registry.complete(agent_id, result_text="done")

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "agent_id": agent_id,
                "prompt": "follow up",
                "load_skills": [],
                "description": "existing",
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["agent_id"] == agent_id


# ------------------------------------------------------------------
# JSONL rehydrate
# ------------------------------------------------------------------


def test_continuation_falls_back_to_jsonl_rehydrate() -> None:
    tool = _make_tool(with_wiring=False)
    runtime = tool._runtime

    # No in-memory registry; JSONL should find it
    runtime._session_manager.store.find_session_by_metadata.return_value = (
        "sess_from_jsonl"
    )

    fake_config = MagicMock()
    fake_config.metadata = {
        "agent_id": "a1234567890abcdef",
        "agent_type": "explore",
        "description": "rehydrated",
    }
    fake_config.created_at = "2024-01-01T00:00:00"
    fake_config.workspace_root = Path("/tmp")
    fake_config.system_prompt = None
    fake_config.skills = None
    fake_config.tool_allowlist = None

    fake_load_result = MagicMock()
    fake_load_result.config = fake_config
    fake_load_result.messages = []

    runtime._session_manager.load.return_value = fake_load_result
    runtime._session_manager.store.resolve_path.return_value = Path(
        "/tmp/sess_from_jsonl.jsonl"
    )

    # Need wiring with registry for the resume path
    registry = BackgroundTaskRegistry()
    wiring = MagicMock()
    wiring.registry = registry
    wiring.subagent_runner = _FakeRunner()
    tool.bind_wiring(wiring)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "agent_id": "a1234567890abcdef",
                "prompt": "resume please",
                "load_skills": [],
                "description": "rehydrated",
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        assert result["agent_id"] == "a1234567890abcdef"


# ------------------------------------------------------------------
# Not found
# ------------------------------------------------------------------


def test_continuation_not_found_raises_tool_error() -> None:
    tool = _make_tool()
    # Registry empty, JSONL returns None
    tool._runtime._session_manager.store.find_session_by_metadata.return_value = None

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "agent_id": "a999999999999999",
                    "prompt": "resume",
                    "load_skills": [],
                    "description": "missing",
                },
                ctx,
            )
        assert "agent_not_found" in str(exc_info.value.details)


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def test_missing_description_raises() -> None:
    tool = _make_tool(with_wiring=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError):
            tool.run(
                {
                    "prompt": "do something",
                    "subagent_type": "explore",
                    "load_skills": [],
                },
                ctx,
            )


def test_missing_prompt_raises() -> None:
    tool = _make_tool(with_wiring=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError):
            tool.run(
                {
                    "description": "test",
                    "subagent_type": "explore",
                    "load_skills": [],
                },
                ctx,
            )


def test_mutually_exclusive_category_and_subagent_type() -> None:
    tool = _make_tool(with_wiring=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError):
            tool.run(
                {
                    "description": "test",
                    "prompt": "do",
                    "category": "coding",
                    "subagent_type": "explore",
                    "load_skills": [],
                },
                ctx,
            )


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


def test_serialize_async_launched() -> None:
    tool = _make_tool(with_wiring=False)
    text = tool.serialize_result(
        {
            "status": "async_launched",
            "agent_id": "a123",
            "description": "desc",
            "output_file": "/tmp/out",
        }
    )
    assert "Background agent launched" in text
    assert "a123" in text
    assert "output_file" in text


def test_serialize_message_queued() -> None:
    tool = _make_tool(with_wiring=False)
    text = tool.serialize_result(
        {
            "status": "message_queued",
            "agent_id": "a123",
            "description": "desc",
            "output_file": "/tmp/out",
        }
    )
    assert "Message queued for agent" in text


def test_serialize_completed() -> None:
    tool = _make_tool(with_wiring=False)
    text = tool.serialize_result(
        {
            "status": "completed",
            "content": "result text",
            "agent_id": "a123",
        }
    )
    assert "result text" in text
