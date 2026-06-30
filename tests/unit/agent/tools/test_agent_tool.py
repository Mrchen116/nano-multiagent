"""Tests for AgentTool background/foreground/continuation paths."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, get_type_hints
from unittest.mock import MagicMock, patch

import pytest

from agent.core.agent.run_control import RunController
from agent.core.background_tasks.interfaces import (
    BackgroundSubagentHandle,
    BackgroundSubagentRunner,
)
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


class _FakeSubagentHandle:
    def stop(self) -> None:
        pass

    def send_message(self, prompt: str) -> bool:
        del prompt
        return True


class _FakeMessageHandle:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, prompt: str) -> bool:
        self.messages.append(prompt)
        return True


class _FakeRunner:
    def __init__(self) -> None:
        self.submit_foreground_calls = 0
        self.start_calls: list[dict] = []

    def start(
        self,
        *,
        agent_session_id,
        parent_session_id,
        prompt,
        on_complete,
        on_fail,
        on_kill,
        workspace_root=None,
        llm_session_id=None,
        model=None,
    ):
        self.start_calls.append(
            {
                "agent_session_id": agent_session_id,
                "parent_session_id": parent_session_id,
                "llm_session_id": llm_session_id,
                "model": model,
            }
        )

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
        return _FakeSubagentHandle()

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

        self.submit_foreground_calls += 1
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


def test_registry_terminal_transition_disables_live_message_delivery() -> None:
    registry = BackgroundTaskRegistry()
    agent_id = "a1234567890abcdef"
    handle = _FakeMessageHandle()
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
    registry.set_message_handle(agent_id, handle)

    assert registry.send_agent_message(agent_id, "before terminal") is True

    registry.complete(agent_id, result_text="done")

    assert registry.send_agent_message(agent_id, "after terminal") is False
    assert handle.messages == ["before terminal"]


def test_subagent_runner_start_returns_stop_and_message_handle_contract() -> None:
    hints = get_type_hints(BackgroundSubagentRunner.start)

    assert hints["return"] is BackgroundSubagentHandle


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


def test_create_subagent_session_routes_through_dedicated_loop() -> None:
    """bugfix-418 round1: subagent session creation routes through the runner's
    submit_foreground (kernel's dedicated loop) by a DIRECT call — no capability
    probe, no bare-asyncio.run fallback — same as the turn-execution path
    (decision 1). Foreground dispatch therefore submits twice: once to create the
    session, once for the turn.
    """
    tool = _make_tool(with_wiring=True)
    tool._runtime.run = _fake_run_fast
    runner = tool._wiring.subagent_runner

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
        # create_session (1) + turn (1) both go through the dedicated loop.
        assert runner.submit_foreground_calls == 2, (
            "subagent session creation must route through submit_foreground "
            "(dedicated loop), not bare asyncio.run on a transient loop"
        )


def test_create_subagent_session_fails_loud_without_runner() -> None:
    """bugfix-418 round1: with no real subagent runner, creation must fail loud
    (the runner's submit_foreground raises) rather than silently fall back to
    bare asyncio.run — which would re-open the cross-loop back door.
    """
    from agent.platform.background_tasks.wiring import wire_background_tasks

    runtime = MagicMock()
    runtime.create_session = _fake_create_session
    # No runtime passed → wiring builds a _NoOpSubagentRunner whose
    # submit_foreground raises.
    with tempfile.TemporaryDirectory() as tmpdir:
        wiring = wire_background_tasks(workspace_root=Path(tmpdir), runtime=None)
        tool = AgentTool(runtime=runtime, wiring=wiring)
        ctx = _make_ctx(tmpdir)
        # Creation happens before the turn's try/except, so the runner's
        # RuntimeError propagates loudly (surfaced as a tool error) instead of a
        # silent asyncio.run success that would re-open the cross-loop path.
        with pytest.raises(RuntimeError, match="not configured"):
            tool.run(
                {
                    "description": "test task",
                    "prompt": "do something",
                    "subagent_type": "explore",
                    "load_skills": [],
                    "run_in_background": False,
                },
                ctx,
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


def test_foreground_auto_background_watcher_completes_registry() -> None:
    """bugfix-418 round1 W1: cover the timeout→auto-background NOTIFICATION window.

    The prior test only asserted status=async_launched at hand-off time; the
    design risk section promises that once the (now background) subagent's future
    completes, the watcher drives registry.complete — the terminal transition the
    notifying store wraps to deliver a <task-notification>. This asserts the
    watcher actually closes that loop: the registry record reaches `completed`
    carrying the subagent's result text.
    """
    tool = _make_tool()
    registry = tool._wiring.registry

    # runtime.run resolves shortly AFTER the foreground budget elapses, so the
    # call hands off to background and the watcher later observes completion.
    late_result = _FakeTurnResult("late subagent result")

    async def _late_run(*args, **kwargs):
        time.sleep(0.3)
        return late_result

    tool._runtime.run = _late_run

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
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
        agent_id = result["agent_id"]

        # Poll for the watcher to observe the future and call registry.complete.
        for _ in range(50):
            record = registry.get(agent_id)
            if record is not None and record.status == BackgroundTaskStatus.COMPLETED:
                break
            time.sleep(0.05)

        record = registry.get(agent_id)
        assert record is not None
        assert record.status == BackgroundTaskStatus.COMPLETED, (
            "auto-background watcher must call registry.complete on future "
            "completion (the terminal transition that delivers the notification)"
        )
        assert record.result_text == "late subagent result"


def test_foreground_auto_background_running_follow_up_uses_live_controller() -> None:
    tool = _make_tool()
    registry = tool._wiring.registry
    consumed: list[str] = []

    async def _pending_run(*args, **kwargs):
        import asyncio

        controller = kwargs["controller"]
        follow_up = None
        for _ in range(100):
            pending = controller.drain_pending()
            if pending:
                follow_up = pending[0].message.content
                break
            await asyncio.sleep(0.01)
        if follow_up is None:
            follow_up = "missing follow-up"
        consumed.append(follow_up)
        return _FakeTurnResult(f"auto consumed {follow_up}")

    tool._runtime.run = _pending_run

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = tool.run(
            {
                "description": "slow task",
                "prompt": "do something slow",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
                "timeout_seconds": 0.01,
            },
            ctx,
        )
        assert result["status"] == "async_launched"
        agent_id = result["agent_id"]

        follow_up = tool.run(
            {
                "agent_id": agent_id,
                "prompt": "auto follow up",
                "load_skills": [],
                "description": "slow task",
            },
            ctx,
        )
        assert follow_up["status"] == "message_queued"

        for _ in range(50):
            record = registry.get(agent_id)
            if record is not None and record.status == BackgroundTaskStatus.COMPLETED:
                break
            time.sleep(0.05)

        record = registry.get(agent_id)
        assert record is not None
        assert record.status == BackgroundTaskStatus.COMPLETED
        assert record.result_text == "auto consumed auto follow up"
        assert consumed == ["auto follow up"]


def test_auto_background_stopped_agent_rejects_follow_up_without_false_queued() -> None:
    from agent.platform.tools.builtins.agent import _ControllerHandle

    tool = _make_tool()
    registry = tool._wiring.registry
    agent_id = "a1234567890abcdef"
    controller = RunController()
    handle = _ControllerHandle(controller)
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
    assert registry.set_message_handle(agent_id, handle) is True
    handle.stop()

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "agent_id": agent_id,
                    "prompt": "follow up after stop",
                    "load_skills": [],
                    "description": "existing",
                },
                ctx,
            )

    assert exc_info.value.details["code"] == "agent_message_not_deliverable"


# ------------------------------------------------------------------
# Continuation: running agent
# ------------------------------------------------------------------


def test_explicit_background_stopped_agent_rejects_follow_up_without_false_queued() -> None:
    from agent.platform.background_tasks.runtime_runner import _ControllerHandle

    tool = _make_tool()
    registry = tool._wiring.registry
    agent_id = "a1234567890abcdef"
    controller = RunController()
    handle = _ControllerHandle(controller)
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
    assert registry.set_message_handle(agent_id, handle) is True
    handle.stop()

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "agent_id": agent_id,
                    "prompt": "follow up after stop",
                    "load_skills": [],
                    "description": "existing",
                },
                ctx,
            )

    assert exc_info.value.details["code"] == "agent_message_not_deliverable"


def test_continuation_to_running_agent_without_live_delivery_fails() -> None:
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
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "agent_id": agent_id,
                    "prompt": "follow up",
                    "load_skills": [],
                    "description": "existing",
                },
                ctx,
            )
        assert exc_info.value.details["code"] == "agent_message_not_deliverable"


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


# ------------------------------------------------------------------
# bugfix-422 (#129): subagent LLM requests group under parent session
# ------------------------------------------------------------------


def test_background_launch_passes_parent_as_llm_session_id() -> None:
    """Background subagent must reuse the parent session id at the LLM layer so
    its provider calls group under the parent in the LLM proxy session-inspector,
    while keeping its own agent_session_id for JSONL storage."""
    tool = _make_tool()
    runner = tool._wiring.subagent_runner
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)  # session_id="parent_1"
        tool.run(
            {
                "description": "test task",
                "prompt": "do something",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": True,
            },
            ctx,
        )
        assert len(runner.start_calls) == 1
        call = runner.start_calls[0]
        assert call["llm_session_id"] == "parent_1"
        # local session id stays independent
        assert call["agent_session_id"] != "parent_1"


def test_resume_passes_parent_as_llm_session_id() -> None:
    """Resuming a terminal subagent must also thread llm_session_id=parent."""
    tool = _make_tool()
    registry = tool._wiring.registry
    runner = tool._wiring.subagent_runner

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
        assert len(runner.start_calls) == 1
        call = runner.start_calls[0]
        assert call["llm_session_id"] == "parent_1"
        assert call["agent_session_id"] == "sess_terminal"


def test_foreground_passes_parent_as_llm_session_id() -> None:
    """Foreground subagent goes through submit_foreground(runtime.run(...)); the
    runtime.run call must carry llm_session_id=parent."""
    tool = _make_tool(with_wiring=True)

    captured: dict = {}

    async def _spy_run(session_id, parts, **kwargs):
        captured["session_id"] = session_id
        captured["llm_session_id"] = kwargs.get("llm_session_id")
        return _FakeTurnResult("sync result")

    tool._runtime.run = _spy_run

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)  # session_id="parent_1"
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
        assert captured["llm_session_id"] == "parent_1"
        # the runtime.run target session is the subagent's own session
        assert captured["session_id"] != "parent_1"


# ------------------------------------------------------------------
# bugfix-443: subagent inherits the parent run's model (root cause A)
# ------------------------------------------------------------------


def test_background_launch_inherits_parent_run_model() -> None:
    """bugfix-443: a background subagent dispatched from a run started with
    model=M must thread that model into runner.start so its whole side-chain
    follows the parent model instead of the global default."""
    tool = _make_tool()
    tool._runtime.resolve_run_model.return_value = "mimo-model"
    runner = tool._wiring.subagent_runner
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)  # session_id="parent_1"
        tool.run(
            {
                "description": "test task",
                "prompt": "do something",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": True,
            },
            ctx,
        )
        tool._runtime.resolve_run_model.assert_called_with("parent_1")
        assert len(runner.start_calls) == 1
        assert runner.start_calls[0]["model"] == "mimo-model"


def test_resume_inherits_parent_run_model() -> None:
    """bugfix-443: resuming a terminal subagent must also inherit the parent
    run's model (the resume path is a separate dispatch point)."""
    tool = _make_tool()
    tool._runtime.resolve_run_model.return_value = "mimo-model"
    registry = tool._wiring.registry
    runner = tool._wiring.subagent_runner

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
        assert len(runner.start_calls) == 1
        assert runner.start_calls[0]["model"] == "mimo-model"


def test_resume_inherits_current_run_model_across_run_boundary() -> None:
    """bugfix-443 fix1 C4: a resumed subagent must inherit the *current resuming
    run*'s model (ctx.session_id), not the original launcher's
    (record.parent_session_id). The launcher run may already be terminal and
    popped from _active_run_models → resolving from it yields None and the
    subagent would wrongly fall back to the global default."""
    tool = _make_tool()

    def _resolve(session_id):
        # Original launcher run is gone (popped); the active resuming run carries
        # the model.
        return {"current_run": "current-model", "old_launcher": None}.get(session_id)

    tool._runtime.resolve_run_model.side_effect = _resolve
    registry = tool._wiring.registry
    runner = tool._wiring.subagent_runner

    agent_id = "a1234567890abcdef"
    registry.register_subagent(
        task_id=agent_id,
        parent_session_id="old_launcher",
        agent_id=agent_id,
        agent_session_id="sess_terminal",
        description="existing",
        prompt="original",
        agent_type="explore",
        output_file="/tmp/out.jsonl",
    )
    registry.mark_running(agent_id)
    registry.complete(agent_id, result_text="done")

    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        safety = ToolSafety(repo_root=Path(tmpdir), config=ToolSafetyConfig())
        ctx = ToolContext(
            repo_root=Path(tmpdir),
            cwd=Path(tmpdir),
            safety=safety,
            session_id="current_run",
        )
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
        assert len(runner.start_calls) == 1
        # Model resolved from the current resuming run, not the dead launcher.
        assert runner.start_calls[0]["model"] == "current-model"
        # llm_session_id / path grouping still keyed on the original launcher.
        assert runner.start_calls[0]["llm_session_id"] == "old_launcher"


def test_noop_subagent_runner_start_accepts_and_ignores_model() -> None:
    """bugfix-443 fix1 C1: AgentTool now passes model= to runner.start. The
    _NoOpSubagentRunner fallback (built when no AgentRuntime is configured) must
    accept the kwarg and still call on_fail gracefully — otherwise it raises
    TypeError instead of failing the task, stranding it in RUNNING."""
    from agent.platform.background_tasks.wiring import _NoOpSubagentRunner

    runner = _NoOpSubagentRunner()
    failures: list[dict] = []

    stopper = runner.start(
        agent_session_id="s1",
        parent_session_id="p1",
        prompt="go",
        on_complete=lambda **k: None,
        on_fail=lambda **k: failures.append(k),
        on_kill=lambda **k: None,
        model="some-model",
    )

    assert stopper is not None
    assert len(failures) == 1
    assert failures[0]["task_id"] == "s1"


def test_foreground_inherits_parent_run_model() -> None:
    """bugfix-443: the foreground subagent goes through
    submit_foreground(runtime.run(...)); the runtime.run call must carry
    model=<parent run model>."""
    tool = _make_tool(with_wiring=True)
    tool._runtime.resolve_run_model.return_value = "mimo-model"

    captured: dict = {}

    async def _spy_run(session_id, parts, **kwargs):
        captured["model"] = kwargs.get("model")
        return _FakeTurnResult("sync result")

    tool._runtime.run = _spy_run

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)  # session_id="parent_1"
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
        assert captured["model"] == "mimo-model"


# ------------------------------------------------------------------
# load_skills validation (bugfix-431): non-empty skill names
# ------------------------------------------------------------------


def _make_tool_with_skills(available_skill_names: list[str]) -> AgentTool:
    """Build an AgentTool whose runtime.resolve_available_skills returns the given names."""
    from agent.core.skills import SkillMetadata

    runtime = MagicMock()
    runtime.create_session = _fake_create_session
    runtime._session_manager.store.resolve_path.return_value = Path(
        "/tmp/sess_123.jsonl"
    )
    runtime._session_manager.store.find_session_by_metadata.return_value = None

    # Construct minimal SkillMetadata stubs for each known skill name.
    fake_dir = Path("/fake")
    skill_metas = tuple(
        SkillMetadata(
            name=n, description=f"{n} desc", location=fake_dir, base_dir=fake_dir
        )
        for n in available_skill_names
    )

    def _resolve(workspace_root, include_names=None):
        if include_names is None:
            return skill_metas
        return tuple(s for s in skill_metas if s.name in include_names)

    runtime.resolve_available_skills.side_effect = _resolve

    tool = AgentTool(runtime=runtime, wiring=None)
    return tool


def test_load_skills_known_skill_passes_validation() -> None:
    """A known skill name in load_skills must not raise (bugfix-431 校验路径)."""
    tool = _make_tool_with_skills(["summarize", "search_web"])
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        # Should not raise — "summarize" is in the available set.
        # With no wiring the call raises ToolError for missing category/subagent_type,
        # not for skill validation — so we just check that skill validation itself passes.
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "description": "test",
                    "prompt": "do it",
                    "subagent_type": "explore",
                    "load_skills": ["summarize"],
                },
                ctx,
            )
        # Skill validation passed — error is about wiring/runner, not "unknown skills".
        assert "unknown skills" not in str(exc_info.value)


def test_load_skills_unknown_skill_raises_tool_error() -> None:
    """An unknown skill name in load_skills must raise ToolError (bugfix-431 校验路径)."""
    tool = _make_tool_with_skills(["summarize"])
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        with pytest.raises(ToolError) as exc_info:
            tool.run(
                {
                    "description": "test",
                    "prompt": "do it",
                    "subagent_type": "explore",
                    "load_skills": ["no_such_skill"],
                },
                ctx,
            )
        assert "unknown skills" in str(exc_info.value)
        assert "no_such_skill" in str(exc_info.value.details)
