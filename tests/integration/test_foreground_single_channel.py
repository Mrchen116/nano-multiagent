"""bugfix-417-M7 (decision 12): foreground bash single-channel DONE hard gate.

round-6 acceptance proved (proxy log) that a foreground bash timeout produced BOTH a
tool_result AND a <task-notification> — the dual-channel bug. M7 removes foreground
bash from BackgroundTaskRegistry entirely, so the notification channel is physically
unreachable for foreground commands. These two guards replace "trust the human live
re-test" with an automated regression driven through a real build_kernel:
  1. a foreground bash that times out → exactly one channel (tool result with the
     timeout reason), and NO <task-notification> is ever injected into the session;
  2. a run_in_background command → still gets its <task-notification> (the real
     background path must not regress).

Observability: the fake LLM records every (non-system) request message text. An actual
injected <task-notification> is a user-role message carrying a <task-id> tag — the
system prompt's prose mention of the mechanism is excluded. Asserting absence/presence
of such a message across all captured requests is the cross-layer observable.

Shares the build_kernel harness (_build / _run_turn_and_collect / _llm_config /
_allow_all) with test_bash_engine — split out only to keep each test
file under the 400-line cap (docs/TESTING_GUIDE.md §7). Not an e2e-marked test — a fake
LLM client issues the bash tool_call, so no external services are needed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall

from .test_bash_engine import _build, _run_turn_and_collect


class _RecordingBashThenStopLLM:
    """Like _BashThenStopLLM but records the text of every message it is asked to
    generate against, so a test can assert whether a <task-notification> was ever
    injected into the session input."""

    def __init__(
        self, *, command: str, timeout: float | None, run_in_background: bool = False
    ) -> None:
        self._command = command
        self._timeout = timeout
        self._run_in_background = run_in_background
        self._calls = 0
        # Texts of non-system messages only (the system prompt documents the
        # <task-notification> mechanism in prose, so it must be excluded — only an
        # ACTUAL injected notification, a user-role message carrying a <task-id>,
        # counts as "the notification channel fired").
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
            # Any subsequent turn (including one woken by a <task-notification>
            # submit) just stops — but its request messages were already recorded.
            yield LLMMessage(role="assistant", content="done", finish_reason=None)
            yield LLMMessage(
                role="assistant", content="", finish_reason="stop", usage=None
            )


def _seen_any_task_notification(llm: _RecordingBashThenStopLLM) -> bool:
    # An actual injected notification carries both the wrapper and a <task-id> tag
    # (build_task_notification_xml). The system prompt's prose mention of
    # "<task-notification>" is excluded both here (needs <task-id>) and at capture
    # (system-role messages are skipped).
    return any(
        "<task-notification>" in text and "<task-id>" in text
        for text in llm.seen_message_texts
    )


@pytest.mark.asyncio
async def test_foreground_bash_timeout_emits_no_task_notification_through_build_kernel(
    tmp_path: Path,
) -> None:
    """A foreground bash command that hits its own timeout must surface its result
    ONLY via the tool result (reason=tool_timeout) — never an additional
    <task-notification>. This is the M7 dual-channel negative invariant, proven
    end-to-end through build_kernel (foreground bash never enters BackgroundTaskRegistry,
    so the notification path is structurally unreachable)."""
    llm = _RecordingBashThenStopLLM(command="sleep 30", timeout=0.5)
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a command that times out"
        )
        # Give any (erroneous) async notification delivery a chance to land before we
        # assert its absence — a false negative would otherwise be a flaky pass.
        await asyncio.sleep(0.5)
    finally:
        kernel.close()

    # Channel 1 (tool result) fired with the timeout reason.
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
    # Channel 2 (notification) must NOT have fired — neither in the stream nor injected
    # into any subsequent LLM request.
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
    """A run_in_background bash command must still deliver its <task-notification>
    when it completes — the real background path must not regress under M7."""
    llm = _RecordingBashThenStopLLM(
        command="echo hi", timeout=None, run_in_background=True
    )
    kernel = _build(tmp_path, llm)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a background command"
        )
        # The background task completes async; its notification is delivered by
        # submitting (or injecting) into the parent session, which drives another
        # generate() call. Poll the recorded requests for the notification.
        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            if _seen_any_task_notification(llm):
                break
            await asyncio.sleep(0.1)
    finally:
        kernel.close()

    # The background completion delivered a <task-notification> into the session —
    # the real background notification path is intact under M7.
    assert _seen_any_task_notification(llm), (
        "run_in_background command completed but no <task-notification> was delivered "
        "— the real background notification path regressed under M7"
    )
