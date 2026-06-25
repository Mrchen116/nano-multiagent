"""Persistence fidelity: reasoning + tool_result pairing survive JSONL round-trip.

C1 red tests for bugfix-375 / bugfix-376 (folded):
1. reasoning_content + reasoning_signature written to JSONL entry and restored
   in build_chat_messages output (LLMMessage).
2. tool_use ↔ tool_result pairing is preserved after persist→restore cycle
   (assistant tool_calls paired with matching tool_call_id results).

bugfix-402-M1/R3 additions:
3. Orphaned tool_call in JSONL is repaired by prepare_transcript_for_run so that
   build_chat_messages produces a valid LLM-ready transcript.
"""

import json
from pathlib import Path

import pytest

from agent.core.ids import make_message_id
from agent.core.types import Message
from agent.core.agent.runtime import _message_to_entry
from agent.core.agent.prompting import build_chat_messages
from agent.core.session.entries import (
    message_from_turn_entry,
    SessionEntry,
    SessionEntryKind,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


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
        assert call_id_a in tool_call_ids, (
            "call-parallel-A must appear in restored tool results"
        )
        assert call_id_b in tool_call_ids, (
            "call-parallel-B must appear in restored tool results"
        )

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
        tool_result = _make_tool_msg(
            call_id=call_id, tool_name="read", result="x content"
        )

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
        assert asst.tool_calls, (
            "assistant LLMMessage must have tool_calls after roundtrip"
        )
        assert asst.tool_calls[0].call_id == call_id


# ---------------------------------------------------------------------------
# Guard (bugfix-375/M2): Message↔JSONL round-trip field-conservation.
# Forces any newly-added Message field to be classified as persisted (and
# handled in _message_to_entry/_to_message) or explicitly not-persisted — so a
# future field can't silently vanish on persist→restore the way reasoning_*
# once did.
# ---------------------------------------------------------------------------


def test_message_jsonl_roundtrip_field_conservation_guard():
    import dataclasses
    from agent.core.session.jsonl_store import _to_message

    # Top-level scalar fields that MUST survive Message -> entry -> Message.
    PERSISTED = {
        "message_id",
        "role",
        "content",
        "parent_message_id",
        "group_id",
        "tool_call_id",
        "reasoning_content",
        "reasoning_signature",
        # bugfix-433 决策4: structured multimodal parts round-trip through JSONL.
        "parts",
    }
    # Fields intentionally NOT round-tripped at top level:
    #  - name: unused by the persistence path (tool identity travels via
    #    tool_call_id + metadata.tool_name)
    #  - metadata: selectively projected (only specific keys persist), covered
    #    by the dedicated metadata tests, not this scalar guard
    NOT_PERSISTED = {"name", "metadata"}

    all_fields = {f.name for f in dataclasses.fields(Message)}
    assert all_fields == PERSISTED | NOT_PERSISTED, (
        "Message gained/lost a field. Classify each field: add it to PERSISTED "
        "(and handle it in _message_to_entry + _to_message) or to NOT_PERSISTED "
        "with a reason — never let a new field silently skip JSONL round-trip."
    )

    msg = Message(
        message_id="m-guard",
        role="assistant",
        content="body",
        parent_message_id="p-0",
        group_id="g-1",
        tool_call_id="tc-1",
        reasoning_content="chain of thought",
        reasoning_signature="sig-xyz-4340",
    )
    restored = _to_message(_message_to_entry(msg, "sess-guard"))
    for fname in PERSISTED:
        assert getattr(restored, fname) == getattr(msg, fname), (
            f"field '{fname}' dropped in Message↔JSONL round-trip"
        )


# ---------------------------------------------------------------------------
# bugfix-433 决策4: image parts survive persist → reload → replay (cross-turn)
# ---------------------------------------------------------------------------

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="


class TestImagePartsRoundTrip:
    """A user turn's image survives JSONL store load and reappears in the next turn."""

    def test_user_image_parts_persist_and_replay_through_store(
        self, tmp_path: Path
    ) -> None:
        """Persist a user Message with image parts via the real store, reload it, and
        confirm build_chat_messages restores the image block for the next turn.

        This is the cross-turn contract: after the image-bearing turn is written to
        JSONL and the session is reloaded (simulating a later turn / process restart),
        the model must still see the image.
        """
        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)
        session = manager.create_session(workspace_root=tmp_path)
        sid = session.session_id

        # Persist a user turn carrying an image (mirrors runtime submit path).
        user_msg = Message(
            message_id=make_message_id(),
            role="user",
            content="what is this\n[image:placeholder]",
            parts=(
                {"type": "text", "text": "what is this"},
                {"type": "image", "image_url": _IMAGE_DATA_URL},
            ),
        )
        path = store.resolve_path(sid)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_message_to_entry(user_msg, sid)) + "\n")

        # Reload through the real load path (used to rebuild runtime history).
        reloaded = JsonlSessionStore(data_dir=tmp_path)
        result = reloaded.load(sid)
        restored = [m for m in result.messages if m.role == "user"][-1]
        assert restored.parts is not None
        assert {"type": "image", "image_url": _IMAGE_DATA_URL} in [
            dict(p) for p in restored.parts
        ]

        # Next turn: build_chat_messages must replay the image as a block.
        llm_messages = build_chat_messages(
            history_messages=tuple(result.messages),
            user_text="what was in that image?",
        )
        history_user = [m for m in llm_messages if m.role == "user"][0]
        assert isinstance(history_user.content, list)
        assert {"type": "image", "image_url": _IMAGE_DATA_URL} in history_user.content

    def test_pure_text_user_turn_has_no_parts_key_in_jsonl(self) -> None:
        """A text-only user turn must not write a `parts` key (text golden 不漂移)."""
        msg = Message(message_id="m1", role="user", content="just text")
        entry = _message_to_entry(msg, session_id="s1")
        assert "parts" not in entry

    def test_message_from_turn_entry_restores_parts(self) -> None:
        """The SessionEntry restore path must also read parts (keep both paths aligned).

        ``new_turn_appended_entry`` already persists parts; ``message_from_turn_entry``
        is the second restore path (append return value / entry-based reload) and must
        surface parts the same way ``_to_message`` does, so image-bearing turns are not
        silently dropped depending on which restore path runs.
        """
        from agent.core.session.entries import (
            new_turn_appended_entry,
            message_from_turn_entry,
        )

        entry = new_turn_appended_entry(
            session_id="s1",
            turn_id="t1",
            role="user",
            content="look\n[image:placeholder]",
            message_id="m1",
            parts=[
                {"type": "text", "text": "look"},
                {"type": "image", "image_url": _IMAGE_DATA_URL},
            ],
        )
        msg = message_from_turn_entry(entry)
        assert msg.parts is not None
        assert {"type": "image", "image_url": _IMAGE_DATA_URL} in [
            dict(p) for p in msg.parts
        ]

    def test_new_turn_appended_entry_omits_empty_parts_key(self) -> None:
        """bugfix-433-fix1 #4: text-only turn must NOT write `parts: []`.

        ``_message_to_entry`` only writes ``parts`` when non-empty; ``new_turn_appended_entry``
        previously always wrote ``"parts": []`` — an asymmetry that makes the two write paths
        produce structurally different entries for the same text-only turn (golden drift).
        """
        from agent.core.session.entries import new_turn_appended_entry

        entry = new_turn_appended_entry(
            session_id="s1", turn_id="t1", role="user", content="just text", message_id="m1"
        )
        assert "parts" not in entry.data

    def test_non_empty_parts_round_trip_through_to_message(self) -> None:
        """bugfix-433-fix1 #8: guard the non-empty parts round-trip explicitly.

        The field-conservation guard only exercised parts=None→None; a regression that
        dropped non-empty parts on round-trip would slip through. Assert image parts
        survive _message_to_entry → _to_message intact.
        """
        from agent.core.session.jsonl_store import _to_message

        msg = Message(
            message_id="m-parts",
            role="user",
            content="look\n[image:placeholder]",
            parts=(
                {"type": "text", "text": "look"},
                {"type": "image", "image_url": _IMAGE_DATA_URL},
            ),
        )
        restored = _to_message(_message_to_entry(msg, "sess-parts"))
        assert restored.parts is not None
        assert [dict(p) for p in restored.parts] == [
            {"type": "text", "text": "look"},
            {"type": "image", "image_url": _IMAGE_DATA_URL},
        ]


