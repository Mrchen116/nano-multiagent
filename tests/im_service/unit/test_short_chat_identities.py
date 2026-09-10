"""Verify stable short identities, collision handling and authorized member lookup."""

import re
from types import SimpleNamespace

import pytest

from IM.application.work_conversations import WorkConversationQuery
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserAlreadyExistsError, UserRepository


def test_short_ids_retry_only_primary_key_collisions(tmp_path, monkeypatch):
    db = connect(tmp_path / "ids.db")
    initialize_schema(db)
    users = UserRepository(db)
    first = users.create_user(username="first", display_name="First")
    assert re.fullmatch(r"u_[a-z0-9]{8}", first.id)
    ids = iter([first.id, "u_second00", "u_third000"])
    monkeypatch.setattr("IM.infra.repositories.users.new_chat_id", lambda _: next(ids))
    second = users.create_user(username="second", display_name="Second")
    assert second.id == "u_second00"
    with pytest.raises(UserAlreadyExistsError):
        users.create_user(username="second", display_name="Duplicate")
    conversations = ConversationRepository(db)
    room = conversations.create_conversation(
        title="First", participant_ids=[first.id, second.id]
    )
    assert re.fullmatch(r"c_[a-z0-9]{8}", room.id)
    ids = iter([room.id, "c_second00"])
    monkeypatch.setattr(
        "IM.infra.repositories.conversations.new_chat_id", lambda _: next(ids)
    )
    other = conversations.create_conversation(
        title="Second", participant_ids=[first.id, second.id]
    )
    assert other.id == "c_second00"
    assert other.participant_ids == room.participant_ids
    assert not db.execute("PRAGMA foreign_key_check").fetchall()


def test_info_includes_silent_members_and_external_history_never_impersonates_owner(
    tmp_path,
):
    db = connect(tmp_path / "query.db")
    initialize_schema(db)
    users = UserRepository(db)
    owner = users.create_user(username="owner", display_name="Owner")
    agent = users.create_user(username="agent:worker", display_name="Worker")
    silent = users.create_user(username="silent", display_name="Silent")
    AgentProfileRepository(db).create_profile(
        agent_id="worker",
        owner_id=owner.id,
        node_id=None,
        display_name="Worker",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
        work_mode="global",
    )
    query = WorkConversationQuery(
        db,
        SimpleNamespace(session=lambda *_: {"node_id": None, "scope": "global_main"}),
    )
    scope = dict(node_id=None, agent_id="worker", session_id="main")
    conversations = ConversationRepository(db)
    room = conversations.create_conversation(
        title="Team", participant_ids=[owner.id, agent.id, silent.id]
    )
    second = conversations.create_conversation(
        title="Other team", participant_ids=[owner.id, agent.id]
    )
    members = query.query(**scope, action="info", target=room.id)["members"]
    assert {p["user_id"] for p in members} == {owner.id, agent.id, silent.id}
    assert next(p for p in members if p["user_id"] == agent.id) == {
        "user_id": agent.id,
        "name": "Worker",
        "type": "agent",
        "mention": f'<mention type="user" target_id="{agent.id}"/>',
    }
    assert agent.id in {
        p["user_id"]
        for p in query.query(**scope, action="info", target=second.id)["members"]
    }
    denied = conversations.create_conversation(
        title="Private", participant_ids=[owner.id, silent.id]
    )
    with pytest.raises(ValueError, match="target_not_accessible"):
        query.query(**scope, action="info", target=denied.id)
    with db:
        db.execute(
            "UPDATE conversations SET external_source='feishu' WHERE id=?", (room.id,)
        )
    messages = MessageRepository(db)
    old = messages.create_message(
        conversation_id=room.id,
        sender_user_id=owner.id,
        sender_display_name="External Alice",
        content="Old external message",
    )
    new = messages.create_message(
        conversation_id=room.id,
        sender_user_id=owner.id,
        sender_display_name="External Bob",
        sender_source_id="ou_bob",
        content="New external message",
    )
    history = query.query(**scope, action="read", target=room.id)
    from personal_assistant.tools.conversations import ConversationsTool
    import json

    model = json.loads(ConversationsTool().serialize_result(history))
    senders = {m["id"]: m["sender"] for m in model["messages"]}
    assert senders[old.id] == {
        "name": "External Alice",
        "type": "external",
        "channel": "feishu",
    }
    assert senders[new.id] == {
        "name": "External Bob",
        "type": "external",
        "channel": "feishu",
        "source_id": "ou_bob",
    }
