from agent.core.agent.compaction.planner import CompactionPlanner
from agent.core.agent.compaction.types import CompactionReason
from agent.core.session.entries import SessionEntry, SessionEntryKind


def _turn_entry(
    *,
    entry_id: str,
    role: str,
    content: str,
    tool_phase: str | None = None,
    tool_call_id: str | None = None,
) -> SessionEntry:
    metadata: dict[str, str] = {}
    if tool_phase is not None:
        metadata["tool_phase"] = tool_phase
    if tool_call_id is not None:
        metadata["tool_call_id"] = tool_call_id
    return SessionEntry(
        entry_id=entry_id,
        session_id="sess_compact",
        created_at="2026-02-27T09:00:00+00:00",
        kind=SessionEntryKind.TURN_APPENDED,
        data={
            "turn_id": f"turn_{entry_id}",
            "message_id": f"msg_{entry_id}",
            "role": role,
            "content": content,
            "parts": [],
            "metadata": metadata,
        },
    )


def test_planner_collects_all_turn_events_after_latest_compaction() -> None:
    planner = CompactionPlanner(min_kept_messages=2)
    events = (
        _turn_entry(entry_id="evt_1", role="user", content="old user"),
        _turn_entry(
            entry_id="evt_2",
            role="assistant",
            content="tool call",
            tool_phase="call",
            tool_call_id="call_1",
        ),
        _turn_entry(
            entry_id="evt_3",
            role="tool",
            content="tool result",
            tool_phase="result",
            tool_call_id="call_1",
        ),
        _turn_entry(entry_id="evt_4", role="user", content="latest user"),
    )

    plan = planner.plan(events=events, reason=CompactionReason.THRESHOLD)

    assert plan is not None
    # In the full-compact design, first_kept_event_id is always empty
    # and kept_events is always empty.
    assert plan.first_kept_event_id == ""
    assert plan.kept_events == ()
    assert [entry.entry_id for entry in plan.dropped_events] == [
        "evt_1",
        "evt_2",
        "evt_3",
        "evt_4",
    ]


def test_planner_returns_none_when_no_turn_events_to_compact() -> None:
    planner = CompactionPlanner(min_kept_messages=3)
    events = ()

    plan = planner.plan(events=events, reason=CompactionReason.THRESHOLD)

    assert plan is None


def test_planner_skips_events_before_latest_compaction() -> None:
    from agent.core.session.entries import CompactionEntry, new_compaction_entry

    planner = CompactionPlanner(min_kept_messages=2)
    compaction = new_compaction_entry(
        session_id="sess_compact",
        first_kept_event_id="",
        summary="old summary",
    )
    events = (
        _turn_entry(entry_id="evt_1", role="user", content="before compaction"),
        compaction,
        _turn_entry(entry_id="evt_2", role="user", content="after compaction"),
        _turn_entry(entry_id="evt_3", role="assistant", content="latest answer"),
    )

    plan = planner.plan(events=events, reason=CompactionReason.THRESHOLD)

    assert plan is not None
    assert plan.first_kept_event_id == ""
    assert plan.kept_events == ()
    assert [entry.entry_id for entry in plan.dropped_events] == [
        "evt_2",
        "evt_3",
    ]
