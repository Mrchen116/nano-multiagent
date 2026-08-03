"""Verify production kernel wiring exposes tool liveness and timeout events."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel


def _llm_config() -> LLMConfig:
    return LLMConfig(
        provider="openai_compat",
        model="codex_oauth:gpt-5.5",
        base_url="http://127.0.0.1:4000",
        default_model="codex_oauth:gpt-5.5",
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="codex_oauth:gpt-5.5"),),
            ),
        ),
    )


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    from agent.platform.permissions.broker import PermissionDecision

    return PermissionDecision(behavior="allow")


class _BashThenStopLLM:
    """Emit one bash tool call, then finish after receiving its result."""

    def __init__(self, *, command: str, timeout: float | None) -> None:
        self._command = command
        self._timeout = timeout
        self._calls = 0

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self._calls += 1
        first = self._calls == 1
        return self._stream(first)

    async def _stream(self, first: bool):
        # The loop treats a message with empty content AND finish_reason set as a
        # terminal metadata frame (it skips its body). So the tool_call must ride a
        # frame with finish_reason=None, followed by a separate terminal frame that
        # carries finish_reason — mirroring the real provider's streamed shape.
        if first:
            args: dict[str, Any] = {"command": self._command}
            if self._timeout is not None:
                args["timeout"] = self._timeout
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(call_id="call_1", name="bash", arguments=args),
                ),
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="tool_calls",
                usage=None,
            )
        else:
            yield LLMMessage(
                role="assistant",
                content="done",
                finish_reason=None,
            )
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason="stop",
                usage=None,
            )


def _build(tmp_path: Path, llm_client: Any) -> Any:
    return build_kernel(
        llm=_llm_config(),
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=llm_client,
    )


async def _run_turn_and_collect(
    kernel: Any, session_id: str, tmp_path: Path, text: str
) -> list[dict]:
    """Collect one run's stream through its terminal status event."""
    events: list[dict] = []
    run = kernel.submit(
        session_id=session_id,
        parts=[{"type": "text", "text": text}],
        workspace_root=tmp_path,
    )

    async def _collect() -> None:
        async for event in kernel.stream(session_id):
            events.append(event)
            if (
                event.get("event") == "run_status"
                and event.get("run_id") == run.run_id
                and event.get("status") in {"completed", "failed", "cancelled"}
            ):
                return

    await asyncio.wait_for(_collect(), timeout=20.0)
    return events


@pytest.mark.asyncio
async def test_silent_long_bash_emits_run_heartbeat_through_build_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silent long bash command emits liveness through ``kernel.stream``."""
    monkeypatch.setattr(
        "agent.platform.tools.builtins.bash._FOREGROUND_HEARTBEAT_INTERVAL", 0.2
    )
    kernel = _build(tmp_path, _BashThenStopLLM(command="sleep 1.5", timeout=None))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a slow command"
        )
    finally:
        kernel.close()

    heartbeats = [e for e in events if e.get("event") == "run_heartbeat"]
    assert heartbeats, (
        "no run_heartbeat reached kernel.stream during a silent long bash command — "
        f"liveness chain broken; saw events: {[e.get('event') for e in events]}"
    )


@pytest.mark.asyncio
async def test_bash_timeout_surfaces_tool_timeout_reason_through_build_kernel(
    tmp_path: Path,
) -> None:
    """A bash deadline surfaces ``tool_timeout`` on its stream event."""
    kernel = _build(tmp_path, _BashThenStopLLM(command="sleep 30", timeout=0.5))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a command that times out"
        )
    finally:
        kernel.close()

    tool_ends = [e for e in events if e.get("event") == "tool_end"]
    assert tool_ends, (
        f"no tool_end event seen; events: {[e.get('event') for e in events]}"
    )
    bash_end = next((e for e in tool_ends if e.get("name") == "bash"), None)
    assert bash_end is not None, f"no bash tool_end; tool_ends: {tool_ends}"
    assert bash_end.get("reason_code") == "tool_timeout", (
        f"bash timeout did not surface reason_code=tool_timeout: {bash_end!r}"
    )


class _SlowSleepTool:
    """Block without emitting tool-specific progress events."""

    name = "slow_sleep"
    description = "Sleep for `seconds` seconds without emitting progress (test tool)."
    input_schema = {
        "type": "object",
        "properties": {"seconds": {"type": "number"}},
        "required": ["seconds"],
    }

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:  # noqa: ANN401
        time.sleep(float(args["seconds"]))
        return {"slept": args["seconds"]}


class _SlowToolThenStopLLM:
    """Emit one slow tool call, then finish after receiving its result."""

    def __init__(self, *, seconds: float) -> None:
        self._seconds = seconds
        self._calls = 0

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self._calls += 1
        return self._stream(self._calls == 1)

    async def _stream(self, first: bool):
        if first:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="call_1",
                        name="slow_sleep",
                        arguments={"seconds": self._seconds},
                    ),
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


@pytest.mark.asyncio
async def test_silent_non_bash_tool_emits_run_heartbeat_through_build_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silent non-bash tool inherits generic liveness events."""
    monkeypatch.setattr(
        "agent.core.tools.registry._GENERIC_EXECUTION_HEARTBEAT_INTERVAL", 0.2
    )
    kernel = build_kernel(
        llm=_llm_config(),
        tools=[_SlowSleepTool()],
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_SlowToolThenStopLLM(seconds=1.5),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        events = await _run_turn_and_collect(
            kernel, session.session_id, tmp_path, "run a slow non-bash tool"
        )
    finally:
        kernel.close()

    heartbeats = [e for e in events if e.get("event") == "run_heartbeat"]
    assert heartbeats, (
        "no run_heartbeat reached kernel.stream during a silent long non-bash tool — "
        "generic executor liveness not wired; saw events: "
        f"{[e.get('event') for e in events]}"
    )
    # The heartbeat must come from the generic executing-phase ticker, not bash.
    assert any(e.get("phase") == "executing" for e in heartbeats), (
        f"expected an executing-phase heartbeat from the generic ticker: {heartbeats!r}"
    )
