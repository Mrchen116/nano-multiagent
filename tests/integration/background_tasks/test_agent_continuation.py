"""Integration tests for agent continuation: message queue and JSONL rehydrate."""

from __future__ import annotations

import time
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.errors import ToolError
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.types import Message, TurnResult
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

from ._runtime_stub import _RuntimeStubBase, _make_ctx

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _RuntimeStub(_RuntimeStubBase):
    async def run(
        self,
        session_id: str,
        parts: Any,
        *,
        stream: bool = False,
        controller: Any = None,
        parent_session_id: str | None = None,
        workspace_root: Any = None,
        run_id: str | None = None,
        llm_session_id: str | None = None,
        model: str | None = None,
    ) -> TurnResult:
        import time as _time

        if self._delay > 0:
            _time.sleep(self._delay)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_1",
            messages=(
                Message(message_id="msg_1", role="assistant", content="subagent done"),
            ),
            completed=True,
            stop_reason="completed",
        )


class _GatedFollowUpLLM:
    """Controlled LLM that proves AgentLoop sends a second request with follow-up."""

    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self.first_request_started = threading.Event()
        self.release_first_request = threading.Event()

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        return self._generate(request)

    async def _generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        import asyncio

        self.requests.append(request)
        if len(self.requests) == 1:
            self.first_request_started.set()
            while not self.release_first_request.is_set():
                await asyncio.sleep(0.01)
            yield LLMMessage(role="assistant", content="round one complete")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return

        user_messages = [
            message.content for message in request.messages if message.role == "user"
        ]
        marker = "Also check the tests."
        if marker not in user_messages:
            raise AssertionError(
                f"follow-up missing from second LLM request: {user_messages!r}"
            )
        yield LLMMessage(
            role="assistant",
            content="VISIBLE FOLLOWUP RECEIVED: Also check the tests.",
        )
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def test_running_agent_follow_up_enters_live_runtime_controller(
    tmp_path: Path,
) -> None:
    """Running follow-up reaches the original subagent's next real LLM request."""
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    parent_session = service.create_session(workspace_root=tmp_path)
    llm = _GatedFollowUpLLM()
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
    )
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id=parent_session.session_id)

    # Launch background agent.
    result = tool.run(
        {
            "description": "long task",
            "prompt": "Take your time.",
            "subagent_type": "oracle",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]
    assert llm.first_request_started.wait(timeout=2), "subagent LLM did not start"

    # Send follow-up while still running.
    follow_up = tool.run(
        {
            "agent_id": agent_id,
            "prompt": "Also check the tests.",
        },
        ctx,
    )

    assert follow_up["status"] == "message_queued"
    assert follow_up["agent_id"] == agent_id
    llm.release_first_request.set()

    for _ in range(50):
        record = wiring.registry.get(agent_id)
        if record is not None and record.status == BackgroundTaskStatus.COMPLETED:
            break
        time.sleep(0.05)

    record = wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.COMPLETED
    assert record.result_text == "VISIBLE FOLLOWUP RECEIVED: Also check the tests."
    assert len(llm.requests) == 2, "follow-up must continue the same run, not a new run"
    second_user_messages = [
        message.content
        for message in llm.requests[1].messages
        if message.role == "user"
    ]
    assert second_user_messages == ["Take your time.", "Also check the tests."]


def test_jsonl_rehydrate_continues_agent_after_registry_loss(tmp_path: Path) -> None:
    """After kernel restart (registry lost), Agent(agent_id=...) rehydrates from session store."""
    runtime = _RuntimeStub(tmp_path, delay=0.1)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    # Launch background agent and let it complete.
    result = tool.run(
        {
            "description": "research",
            "prompt": "Study loop.",
            "subagent_type": "explore",
            "load_skills": [],
            "run_in_background": True,
        },
        ctx,
    )
    agent_id = result["agent_id"]

    for _ in range(50):
        record = wiring.registry.get(agent_id)
        if record is not None and record.status.value in (
            "completed",
            "failed",
            "killed",
        ):
            break
        time.sleep(0.05)

    # Simulate kernel restart: create fresh registry but keep runtime (and its store).
    new_wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    new_tool = AgentTool(runtime=runtime, wiring=new_wiring)

    # Continue the agent — should rehydrate from JSONL (session store).
    resume_result = new_tool.run(
        {
            "agent_id": agent_id,
            "prompt": "Now focus on bash.",
        },
        ctx,
    )

    assert resume_result["status"] == "async_launched"
    assert resume_result["agent_id"] == agent_id

    # Fresh registry should now have the running record.
    record = new_wiring.registry.get(agent_id)
    assert record is not None
    assert record.status == BackgroundTaskStatus.RUNNING


def test_continuation_on_unknown_agent_id_raises_not_found(tmp_path: Path) -> None:
    """Agent(agent_id=unknown) with no store match returns ToolError."""
    runtime = _RuntimeStub(tmp_path)
    wiring = wire_background_tasks(workspace_root=tmp_path, runtime=runtime)
    tool = AgentTool(runtime=runtime, wiring=wiring)
    ctx = _make_ctx(tmp_path, session_id="sess_parent")

    with pytest.raises(ToolError, match="No subagent with agent_id"):
        tool.run(
            {
                "agent_id": "a000000000000000",
                "prompt": "Continue.",
            },
            ctx,
        )
