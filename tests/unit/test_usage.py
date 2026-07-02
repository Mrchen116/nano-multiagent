from __future__ import annotations

import json
from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.skills.usage import (
    F4Trigger,
    bump_skill_usage,
    ensure_skill_record,
    reset_uses_since_last_batch,
)


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


def test_bump_skill_usage_returns_f4_trigger_for_auto_skill_threshold(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "skills"
    skill_root.mkdir()
    ensure_skill_record(
        skill_root=skill_root,
        skill_name="auto-skill",
        source="F3",
        now_iso="2026-07-01T00:00:00Z",
    )

    first = bump_skill_usage(
        skill_root=skill_root,
        skill_name="auto-skill",
        session_id="session-1",
        tool_call_id="call-1",
        source="F3",
        now_iso="2026-07-02T10:00:00Z",
        threshold=2,
    )
    second = bump_skill_usage(
        skill_root=skill_root,
        skill_name="auto-skill",
        session_id="session-2",
        tool_call_id="call-2",
        source="F3",
        now_iso="2026-07-02T11:00:00Z",
        threshold=2,
    )

    assert first.trigger is None
    assert second.trigger is not None
    assert second.trigger.skill_name == "auto-skill"
    assert [ref["session_id"] for ref in second.trigger.session_refs] == [
        "session-1",
        "session-2",
    ]

    reset_uses_since_last_batch(skill_root=skill_root, skill_name="auto-skill")
    data = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    assert data["auto-skill"]["uses_since_last_B"] == 0


def test_bump_skill_usage_does_not_trigger_f4_for_manual_skill(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    skill_root.mkdir()

    result = bump_skill_usage(
        skill_root=skill_root,
        skill_name="manual-skill",
        session_id="session-1",
        tool_call_id="call-1",
        source="F1",
        now_iso="2026-07-02T10:00:00Z",
        threshold=1,
    )

    assert result.trigger is None


def test_runtime_dedupes_running_or_queued_skill_batch_reviews() -> None:
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime._skill_batch_review_queued = set()
    runtime._skill_batch_review_running = set()
    trigger = F4Trigger(
        skill_name="auto-skill",
        skill_root=Path("/tmp/skills"),
        session_refs=(),
        call_key="session-1:call-1",
    )

    assert AgentRuntime.enqueue_skill_batch_review(runtime, trigger) is True
    assert AgentRuntime.enqueue_skill_batch_review(runtime, trigger) is False
    runtime._skill_batch_review_queued.clear()
    runtime._skill_batch_review_running.add("auto-skill")
    assert AgentRuntime.enqueue_skill_batch_review(runtime, trigger) is False
