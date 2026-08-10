"""Integration coverage for self-evolution side-chain delivery isolation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMToolCall
from agent.sdk import LLMConfig, build_kernel
from tests.helpers.self_evolution import (
    FOREGROUND_REPLY as _FOREGROUND_REPLY,
    MEMORY_SENTINEL as _MEMORY_SENTINEL,
    SEED_REPLY as _SEED_REPLY,
    SKILL_CONTENT as _SKILL_CONTENT,
    SKILL_NAME as _SKILL_NAME,
    SelfEvolutionLLM as _SelfEvolutionLLM,
    allow_all as _allow_all,
    wait_for_terminal as _wait_for_terminal,
)


async def _collect_through_review(
    kernel: Any, session_id: str, *, after_sequence: int
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for event in kernel.stream(session_id, after_sequence=after_sequence):
        events.append(event)
        if event.get("event") == "self_evolution_review":
            return events
    raise AssertionError("session stream closed before self_evolution_review")


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
