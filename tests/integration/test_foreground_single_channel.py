"""Real-Kernel coverage for foreground and background bash result channels."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall

from .test_bash_engine import _build, _run_turn_and_collect


class _RecordingBashThenStopLLM:
    """Record model inputs while issuing one bash call."""

    def __init__(
        self, *, command: str, timeout: float | None, run_in_background: bool = False
    ) -> None:
        self._command = command
        self._timeout = timeout
        self._run_in_background = run_in_background
        self._calls = 0
        self.seen_message_texts: list[str] = []

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        for message in request.messages:
            if getattr(message, "role", None) == "system":
                continue
            content = getattr(message, "content", "")
            if isinstance(content, str):
                self.seen_message_texts.append(content)
        self._calls += 1
        return self._stream(self._calls == 1)

    async def _stream(self, first: bool):
        if first:
            args: dict[str, Any] = {"command": self._command}
            if self._timeout is not None:
                args["timeout"] = self._timeout
            if self._run_in_background:
                args["run_in_background"] = True
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id="call_1", name="bash", arguments=args),
                ),
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant", content="", finish_reason="tool_calls", usage=None
            )
        else:
            yield LLMMessage(role="assistant", content="done", finish_reason=None)
            yield LLMMessage(
                role="assistant", content="", finish_reason="stop", usage=None
            )


def _seen_any_task_notification(llm: _RecordingBashThenStopLLM) -> bool:
    return any(
        "<task-notification>" in text and "<task-id>" in text
        for text in llm.seen_message_texts
    )


@pytest.mark.asyncio
async def test_foreground_bash_timeout_emits_no_task_notification_through_build_kernel(
    tmp_path: Path,
) -> None:
    """Return a foreground timeout only through its tool result."""
    llm = _RecordingBashThenStopLLM(command="sleep 30", timeout=0.5)
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a command that times out"
        )
    finally:
        kernel.close()

    bash_end = next(
        (e for e in events if e.get("event") == "tool_end" and e.get("name") == "bash"),
        None,
    )
    assert bash_end is not None, (
        f"no bash tool_end event; events: {[e.get('event') for e in events]}"
    )
    assert bash_end.get("reason_code") == "tool_timeout", (
        f"foreground timeout did not surface via the tool result: {bash_end!r}"
    )
    assert not _seen_any_task_notification(llm), (
        "a <task-notification> was injected for a FOREGROUND bash timeout — the "
        "dual-channel bug is back (foreground must be single-channel)"
    )
    assert not any("<task-notification>" in str(e.get("text", "")) for e in events), (
        "a <task-notification> surfaced on the stream for a foreground bash timeout"
    )


@pytest.mark.asyncio
async def test_run_in_background_command_still_emits_task_notification(
    tmp_path: Path,
) -> None:
    """Deliver a background command result to the initiating session."""
    llm = _RecordingBashThenStopLLM(
        command="echo hi", timeout=None, run_in_background=True
    )
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a background command"
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        while loop.time() < deadline:
            if _seen_any_task_notification(llm):
                break
            await asyncio.sleep(0.1)
    finally:
        kernel.close()

    assert _seen_any_task_notification(llm), (
        "run_in_background command completed but no <task-notification> was delivered "
        "— the background notification path regressed"
    )
