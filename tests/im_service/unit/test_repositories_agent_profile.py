"""Unit tests for agent profile repository: roundtrip, optimistic lock, alias snapshot."""

from pathlib import Path

import pytest

from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    AgentProfileRepository,
    AgentProfileVersionConflictError,
    BindRepository,
    ConversationRepository,
    MessageRepository,
    NodeRepository,
    UserRepository,
)


def _build_repositories(
    tmp_path: Path,
) -> tuple[
    UserRepository,
    ConversationRepository,
    MessageRepository,
    AgentProfileRepository,
    NodeRepository,
    BindRepository,
]:
    """Build repository instances bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        UserRepository(connection),
        ConversationRepository(connection),
        MessageRepository(connection),
        AgentProfileRepository(connection),
        NodeRepository(connection),
        BindRepository(connection),
    )


def test_agent_profile_roundtrip_and_optimistic_lock(tmp_path: Path) -> None:
    """Persist profiles and reject stale profile_version updates."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_user = users.create_user(username="agent-1", display_name="Alpha")
    seeded = profiles.upsert_profile(
        agent_id=agent_user.id,
        owner_id=owner.owner_id,
        display_name="Alpha",
        description="initial",
        system_prompt="You are Alpha.",
        skills=["plan"],
        tool_allowlist=["read"],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    created_conversation = conversations.create_conversation(
        title="alpha thread",
        participant_ids=[owner.id, seeded.agent_id],
    )
    assert created_conversation.config_profile_version == 1

    updated = profiles.update_profile(
        agent_id=agent_user.id,
        profile_version=1,
        display_name="Alpha v2",
        description="updated",
        system_prompt="You are Alpha v2.",
        skills=["plan", "review"],
        tool_allowlist=["read", "edit"],
        group_reply_policy="auto",
        default_model="claude-sonnet-4",
        workspace_root="/srv/agents/alpha",
    )
    assert updated.profile_version == 2
    assert updated.group_reply_policy == "auto"
    assert updated.workspace_root == "/srv/agents/alpha"

    with pytest.raises(AgentProfileVersionConflictError):
        profiles.update_profile(
            agent_id=agent_user.id,
            profile_version=1,
            display_name="stale",
            description="stale",
            system_prompt="stale",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )


def test_direct_conversation_with_agent_alias_freezes_prompt_snapshot(tmp_path: Path) -> None:
    """Freeze agent snapshot metadata when direct chats target an alias user like `agent:<id>`."""
    users, conversations, _, profiles, _, _ = _build_repositories(tmp_path)
    owner = users.create_user(username="owner", display_name="Owner")
    agent_alias = users.create_user(username="agent:agent-1", display_name="Alpha Alias")
    profiles.upsert_profile(
        agent_id="agent-1",
        owner_id=owner.owner_id,
        display_name="Alpha",
        description="initial",
        system_prompt="You are Alpha.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )

    created = conversations.create_conversation(
        title="alias direct",
        participant_ids=[owner.id, agent_alias.id],
    )
    stored = conversations.get_conversation(conversation_id=created.id)
    snapshot_row = conversations._connection.execute(
        "SELECT config_agent_id, config_profile_version, config_system_prompt FROM conversations WHERE id = ?",
        (created.id,),
    ).fetchone()

    assert created.type == "direct"
    assert created.config_profile_version == 1
    assert stored is not None
    assert stored.config_profile_version == 1
    assert snapshot_row is not None
    assert snapshot_row["config_agent_id"] == "agent-1"
    assert snapshot_row["config_profile_version"] == 1
    assert snapshot_row["config_system_prompt"] == "You are Alpha."
