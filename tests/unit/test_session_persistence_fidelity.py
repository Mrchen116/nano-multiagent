"""Persistence fidelity: reasoning + tool_result pairing survive JSONL round-trip.

C1 red tests for bugfix-375 / bugfix-376 (folded):
1. reasoning_content + reasoning_signature written to JSONL entry and restored
   in build_chat_messages output (LLMMessage).
2. tool_use ↔ tool_result pairing is preserved after persist→restore cycle
   (assistant tool_calls paired with matching tool_call_id results).
"""

import json

import pytest

from agent.core.ids import make_message_id
from agent.core.types import Message
from agent.core.agent.runtime import _message_to_entry
from agent.core.agent.prompting import build_chat_messages
from agent.core.session.entries import message_from_turn_entry, SessionEntry, SessionEntryKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assistant_msg(
    *,
    content: str = "thinking about it",
    tool_calls: list[dict] | None = None,
    reasoning_content: str | None = None,
    reasoning_signature: str | None = None,
) -> Message:
    metadata: dict = {}
    if tool_calls:
        metadata["tool_calls"] = tool_calls
    return Message(
        message_id=make_message_id(),
        role="assistant",
        content=content,
        metadata=metadata,
        reasoning_content=reasoning_content,
        reasoning_signature=reasoning_signature,
    )


def _make_tool_msg(*, call_id: str, tool_name: str, result: str) -> Message:
    return Message(
        message_id=make_message_id(),
        role="tool",
        content=result,
        tool_call_id=call_id,
        metadata={"tool_name": tool_name},
    )


def _entry_to_message(entry: dict) -> Message:
    """Simulate what session restore does: JSONL dict → SessionEntry → Message.

    Mirrors the real restore path in jsonl_store._to_message + _build_turn_metadata,
    which reads reasoning/tool fields from JSONL top-level into metadata.
    """
    se = SessionEntry(
        entry_id=entry.get("uuid", make_message_id()),
        session_id=entry.get("session_id", "test-session"),
        created_at=entry.get("timestamp", "2026-01-01T00:00:00+00:00"),
        kind=SessionEntryKind.TURN_APPENDED,
        data={
            "turn_id": "turn-1",
            "message_id": entry.get("uuid"),
            "role": entry["role"],
            "content": entry["content"],
            "tool_call_id": entry.get("tool_call_id"),
            "group_id": entry.get("group_id"),
            "parts": [],
            "metadata": {
                k: entry[k]
                for k in (
                    "tool_calls",
                    "tool_name",
                    "tool_error",
                    "tool_output",
                    "reasoning_content",
                    "reasoning_signature",
                )
                if k in entry
            },
        },
    )
    return message_from_turn_entry(se)


def _roundtrip(msg: Message) -> Message:
    """Persist msg → JSONL entry → restore as Message."""
    entry = _message_to_entry(msg, session_id="test-session")
    return _entry_to_message(entry)


# ---------------------------------------------------------------------------
# C1-R1: reasoning_content is written to JSONL and restored
# ---------------------------------------------------------------------------

class TestReasoningPersistence:
    def test_reasoning_content_written_to_jsonl_entry(self):
        msg = _make_assistant_msg(
            reasoning_content="let me think step by step",
            reasoning_signature="sig-abc123",
        )
        entry = _message_to_entry(msg, session_id="s1")
        assert entry.get("reasoning_content") == "let me think step by step", (
            "_message_to_entry must write reasoning_content to JSONL"
        )
        assert entry.get("reasoning_signature") == "sig-abc123", (
            "_message_to_entry must write reasoning_signature to JSONL"
        )

    def test_reasoning_fields_on_message_type(self):
        """Message dataclass must carry reasoning fields as first-class attrs."""
        msg = Message(
            message_id="m1",
            role="assistant",
            content="hi",
            reasoning_content="thinking...",
            reasoning_signature="sig-xyz",
        )
        assert msg.reasoning_content == "thinking..."
        assert msg.reasoning_signature == "sig-xyz"

    def test_restored_message_carries_reasoning(self):
        msg = _make_assistant_msg(
            content="answer",
            reasoning_content="step 1: ...",
            reasoning_signature="sig-001",
        )
        restored = _roundtrip(msg)
        assert restored.reasoning_content == "step 1: ...", (
            "restored Message must carry reasoning_content"
        )
        assert restored.reasoning_signature == "sig-001", (
            "restored Message must carry reasoning_signature"
        )

    def test_build_chat_messages_emits_reasoning_fields(self):
        """build_chat_messages must pass reasoning through to LLMMessage."""
        history = (
            _roundtrip(
                _make_assistant_msg(
                    content="okay",
                    reasoning_content="inner monologue",
                    reasoning_signature="sig-999",
                )
            ),
        )
        llm_messages = build_chat_messages(
            history_messages=history,
            user_text="next question",
        )
        assistant_msgs = [m for m in llm_messages if m.role == "assistant"]
        assert assistant_msgs, "expected at least one assistant LLMMessage"
        asst = assistant_msgs[0]
        assert asst.reasoning_content == "inner monologue", (
            "build_chat_messages must propagate reasoning_content from Message"
        )
        assert asst.reasoning_signature == "sig-999", (
            "build_chat_messages must propagate reasoning_signature from Message"
        )

    def test_reasoning_none_when_absent(self):
        msg = _make_assistant_msg(content="no thinking here")
        entry = _message_to_entry(msg, session_id="s1")
        assert "reasoning_content" not in entry
        assert "reasoning_signature" not in entry
        restored = _roundtrip(msg)
        assert restored.reasoning_content is None
        assert restored.reasoning_signature is None


