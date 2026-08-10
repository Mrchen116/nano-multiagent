"""Integration coverage for self-evolution side-chain delivery isolation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, PermissionDecision, build_kernel

_FOREGROUND_REPLY = "Foreground answer"
_SEED_REPLY = "Seed answer"
_MEMORY_SENTINEL = "User prefers verified reference behavior. [Source: test turn]"
_RAW_REVIEW_REPLY = "Saved: user prefers verified reference behavior."
_SKILL_NAME = "reference-verification"
_SKILL_CONTENT = """---
name: reference-verification
description: Verify reference behavior before implementing an imitation.
---

# Reference verification

Inspect the reference behavior before implementation.
"""


async def _allow_all(
    _tool_name: str, _tool_input: dict[str, Any], _context: Any
) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


class _SelfEvolutionLLM:
    """Drive foreground turns followed by one two-round self-evolution fork."""

    def __init__(
        self,
        *,
        foreground_replies: tuple[str, ...],
        review_tool_call: LLMToolCall,
    ) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self.agent_requests: list[LLMGenerateRequest] = []
        self._foreground_replies = foreground_replies
        self._review_tool_call = review_tool_call

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        if request.tools == ():

            async def _classify() -> AsyncIterator[LLMMessage]:
                yield LLMMessage(role="assistant", content="<block>no</block>")
                yield LLMMessage(role="assistant", content="", finish_reason="stop")

            return _classify()

        request_index = len(self.agent_requests)
        self.agent_requests.append(request)

        async def _stream() -> AsyncIterator[LLMMessage]:
            if request_index < len(self._foreground_replies):
                yield LLMMessage(
                    role="assistant",
                    content=self._foreground_replies[request_index],
                )
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return

            if request_index == len(self._foreground_replies):
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(self._review_tool_call,),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return

            if request_index != len(self._foreground_replies) + 1:
                raise AssertionError(f"unexpected LLM request index {request_index}")
            assert any(
                message.role == "assistant"
                and any(
                    tool_call.call_id == self._review_tool_call.call_id
                    and tool_call.name == self._review_tool_call.name
                    for tool_call in message.tool_calls
                )
                for message in request.messages
            )
            assert any(
                message.role == "tool"
                and message.tool_call_id == self._review_tool_call.call_id
                for message in request.messages
            )
            yield LLMMessage(role="assistant", content=_RAW_REVIEW_REPLY)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


async def _collect_through_review(
    kernel: Any, session_id: str, *, after_sequence: int
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for event in kernel.stream(session_id, after_sequence=after_sequence):
        events.append(event)
        if event.get("event") == "self_evolution_review":
            return events
    raise AssertionError("session stream closed before self_evolution_review")


async def _wait_for_terminal(kernel: Any, run_id: str) -> None:
    while True:
        run = kernel.get_run(run_id)
        if run is not None and run.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_self_evolution_raw_output_stays_out_of_parent_session_events(
    tmp_path: Path,
) -> None:
    """A real memory review fork exposes only its structured review notice."""

    client = _SelfEvolutionLLM(
        foreground_replies=(_SEED_REPLY, _FOREGROUND_REPLY),
        review_tool_call=LLMToolCall(
            call_id="memory-call",
            name="memory",
            arguments={
                "action": "add",
                "target": "user",
                "content": _MEMORY_SENTINEL,
            },
        ),
    )
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["memory"],
            features={},
            metadata={
                "self_evolution": {
                    "enabled": True,
                    "skill_creation": False,
                    "memory_curation": True,
                    "skill_nudge_interval": 100,
                    "memory_nudge_interval": 1,
                }
            },
        )
        seed_run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Seed the conversation."}],
        )
        await asyncio.wait_for(_wait_for_terminal(kernel, seed_run.run_id), timeout=2)
        stream_anchor = kernel.current_event_sequence()

        run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Please remember my preference."}],
        )

        events = await asyncio.wait_for(
            _collect_through_review(
                kernel, session.session_id, after_sequence=stream_anchor
            ),
            timeout=5,
        )

        foreground_events = [
            event
            for event in events
            if event.get("event") == "assistant_message"
            and event.get("content") == _FOREGROUND_REPLY
        ]
        assert len(foreground_events) == 1
        assistant_contents = [
            event.get("content")
            for event in events
            if event.get("event") == "assistant_message" and event.get("content")
        ]
        assert assistant_contents == [_FOREGROUND_REPLY]
        review_tool_events = [
            event
            for event in events
            if event.get("event") in {"tool_start", "tool_end"}
            and event.get("name") == "memory"
        ]
        assert review_tool_events == []
        turn_end_events = [
            event
            for event in events
            if event.get("event") == "turn_end" and event.get("run_id") == run.run_id
        ]
        assert len(turn_end_events) == 1

        review_event = events[-1]
        assert review_event["event"] == "self_evolution_review"
        assert review_event["reviewed_memory"] is True
        assert review_event["reviewed_skills"] is False
        assert review_event["tool_names_called"] == ["memory"]
        assert review_event["completed"] is True

        user_memory = tmp_path / ".nanoassistant" / "memory" / "USER.md"
        assert _MEMORY_SENTINEL in user_memory.read_text(encoding="utf-8")
        assert len(client.agent_requests) == 4
        assert {request.model for request in client.requests} == {"test-model"}
        assert kernel.get_run(run.run_id) is not None
    finally:
        await kernel.aclose()


@pytest.mark.asyncio
async def test_self_evolution_skill_create_keeps_only_business_event_visible(
    tmp_path: Path,
) -> None:
    """A real skill review keeps activation sync while hiding raw fork output."""

    client = _SelfEvolutionLLM(
        foreground_replies=(_FOREGROUND_REPLY,),
        review_tool_call=LLMToolCall(
            call_id="skill-create-call",
            name="skill_manage",
            arguments={
                "action": "create",
                "name": _SKILL_NAME,
                "scope": "agent",
                "content": _SKILL_CONTENT,
            },
        ),
    )
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["skill_manage"],
            features={},
            metadata={
                "self_evolution": {
                    "enabled": True,
                    "skill_creation": True,
                    "memory_curation": False,
                    "skill_nudge_interval": 1,
                    "memory_nudge_interval": 100,
                }
            },
        )
        stream_anchor = kernel.current_event_sequence()
        run = kernel.submit(
            session_id=session.session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Solve one complex task."}],
        )

        events = await asyncio.wait_for(
            _collect_through_review(
                kernel, session.session_id, after_sequence=stream_anchor
            ),
            timeout=5,
        )

        assistant_contents = [
            event.get("content")
            for event in events
            if event.get("event") == "assistant_message" and event.get("content")
        ]
        assert assistant_contents == [_FOREGROUND_REPLY]
        assert not any(
            event.get("event") in {"tool_start", "tool_end"}
            and event.get("name") == "skill_manage"
            for event in events
        )
        assert (
            len(
                [
                    event
                    for event in events
                    if event.get("event") == "turn_end"
                    and event.get("run_id") == run.run_id
                ]
            )
            == 1
        )

        skill_created_events = [
            event for event in events if event.get("event") == "skill_created"
        ]
        assert len(skill_created_events) == 1
        assert skill_created_events[0]["name"] == _SKILL_NAME
        assert skill_created_events[0]["scope"] == "agent"
        assert skill_created_events[0]["run_id"] == run.run_id
        assert skill_created_events[0]["source"] == "self_evolution"

        review_event = events[-1]
        assert review_event["event"] == "self_evolution_review"
        assert review_event["reviewed_memory"] is False
        assert review_event["reviewed_skills"] is True
        assert review_event["tool_names_called"] == ["skill_manage"]
        assert review_event["completed"] is True

        skill_path = tmp_path / ".nanoassistant" / "skills" / _SKILL_NAME / "SKILL.md"
        assert skill_path.read_text(encoding="utf-8") == _SKILL_CONTENT
        assert len(client.agent_requests) == 3
        assert len(client.requests) == 4
        assert {request.model for request in client.requests} == {"test-model"}
    finally:
        await kernel.aclose()
