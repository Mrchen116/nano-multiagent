"""Protect durable admission and model-content proofs through the SDK boundary."""

import asyncio
import threading

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import build_kernel
from tests.contract.test_kernel_sdk_behavior_contract import (
    _allow_all,
    _lc_llm,
    _wait_for_terminal_run,
)


class _Client:
    def __init__(self, *, tool=False, block=False):
        self.tool = tool
        self.block = block
        self.entered = threading.Event()
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        self.entered.set()
        if self.block:
            await asyncio.Event().wait()
        if self.tool and len(self.requests) == 1:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="proof-call", name="receipt_test", arguments={}
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
        else:
            yield LLMMessage(role="assistant", content="done", finish_reason="stop")


class _Tool:
    name = "receipt_test"
    description = "Return model content."
    input_schema = {"type": "object", "properties": {}}
    max_result_size_chars = None

    def __init__(self, fallback=False):
        self.fallback = fallback
        self.serializations = 0

    def run(self, args, ctx):
        return {"body": "完整正文"}

    def serialize_result(self, output, error=None):
        self.serializations += 1
        if self.fallback:
            raise ValueError("serializer unavailable")
        return f"完整正文 {self.serializations}"


def _kernel(tmp_path, client, **kwargs):
    return build_kernel(
        llm=_lc_llm(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        _llm_client_override=client,
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_committed_tool_content_matches_live_context_and_fallback(
    tmp_path, fallback
):
    from agent.sdk import tool_content_digest

    client = _Client(tool=True)
    kernel = _kernel(tmp_path, client, tools=[_Tool(fallback)])
    events = []
    subscription = kernel.observe_events(events.append)
    try:
        session = await kernel.create_session(enabled_tools=["receipt_test"])
        run = kernel.submit(
            session_id=session.session_id, parts=[{"type": "text", "text": "read"}]
        )
        result = await _wait_for_terminal_run(kernel, run.run_id)
        assert result.status == "completed"
        proof = next(
            event for event in events if event["event"] == "tool_result_committed"
        )
        actual = next(
            message.content
            for request in client.requests
            for message in request.messages
            if message.role == "tool"
        )
        assert proof["content_digest"] == tool_content_digest(actual)
        assert proof["serialization_status"] == (
            "fallback" if fallback else "succeeded"
        )
        assert proof["tool_call_id"] == "proof-call"
        assert proof["name"] == "receipt_test"
    finally:
        subscription.close()
        kernel.close()

    replay_client = _Client()
    reopened = _kernel(tmp_path, replay_client, tools=[_Tool(fallback)])
    try:
        next_run = reopened.submit(
            session_id=session.session_id, parts=[{"type": "text", "text": "continue"}]
        )
        await _wait_for_terminal_run(reopened, next_run.run_id)
        persisted = next(
            message.content
            for request in replay_client.requests
            for message in request.messages
            if message.role == "tool"
        )
        assert persisted == actual
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_storage_failure_never_publishes_tool_commit(tmp_path, monkeypatch):
    from agent.core.session.jsonl_writer import JsonlWriter

    ran = threading.Event()

    class StorageFailureTool(_Tool):
        def run(self, args, ctx):
            ran.set()
            return super().run(args, ctx)

    original = JsonlWriter.durable_barrier

    def fail_after_tool(writer, *args, **kwargs):
        if ran.is_set():
            raise OSError("durability unavailable")
        return original(writer, *args, **kwargs)

    client = _Client(tool=True)
    kernel = _kernel(tmp_path, client, tools=[StorageFailureTool()])
    events = []
    subscription = kernel.observe_events(events.append)
    try:
        session = await kernel.create_session(enabled_tools=["receipt_test"])
        monkeypatch.setattr(JsonlWriter, "durable_barrier", fail_after_tool)
        run = kernel.submit(
            session_id=session.session_id, parts=[{"type": "text", "text": "read"}]
        )
        result = await _wait_for_terminal_run(kernel, run.run_id)
        assert ran.is_set() and result.status == "failed"
        assert not any(event["event"] == "tool_result_committed" for event in events)
    finally:
        monkeypatch.undo()
        subscription.close()
        kernel.close()


@pytest.mark.asyncio
async def test_real_agent_child_has_link_tools_and_terminal_without_top_level_run(
    tmp_path,
):
    from agent.core.types import TokenUsage

    class DelegatingClient:
        async def generate(self, request):
            texts = [
                str(message.content)
                for message in request.messages
                if message.role == "user"
            ]
            calls = [
                call for message in request.messages for call in message.tool_calls
            ]
            available = {tool.name for tool in request.tools}
            if "agent" in available and "delegate-child" in texts and not calls:
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="delegate",
                            name="agent",
                            arguments={
                                "description": "Inspect receipt",
                                "prompt": "child-read",
                                "run_in_background": False,
                            },
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
            elif (
                "read" in available
                and any(text.endswith("child-read") for text in texts)
                and not calls
            ):
                yield LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="child-proof",
                            name="read",
                            arguments={"path": str(tmp_path / "evidence.txt")},
                        ),
                    ),
                )
                yield LLMMessage(
                    role="assistant", content="", finish_reason="tool_calls"
                )
            else:
                yield LLMMessage(role="assistant", content="done")
                yield LLMMessage(
                    role="assistant",
                    content="",
                    finish_reason="stop",
                    usage=TokenUsage(
                        prompt_tokens=8, completion_tokens=3, total_tokens=11
                    ),
                )

    (tmp_path / "evidence.txt").write_text("child evidence")
    kernel = _kernel(tmp_path, DelegatingClient())
    events = []
    subscription = kernel.observe_events(events.append)
    try:
        session = await kernel.create_session(enabled_tools=["agent", "read"])
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "delegate-child"}],
        )
        result = await _wait_for_terminal_run(kernel, run.run_id)
        assert result.status == "completed"
        link = next(event for event in events if event["event"] == "session_linked")
        child_events = [
            event for event in events if event["session_id"] == link["child_session_id"]
        ]
        names = {event["event"] for event in child_events}
        assert {
            "turn_started",
            "turn_input_committed",
            "tool_start",
            "tool_end",
            "tool_result_committed",
            "turn_end",
        } <= names
        assert all(event.get("run_id") is None for event in child_events)
        child_starts = [
            event for event in child_events if event["event"] == "tool_start"
        ]
        child_ends = [event for event in child_events if event["event"] == "tool_end"]
        assert len(child_starts) == len(child_ends) == 1
        assert child_starts[0]["call_id"] == child_ends[0]["call_id"] == "child-proof"
        assert child_starts[0]["turn_id"] == child_ends[0]["turn_id"]
        assert child_starts[0]["turn_id"]
        assert link["sequence_num"] < min(
            event["sequence_num"] for event in child_events
        )
        terminal = next(event for event in child_events if event["event"] == "turn_end")
        assert terminal["usage"]["prompt_tokens"] == 8
        assert terminal["elapsed_ms"] >= 0
    finally:
        subscription.close()
        kernel.close()