# ---------------------------------------------------------------------------
# C1-R2: tool_use ↔ tool_result pairing survives persist→restore
# ---------------------------------------------------------------------------

class TestToolResultPairingFidelity:
    def test_tool_call_id_written_to_jsonl_entry(self):
        msg = _make_tool_msg(call_id="call-A", tool_name="read", result="file contents")
        entry = _message_to_entry(msg, session_id="s1")
        assert entry.get("tool_call_id") == "call-A", (
            "_message_to_entry must write tool_call_id to JSONL"
        )

    def test_tool_call_id_restored_on_message(self):
        msg = _make_tool_msg(call_id="call-B", tool_name="bash", result="output")
        restored = _roundtrip(msg)
        assert restored.tool_call_id == "call-B"
        assert restored.role == "tool"

    def test_parallel_tool_results_pair_correctly_in_build_chat_messages(self):
        """Two parallel tool_use blocks must pair with their results in LLM history."""
        call_id_a = "call-parallel-A"
        call_id_b = "call-parallel-B"

        assistant_msg = _make_assistant_msg(
            content="",
            tool_calls=[
                {"call_id": call_id_a, "name": "read", "arguments": {"path": "a.py"}},
                {"call_id": call_id_b, "name": "read", "arguments": {"path": "b.py"}},
            ],
        )
        tool_a = _make_tool_msg(call_id=call_id_a, tool_name="read", result="content A")
        tool_b = _make_tool_msg(call_id=call_id_b, tool_name="read", result="content B")

        # Roundtrip all three through persist→restore
        history = (
            _roundtrip(assistant_msg),
            _roundtrip(tool_a),
            _roundtrip(tool_b),
        )

        llm_messages = build_chat_messages(
            history_messages=history,
            user_text="continue",
        )

        tool_msgs = [m for m in llm_messages if m.role == "tool"]
        assert len(tool_msgs) == 2, f"expected 2 tool messages, got {len(tool_msgs)}"

        tool_call_ids = {m.tool_call_id for m in tool_msgs}
        assert call_id_a in tool_call_ids, "call-parallel-A must appear in restored tool results"
        assert call_id_b in tool_call_ids, "call-parallel-B must appear in restored tool results"

    def test_assistant_tool_calls_restored_from_jsonl(self):
        """tool_calls metadata must survive JSONL roundtrip and appear in LLMMessage."""
        call_id = "call-single-X"
        assistant_msg = _make_assistant_msg(
            content="",
            tool_calls=[
                {"call_id": call_id, "name": "bash", "arguments": {"command": "ls"}},
            ],
        )
        restored = _roundtrip(assistant_msg)
        assert restored.metadata.get("tool_calls"), (
            "tool_calls metadata must survive roundtrip"
        )
        tc_list = restored.metadata["tool_calls"]
        assert len(tc_list) == 1
        assert tc_list[0]["call_id"] == call_id

    def test_build_chat_messages_has_tool_calls_on_assistant(self):
        """After roundtrip, build_chat_messages must produce LLMMessage with tool_calls."""
        call_id = "call-single-Y"
        assistant_msg = _make_assistant_msg(
            content="",
            tool_calls=[
                {"call_id": call_id, "name": "read", "arguments": {"path": "x.py"}},
            ],
        )
        tool_result = _make_tool_msg(call_id=call_id, tool_name="read", result="x content")

        history = (
            _roundtrip(assistant_msg),
            _roundtrip(tool_result),
        )
        llm_messages = build_chat_messages(
            history_messages=history,
            user_text="done",
        )
        asst_msgs = [m for m in llm_messages if m.role == "assistant"]
        assert asst_msgs, "expected at least one assistant LLMMessage after roundtrip"
        asst = asst_msgs[0]
        assert asst.tool_calls, "assistant LLMMessage must have tool_calls after roundtrip"
        assert asst.tool_calls[0].call_id == call_id