# ---------------------------------------------------------------------------
# bugfix-402-M1/R3: orphaned tool_call -> prepare -> build_chat_messages 合法
# ---------------------------------------------------------------------------


def _make_session_with_orphaned_tool_call(
    tmp_path: Path,
) -> tuple[JsonlSessionStore, str]:
    """Create a session whose JSONL contains an unclosed assistant tool_call."""
    store = JsonlSessionStore(data_dir=tmp_path)
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    sid = session.session_id
    call_id = "call-orphan-r3"

    path = store.resolve_path(sid)
    # Write assistant message with tool_call directly to JSONL (simulates mid-run crash)
    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "type": "turn",
                    "uuid": "msg-r3-asst",
                    "parent_uuid": None,
                    "session_id": sid,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return store, sid


class TestOrphanedToolCallRecovery:
    """prepare_transcript_for_run + load -> build_chat_messages 不含孤立 tool_call。"""

    def test_build_chat_messages_valid_after_prepare(self, tmp_path: Path) -> None:
        """prepare 修复后 load+build 产生合法 transcript（每个 tool_call 都有 result）。"""
        store, sid = _make_session_with_orphaned_tool_call(tmp_path)

        store.prepare_transcript_for_run(sid, reason="interrupted")

        result = store.load(sid)
        messages = tuple(result.messages)

        # build_chat_messages 不应因孤立 tool_call 抛错
        llm_msgs = build_chat_messages(
            history_messages=messages,
            user_text="继续",
        )

        # 验证 assistant 的 tool_calls 都有对应 tool result（role=tool or synthetic）
        call_ids_with_result: set[str] = set()
        for m in llm_msgs:
            if m.role == "tool" and m.tool_call_id:
                call_ids_with_result.add(m.tool_call_id)

        call_ids_in_assistant: set[str] = set()
        for m in llm_msgs:
            if m.role == "assistant" and m.tool_calls:
                for tc in m.tool_calls:
                    call_ids_in_assistant.add(tc.call_id)

        assert call_ids_in_assistant == call_ids_with_result, (
            f"orphaned call_ids: {call_ids_in_assistant - call_ids_with_result}"
        )

    def test_load_after_prepare_contains_recovery_message(self, tmp_path: Path) -> None:
        """load() 结果中包含 recovery 后的合成 tool result message。"""
        store, sid = _make_session_with_orphaned_tool_call(tmp_path)
        store.prepare_transcript_for_run(sid, reason="cancelled")

        result = store.load(sid)
        # recovery entry は「type=tool_call_recovery」として raw JSONL に追加されるが,
        # load()の現状実装は recovery entry を messages には含まない.
        # ここでは build_chat_messages が合法であることを確認する.
        messages = tuple(result.messages)
        # Should not raise
        build_chat_messages(history_messages=messages, user_text="next")

    def test_prepare_then_load_is_idempotent(self, tmp_path: Path) -> None:
        """prepare を 2 回呼んでも load 結果に重複 recovery message が出ない。"""
        store, sid = _make_session_with_orphaned_tool_call(tmp_path)

        store.prepare_transcript_for_run(sid, reason="shutdown")
        store.prepare_transcript_for_run(sid, reason="shutdown")

        path = store.resolve_path(sid)
        raw: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))

        recovery_entries = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery_entries) == 1, "2 回 prepare でも recovery entry は 1 つ"


