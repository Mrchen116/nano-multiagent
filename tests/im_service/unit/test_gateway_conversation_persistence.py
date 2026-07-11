"""Behavior tests for the concrete Gateway conversation persistence seam."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import (
    AgentDispatchRecord,
    GatewayConversationPersistence,
)
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    UserRepository,
)


def _build(
    tmp_path: Path,
) -> tuple[sqlite3.Connection, GatewayConversationPersistence]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return connection, GatewayConversationPersistence(connection)


def _upsert_profile(
    connection: sqlite3.Connection,
    *,
    agent_id: str,
    owner_id: str,
    node_id: str | None,
) -> None:
    AgentProfileRepository(connection).upsert_profile(
        agent_id=agent_id,
        owner_id=owner_id,
        node_id=node_id,
        display_name=f"Agent {agent_id}",
        description="",
        system_prompt=f"You are {agent_id}.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=f"/work/{agent_id}",
    )


def test_resolve_send_target_classifies_all_target_forms_and_reuses_direct(
    tmp_path: Path,
) -> None:
    """Explicit/implicit targets land in canonical direct or existing conversation."""
    connection, persistence = _build(tmp_path)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    owner = users.create_user(username="owner", display_name="Owner")
    source = users.create_user(username="agent:A", display_name="Agent A")
    target_agent = users.create_user(username="agent:B", display_name="Agent B")
    teammate = users.create_user(username="teammate", display_name="Teammate")
    group = conversations.create_conversation(
        title="group",
        participant_ids=[owner.id, source.id, target_agent.id, teammate.id],
        caller_owner_id=owner.owner_id,
    )

    agent = persistence.resolve_send_target(
        source_agent_id="A", target="agent:B", caller_owner_id=None
    )
    repeated = persistence.resolve_send_target(
        source_agent_id="A", target=target_agent.id, caller_owner_id=None
    )
    user = persistence.resolve_send_target(
        source_agent_id="A",
        target=f"user_id:{teammate.id}",
        caller_owner_id=owner.owner_id,
    )
    conversation = persistence.resolve_send_target(
        source_agent_id="A", target=group.id, caller_owner_id=None
    )

    assert agent.target.kind == "agent_id"
    assert agent.target.id == "B"
    assert repeated.conversation_id == agent.conversation_id
    assert user.target.kind == "user_id"
    assert (
        conversations.get_conversation(conversation_id=user.conversation_id).owner_id
        == owner.owner_id
    )
    assert conversation.target.kind == "conversation_id"
    assert conversation.conversation_id == group.id


def test_resolve_send_target_keeps_missing_agent_node_out_of_stable_result(
    tmp_path: Path,
) -> None:
    """An existing target resolves while volatile node state stays separately queried."""
    connection, persistence = _build(tmp_path)
    users = UserRepository(connection)
    users.create_user(username="agent:A", display_name="Agent A")
    users.create_user(username="agent:B", display_name="Agent B")

    result = persistence.resolve_send_target(
        source_agent_id="A", target="agent:B", caller_owner_id=None
    )

    assert result.target.kind == "agent_id"
    assert persistence.agent_node_id(agent_id="B") is None


def test_resolve_user_agent_conversation_preserves_human_creator(
    tmp_path: Path,
) -> None:
    """Heartbeat-style delivery keeps the owner user as direct-chat creator."""
    connection, persistence = _build(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="owner", display_name="Owner")
    users.create_user(username="agent:A", display_name="Agent A")

    conversation_id = persistence.resolve_user_agent_conversation(
        agent_id="A", user_id=owner.id, caller_owner_id=owner.owner_id
    )

    conversation = ConversationRepository(connection).get_conversation(
        conversation_id=conversation_id
    )
    assert conversation is not None
    assert conversation.creator_id == owner.id
    assert conversation.owner_id == owner.owner_id


@pytest.mark.parametrize("target", ["", "agent:", "missing-target"])
def test_resolve_send_target_rejects_invalid_or_unknown_target(
    tmp_path: Path, target: str
) -> None:
    """Malformed and unknown targets retain the existing ValueError boundary."""
    connection, persistence = _build(tmp_path)
    UserRepository(connection).create_user(username="agent:A", display_name="Agent A")

    with pytest.raises(ValueError):
        persistence.resolve_send_target(
            source_agent_id="A", target=target, caller_owner_id=None
        )


def test_group_reply_route_returns_stable_peer_identities(tmp_path: Path) -> None:
    """Group route returns peer identities while node availability stays volatile."""
    connection, persistence = _build(tmp_path)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    owner = users.create_user(username="owner", display_name="Owner")
    source = users.create_user(username="agent:A", display_name="Agent A")
    peer_b = users.create_user(username="agent:B", display_name="Agent B")
    peer_c = users.create_user(username="agent:C", display_name="Agent C")
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[owner.id, source.id, peer_c.id, peer_b.id],
        caller_owner_id=owner.owner_id,
    )
    _upsert_profile(connection, agent_id="A", owner_id=owner.owner_id, node_id="node-a")
    _upsert_profile(connection, agent_id="B", owner_id=owner.owner_id, node_id="node-b")
    _upsert_profile(connection, agent_id="C", owner_id=owner.owner_id, node_id=None)

    route = persistence.group_reply_route(
        conversation_id=conversation.id, source_agent_id="A"
    )

    assert route is not None
    assert route.sender_user_id == source.id
    assert route.sender_display_name == "Agent A"
    assert {target.agent_id for target in route.targets} == {"B", "C"}


def test_dispatch_record_is_first_write_wins(tmp_path: Path) -> None:
    """Repeated dispatch keys return the first durable delivery result."""
    _, persistence = _build(tmp_path)
    first = AgentDispatchRecord(
        dispatch_request_key="A:call-1",
        source_agent_id="A",
        target_kind="agent_id",
        target_id="B",
        conversation_id="conv-1",
        message_id="msg-1",
    )
    competing = AgentDispatchRecord(
        dispatch_request_key="A:call-1",
        source_agent_id="A",
        target_kind="user_id",
        target_id="user-2",
        conversation_id="conv-2",
        message_id="msg-2",
    )

    stored_first = persistence.record_dispatch(first)
    stored_again = persistence.record_dispatch(competing)

    assert stored_first == first
    assert stored_again == first
    assert persistence.find_dispatch(dispatch_request_key="A:call-1") == first


def test_system_user_and_usage_scope_are_persistence_owned(tmp_path: Path) -> None:
    """System identity and conversation owner lookup stay behind the module surface."""
    connection, persistence = _build(tmp_path)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    owner = users.create_user(username="owner", display_name="Owner")
    conversation = conversations.create_conversation(
        title="solo", participant_ids=[owner.id], caller_owner_id=owner.owner_id
    )

    first_system_id = persistence.system_user_id()
    second_system_id = persistence.system_user_id()

    assert first_system_id == second_system_id
    assert users.get_user_by_username(username="system").id == first_system_id
    assert (
        persistence.conversation_usage_scope(conversation_id=conversation.id)
        == owner.owner_id
    )
    assert persistence.conversation_usage_scope(conversation_id="missing") is None
