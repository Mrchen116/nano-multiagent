from __future__ import annotations

import json
from pathlib import Path

from agent.core.skills.usage import bump_skill_usage, ensure_skill_record


def test_bump_skill_usage_records_session_ref_and_source(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    skill_root.mkdir()

    result = bump_skill_usage(
        skill_root=skill_root,
        skill_name="review-skill",
        session_id="session-1",
        tool_call_id="call-1",
        source="F3",
        now_iso="2026-07-02T10:00:00Z",
    )

    assert result.counted is True
    data = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    record = data["review-skill"]
    assert record["source"] == "F3"
    assert record["use_count"] == 1
    assert record["last_used_at"] == "2026-07-02T10:00:00Z"
    assert record["session_refs"] == [
        {
            "session_id": "session-1",
            "tool_call_id": "call-1",
            "timestamp": "2026-07-02T10:00:00Z",
        }
    ]
    assert record["recent_call_keys"] == ["session-1:call-1"]


def test_bump_skill_usage_is_idempotent_for_same_tool_call(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    skill_root.mkdir()

    first = bump_skill_usage(
        skill_root=skill_root,
        skill_name="review-skill",
        session_id="session-1",
        tool_call_id="call-1",
        source="F4",
        now_iso="2026-07-02T10:00:00Z",
    )
    second = bump_skill_usage(
        skill_root=skill_root,
        skill_name="review-skill",
        session_id="session-1",
        tool_call_id="call-1",
        source="F4",
        now_iso="2026-07-02T10:05:00Z",
    )

    assert first.counted is True
    assert second.counted is False
    data = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    record = data["review-skill"]
    assert record["use_count"] == 1
    assert record["last_used_at"] == "2026-07-02T10:00:00Z"
    assert len(record["session_refs"]) == 1


def test_ensure_skill_record_preserves_existing_source(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    skill_root.mkdir()

    ensure_skill_record(
        skill_root=skill_root,
        skill_name="manual-skill",
        source="F1",
        now_iso="2026-07-01T09:00:00Z",
    )
    ensure_skill_record(
        skill_root=skill_root,
        skill_name="manual-skill",
        source="F2",
        now_iso="2026-07-02T09:00:00Z",
    )

    data = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    assert data["manual-skill"]["source"] == "F1"
    assert data["manual-skill"]["created_at"] == "2026-07-01T09:00:00Z"
