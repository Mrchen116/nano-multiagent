"""Tests for jsonl_store.load() DAG recovery with group_id."""

from pathlib import Path

import pytest

from agent.core.session.jsonl_store import JsonlSessionStore


def _write_turn(path: Path, **fields: object) -> None:
    import json
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fields, ensure_ascii=False) + "\n")


async def test_load_recovers_orphaned_parallel_tool_results(tmp_path: Path) -> None:
    """Parallel tool results (same group_id) orphaned by linked-list backtrack are recovered."""
    store = JsonlSessionStore(data_dir=tmp_path / "data")
    path = store.resolve_path("sess_1")
    path.parent.mkdir(parents=True, exist_ok=True)

    # session_created
    _write_turn(path, type="session_created", session_id="sess_1", created_at="2026-01-01T00:00:00+00:00")

    # Turn 1: user -> assistant -> tool_a + tool_b (parallel, same group_id)
    _write_turn(path, type="turn", uuid="u1", role="user", content="hello", timestamp="2026-01-01T00:01:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a1",
        parent_uuid="u1",
        group_id="a1",
        role="assistant",
        content="",
        tool_calls=[{"call_id": "c1", "name": "echo", "arguments": {"text": "a"}}],
        timestamp="2026-01-01T00:01:01+00:00",
    )
    _write_turn(
        path,
        type="turn",
        uuid="t1",
        parent_uuid="a1",
        group_id="a1",
        role="tool",
        content="result-a",
        tool_call_id="c1",
        timestamp="2026-01-01T00:01:02+00:00",
    )
    _write_turn(
        path,
        type="turn",
        uuid="t2",
        parent_uuid="a1",
        group_id="a1",
        role="tool",
        content="result-b",
        tool_call_id="c2",
        timestamp="2026-01-01T00:01:03+00:00",
    )

    # Turn 2: user -> assistant (no tool calls)
    _write_turn(path, type="turn", uuid="u2", parent_uuid="a1", role="user", content="next", timestamp="2026-01-01T00:02:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a2",
        parent_uuid="u2",
        group_id="a2",
        role="assistant",
        content="ok",
        timestamp="2026-01-01T00:02:01+00:00",
    )

    result = store.load("sess_1")
    messages = result.messages
    roles = [m.role for m in messages]

    # All messages should be present, including both parallel tool results
    assert roles == ["user", "assistant", "tool", "tool", "user", "assistant"]

    # Both tool results point to the assistant as parent
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 2
    assert tool_msgs[0].parent_message_id == "a1"
    assert tool_msgs[1].parent_message_id == "a1"

    # Both tool results share the same group_id as the assistant
    assert tool_msgs[0].group_id == "a1"
    assert tool_msgs[1].group_id == "a1"


async def test_load_excludes_dead_branches_from_rewind(tmp_path: Path) -> None:
    """Rewound dead branches (different group_id) must NOT be recovered."""
    store = JsonlSessionStore(data_dir=tmp_path / "data")
    path = store.resolve_path("sess_2")
    path.parent.mkdir(parents=True, exist_ok=True)

    _write_turn(path, type="session_created", session_id="sess_2", created_at="2026-01-01T00:00:00+00:00")

    # Active path: u1 -> a1 -> u2 -> a2
    _write_turn(path, type="turn", uuid="u1", role="user", content="hello", timestamp="2026-01-01T00:01:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a1",
        parent_uuid="u1",
        group_id="a1",
        role="assistant",
        content="ack",
        timestamp="2026-01-01T00:01:01+00:00",
    )
    _write_turn(path, type="turn", uuid="u2", parent_uuid="a1", role="user", content="next", timestamp="2026-01-01T00:02:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a2",
        parent_uuid="u2",
        group_id="a2",
        role="assistant",
        content="ok",
        timestamp="2026-01-01T00:02:01+00:00",
    )

    # Dead branch (rewound): u1 -> a1_dead -> t_dead (different group_id, parent is in active chain)
    _write_turn(
        path,
        type="turn",
        uuid="a1_dead",
        parent_uuid="u1",
        group_id="dead_group",
        role="assistant",
        content="wrong",
        timestamp="2026-01-01T00:01:50+00:00",
    )
    _write_turn(
        path,
        type="turn",
        uuid="t_dead",
        parent_uuid="a1_dead",
        group_id="dead_group",
        role="tool",
        content="dead result",
        tool_call_id="c_dead",
        timestamp="2026-01-01T00:01:51+00:00",
    )

    result = store.load("sess_2")
    messages = result.messages
    uuids = {m.message_id for m in messages}

    # Active path should be present
    assert "u1" in uuids
    assert "a1" in uuids
    assert "u2" in uuids
    assert "a2" in uuids

    # Dead branch should NOT be recovered
    assert "a1_dead" not in uuids
    assert "t_dead" not in uuids


