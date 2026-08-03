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
