"""Intent-level query tests for event persistence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.events import EventReplayResult
from IM.infra.repositories.events import EventRepository
from IM.infra.repositories.users import UserRepository


def _build_event_fixture(tmp_path: Path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    outsider = users.create_user(username="outsider", display_name="Outsider")
    conversations = ConversationRepository(connection)
    visible = conversations.create_conversation(
        title="visible",
        participant_ids=[alice.id, bob.id],
        caller_owner_id=alice.owner_id,
    )
    hidden = conversations.create_conversation(
        title="hidden",
        participant_ids=[outsider.id],
        caller_owner_id=outsider.owner_id,
    )
    return connection, EventRepository(connection), alice, bob, visible, hidden


def test_event_queries_return_recipients_and_global_cursor(tmp_path: Path) -> None:
    """Resolve recipient ordering and the global cursor behind one interface."""
    _connection, events, _alice, _bob, visible, hidden = _build_event_fixture(tmp_path)
    visible_event = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="message.sent",
        delivery_status="sent",
        payload={},
    )
    hidden_event = events.append_event(
        conversation_id=hidden.id,
        message_id=None,
        event_type="message.sent",
        delivery_status="sent",
        payload={},
    )

    assert events.recipient_user_ids(visible.id) == tuple(visible.participant_ids)
    assert events.global_max_event_id() == hidden_event.event_id
    assert hidden_event.event_id > visible_event.event_id


def test_user_resume_filters_visibility_and_orders_events(tmp_path: Path) -> None:
    """Replay only events visible to the user, ordered after the supplied cursor."""
    _connection, events, alice, _bob, visible, hidden = _build_event_fixture(tmp_path)
    first = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="run.started",
        delivery_status="running",
        payload={},
    )
    events.append_event(
        conversation_id=hidden.id,
        message_id=None,
        event_type="run.started",
        delivery_status="running",
        payload={},
    )
    last = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="run.completed",
        delivery_status="completed",
        payload={},
    )

    replay = events.list_events_for_user_resume(
        user_id=alice.id,
        after_event_id=first.event_id,
    )

    assert replay == EventReplayResult(
        events=[last],
        resync_required=False,
        reason=None,
    )


def test_user_resume_reports_gap_and_window_miss(tmp_path: Path) -> None:
    """Preserve distinct resync reasons for oversized gaps and stale cursors."""
    connection, events, alice, _bob, visible, _hidden = _build_event_fixture(tmp_path)
    first = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="run.started",
        delivery_status="running",
        payload={},
    )
    second = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="run.completed",
        delivery_status="completed",
        payload={},
    )

    gap = events.list_events_for_user_resume(
        user_id=alice.id,
        after_event_id=first.event_id,
        max_gap=0,
    )
    assert gap.resync_required is True
    assert gap.reason == "event_gap_exceeded"

    old = (
        (datetime.now(timezone.utc) - timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z")
    )
    with connection:
        connection.execute(
            "UPDATE conversation_events SET created_at = ? WHERE event_id = ?",
            (old, second.event_id),
        )
    stale = events.list_events_for_user_resume(
        user_id=alice.id,
        after_event_id=first.event_id,
        max_gap=100,
        replay_window_minutes=15,
    )
    assert stale.resync_required is True
    assert stale.reason == "cursor_stale_or_outside_replay_window"


def test_user_resume_reports_cursor_ahead_of_current_event_store(
    tmp_path: Path,
) -> None:
    """A browser cursor from an older DB epoch must receive an explicit reset reason."""
    _connection, events, alice, _bob, visible, _hidden = _build_event_fixture(tmp_path)
    latest = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="run.completed",
        delivery_status="completed",
        payload={},
    )

    ahead = events.list_events_for_user_resume(
        user_id=alice.id,
        after_event_id=latest.event_id + 100,
    )

    assert ahead.resync_required is True
    assert ahead.reason == "cursor_ahead_of_event_store"


def test_event_enrichment_queries_return_typed_identity_maps(tmp_path: Path) -> None:
    """Resolve relay history and agent labels without exposing SQL rows."""
    connection, events, _alice, _bob, visible, _hidden = _build_event_fixture(tmp_path)
    AgentProfileRepository(connection).upsert_profile(
        agent_id="plato",
        owner_id=visible.owner_id,
        display_name="Plato",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )
    accepted = events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="relay.accepted",
        delivery_status="running",
        payload={
            "run_id": "run-1",
            "relay_task_id": "relay-1",
            "agent_id": "plato",
        },
    )
    events.append_event(
        conversation_id=visible.id,
        message_id=None,
        event_type="relay.accepted",
        delivery_status="running",
        payload={"detail": "run_id=run-2", "agent_id": "plato"},
    )

    identities = events.relay_run_identities(
        conversation_id=visible.id,
        up_to_event_id=accepted.event_id + 1,
    )

    assert identities["run-1"].relay_task_id == "relay-1"
    assert identities["run-1"].agent_id == "plato"
    assert identities["run-2"].relay_task_id is None
    assert events.agent_display_names({"plato", "missing"}) == {"plato": "Plato"}
