"""M246: GroupContextStore sender 字段存储与 drain 返回 (sender, text) 元组测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.gateway.group_context_store import GroupContextStore


def test_append_and_drain_stores_sender(tmp_path: Path) -> None:
    """append 写入 sender；drain 返回 (sender, text) 元组列表。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("key1", "hello", sender="user-1")
    store.append("key1", "world", sender="user-2")

    drained = store.drain("key1")

    assert drained == [("user-1", "hello"), ("user-2", "world")]


def test_drain_returns_sender_text_tuples(tmp_path: Path) -> None:
    """drain 每项都是 (sender, text) 元组，顺序与插入顺序一致。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("k", "msg-a", sender="alice")
    store.append("k", "msg-b", sender="bob")
    store.append("k", "msg-c", sender="alice")

    result = store.drain("k")

    assert len(result) == 3
    assert result[0] == ("alice", "msg-a")
    assert result[1] == ("bob", "msg-b")
    assert result[2] == ("alice", "msg-c")


def test_append_default_sender_is_empty(tmp_path: Path) -> None:
    """append 不传 sender 时默认空字符串，drain 仍返回 ('', text)。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("k", "anon message")

    result = store.drain("k")

    assert result == [("", "anon message")]


def test_drain_empty_returns_empty_list(tmp_path: Path) -> None:
    """drain 无行时返回空列表。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")

    assert store.drain("nonexistent") == []


def test_drain_is_atomic_delete(tmp_path: Path) -> None:
    """drain 之后再 drain 同一 key 返回空。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("k", "x", sender="u")

    first = store.drain("k")
    second = store.drain("k")

    assert first == [("u", "x")]
    assert second == []


def test_drain_only_drains_matching_key(tmp_path: Path) -> None:
    """drain 只清除指定 buf_key，不影响其他 key。"""
    store = GroupContextStore(db_path=tmp_path / "ctx.sqlite3")
    store.append("key-a", "msg-a", sender="u1")
    store.append("key-b", "msg-b", sender="u2")

    drained_a = store.drain("key-a")
    remaining_b = store.drain("key-b")

    assert drained_a == [("u1", "msg-a")]
    assert remaining_b == [("u2", "msg-b")]
