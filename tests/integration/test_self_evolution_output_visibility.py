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
_REVIEW_PROMPT_MARKER = "Review the conversation above and consider saving to memory"


async def _allow_all(
    _tool_name: str, _tool_input: dict[str, Any], _context: Any
) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


class _SelfEvolutionLLM:
    """Drive one foreground response and one two-round memory review fork."""

    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._foreground_calls = 0

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        transcript = "\n".join(str(message.content) for message in request.messages)

        async def _stream() -> AsyncIterator[LLMMessage]:
            if _REVIEW_PROMPT_MARKER not in transcript:
                self._foreground_calls += 1
                content = (
                    _SEED_REPLY if self._foreground_calls == 1 else _FOREGROUND_REPLY
                )
                yield LLMMessage(role="assistant", content=content)
                yield LLMMessage(role="assistant", content="", finish_reason="stop")
                return

            if "added entry to 'user'" not in transcript:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="memory-call",
                            name="memory",
                            arguments={
                                "action": "add",
                                "target": "user",
                                "content": _MEMORY_SENTINEL,
                            },
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
                return

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

    client = _SelfEvolutionLLM()
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

        review_events = [
            event for event in events if event.get("event") == "self_evolution_review"
        ]
        assert len(review_events) == 1
        assert review_events[0]["reviewed_memory"] is True
        assert review_events[0]["reviewed_skills"] is False
        assert review_events[0]["tool_names_called"] == ["memory"]
        assert review_events[0]["completed"] is True

        user_memory = tmp_path / ".nanoassistant" / "memory" / "USER.md"
        assert _MEMORY_SENTINEL in user_memory.read_text(encoding="utf-8")
        assert len(client.requests) == 4
        assert {request.model for request in client.requests} == {"test-model"}
        assert kernel.get_run(run.run_id) is not None
    finally:
        await kernel.aclose()