async def test_load_without_parent_links_uses_chronological_order(tmp_path: Path) -> None:
    """Backward-compatible flat turns (no parent_uuid) fall back to chronological order."""
    store = JsonlSessionStore(data_dir=tmp_path / "data")
    path = store.resolve_path("sess_3")
    path.parent.mkdir(parents=True, exist_ok=True)

    _write_turn(path, type="session_created", session_id="sess_3", created_at="2026-01-01T00:00:00+00:00")

    # Flat turns without parent_uuid
    _write_turn(path, type="turn", uuid="u1", role="user", content="first", timestamp="2026-01-01T00:01:00+00:00")
    _write_turn(path, type="turn", uuid="a1", role="assistant", content="ack1", timestamp="2026-01-01T00:01:01+00:00")
    _write_turn(path, type="turn", uuid="u2", role="user", content="second", timestamp="2026-01-01T00:02:00+00:00")
    _write_turn(path, type="turn", uuid="a2", role="assistant", content="ack2", timestamp="2026-01-01T00:02:01+00:00")

    result = store.load("sess_3")
    messages = result.messages

    assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [m.message_id for m in messages] == ["u1", "a1", "u2", "a2"]


async def test_load_with_compact_boundary_skips_pre_boundary_orphans(tmp_path: Path) -> None:
    """Orphans before compact_boundary are ignored even if group_id matches."""
    store = JsonlSessionStore(data_dir=tmp_path / "data")
    path = store.resolve_path("sess_4")
    path.parent.mkdir(parents=True, exist_ok=True)

    _write_turn(path, type="session_created", session_id="sess_4", created_at="2026-01-01T00:00:00+00:00")

    # Pre-boundary: user -> assistant -> tool_a + tool_b
    _write_turn(path, type="turn", uuid="u_old", role="user", content="old", timestamp="2026-01-01T00:01:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a_old",
        parent_uuid="u_old",
        group_id="a_old",
        role="assistant",
        content="",
        timestamp="2026-01-01T00:01:01+00:00",
    )
    _write_turn(
        path,
        type="turn",
        uuid="t_old_1",
        parent_uuid="a_old",
        group_id="a_old",
        role="tool",
        content="old-result-1",
        timestamp="2026-01-01T00:01:02+00:00",
    )
    _write_turn(
        path,
        type="turn",
        uuid="t_old_2",
        parent_uuid="a_old",
        group_id="a_old",
        role="tool",
        content="old-result-2",
        timestamp="2026-01-01T00:01:03+00:00",
    )

    # Compact boundary
    _write_turn(
        path,
        type="compact_boundary",
        session_id="sess_4",
        timestamp="2026-01-01T00:02:00+00:00",
    )

    # Post-boundary: user -> assistant
    _write_turn(path, type="turn", uuid="u_new", role="user", content="new", timestamp="2026-01-01T00:03:00+00:00")
    _write_turn(
        path,
        type="turn",
        uuid="a_new",
        parent_uuid="u_new",
        group_id="a_new",
        role="assistant",
        content="ack",
        timestamp="2026-01-01T00:03:01+00:00",
    )

    result = store.load("sess_4")
    messages = result.messages

    # Only post-boundary messages should appear
    assert [m.role for m in messages] == ["user", "assistant"]
    assert {m.message_id for m in messages} == {"u_new", "a_new"}