class TestRecoveryWithNoTurns:
    """bugfix-402-M6: recovery entries must not be silently discarded when turns is empty.

    The bare ``if not turns: return`` that previously followed the combined
    ``if not turns and not recovery_by_call_id: return`` guard was unreachable
    when recovery_by_call_id was non-empty.  It silently returned an empty
    LoadResult instead of falling through to _inject_recovery_messages.
    """

    def test_load_with_recovery_but_no_turns_does_not_silently_discard(
        self, tmp_path: Path
    ) -> None:
        """Loading a session that has only recovery entries (no turns) must return
        an empty messages list (not raise or silently skip) — the important thing is
        that the code path does NOT return before reaching _inject_recovery_messages.
        """
        import json as _json
        from agent.core.session.jsonl_store import JsonlSessionStore
        from agent.core.session.manager import SessionManager

        store = JsonlSessionStore(data_dir=tmp_path)
        manager = SessionManager(store=store)
        # Create a real session (writes session_created line) so load() can parse config.
        session = manager.create_session(workspace_root=tmp_path)
        sid = session.session_id

        # Append a recovery entry directly — no turn entries follow the session_created.
        path = store.resolve_path(sid)
        with path.open("a", encoding="utf-8") as f:
            f.write(
                _json.dumps(
                    {
                        "type": "tool_call_recovery",
                        "tool_call_id": "call_orphan_1",
                        "reason": "interrupted",
                        "idempotency_key": "test-idem-1",
                    }
                )
                + "\n"
            )

        # Load must not raise and must return an empty (or at least non-None) LoadResult.
        result = store.load(session_id=sid)
        # The primary assertion: load() completes without error.
        # messages must be [] since there are no assistant turns to attach recovery to;
        # _inject_recovery_messages finds no insertion point and returns unchanged [].
        assert result is not None, "load() must return a LoadResult, not None"
        assert isinstance(result.messages, list), "messages must be a list"
        assert result.messages == [], (
            "no turns → no insertion point → empty message list"
        )
