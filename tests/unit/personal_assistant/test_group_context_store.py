"""Behavior tests for persisted group background context."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.gateway.group_context_store import GroupContextStore


def test_drain_preserves_sender_order_and_consumes_messages_once(
    tmp_path: Path,
) -> None:
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("group-a", "hello", sender="alice")
    store.append("group-a", "world", sender="bob")

    assert store.drain("group-a") == [("alice", "hello"), ("bob", "world")]
    assert store.drain("group-a") == []


def test_drain_isolated_to_requested_group(tmp_path: Path) -> None:
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("group-a", "message-a", sender="alice")
    store.append("group-b", "message-b", sender="bob")

    assert store.drain("group-a") == [("alice", "message-a")]
    assert store.drain("group-b") == [("bob", "message-b")]


def test_drain_with_metadata_preserves_multimodal_projection(tmp_path: Path) -> None:
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    metadata = {
        "attachments": [{"url": "data:image/png;base64,aW1hZ2U="}],
        "kernel_input_parts": [{"type": "image", "attachment_index": 0}],
    }
    store.append("group-a", "", sender="alice", metadata=metadata)

    assert store.drain_with_metadata("group-a") == [("alice", "", metadata)]
    assert store.drain_with_metadata("group-a") == []


def test_reopen_preserves_frozen_human_message_context(tmp_path: Path) -> None:
    db_path = tmp_path / "ctx.sqlite3"
    frozen = {
        "_pa_human_message_context": {
            "version": 1,
            "header": "[Feishu Mon 2026-08-10 09:17 CST]",
            "time_zone": "Asia/Shanghai",
        }
    }
    GroupContextStore(db_path=db_path).append(
        "group-a", "hello", sender="alice", metadata=frozen
    )

    reopened = GroupContextStore(db_path=db_path)

    assert reopened.drain_with_metadata("group-a") == [("alice", "hello", frozen)]
