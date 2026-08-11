"""Controlled LLM driver and fixtures for self-evolution integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage, LLMToolCall
from agent.sdk import PermissionDecision

FOREGROUND_REPLY = "Foreground answer"
SEED_REPLY = "Seed answer"
MEMORY_SENTINEL = "User prefers verified reference behavior. [Source: test turn]"
RAW_REVIEW_REPLY = "Saved: user prefers verified reference behavior."
SKILL_NAME = "reference-verification"
SKILL_CONTENT = """---
name: reference-verification
description: Verify reference behavior before implementing an imitation.
---

# Reference verification

Inspect the reference behavior before implementation.
"""


async def allow_all(
    _tool_name: str, _tool_input: dict[str, Any], _context: Any
) -> PermissionDecision:
    """Allow integration-test tool calls without changing production policy."""

    return PermissionDecision(behavior="allow")


class SelfEvolutionLLM:
    """Drive foreground turns followed by one structural two-round review fork."""

    def __init__(
        self,
        *,
        foreground_replies: tuple[str, ...],
        review_tool_call: LLMToolCall,
        review_gate: asyncio.Event | None = None,
    ) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self.agent_requests: list[LLMGenerateRequest] = []
        self._foreground_replies = foreground_replies
        self._review_tool_call = review_tool_call
        self._review_gate = review_gate

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        """Return the next controlled response from request state and message roles."""

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
                if self._review_gate is not None:
                    await self._review_gate.wait()
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
            yield LLMMessage(role="assistant", content=RAW_REVIEW_REPLY)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


async def wait_for_terminal(kernel: Any, run_id: str) -> None:
    """Wait until one public Kernel run reaches a terminal status."""

    while True:
        run = kernel.get_run(run_id)
        if run is not None and run.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0)
