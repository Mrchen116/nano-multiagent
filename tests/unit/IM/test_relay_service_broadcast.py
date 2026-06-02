"""Unit tests for IM relay broadcast: group chat creates one relay per participant agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def _build_fixture(
    tmp_path: Path,
) -> tuple[
    RelayService,
    MessageRepository,
    ConversationRepository,
    UserRepository,
    AgentProfileRepository,
]:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    relay_service = RelayService(connection)
    profiles = AgentProfileRepository(connection)
    return relay_service, messages, conversations, users, profiles


def test_group_chat_creates_one_relay_per_participant_agent(tmp_path: Path) -> None:
    """群聊 enqueue_message_relay_all 为每个 participant agent 各创建一条独立 relay task。"""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    owner = alice
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=owner.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="You are agent-a.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    profiles.upsert_profile(
        agent_id="agent-b",
        owner_id=owner.owner_id,
        display_name="Agent B",
        description="profile b",
        system_prompt="You are agent-b.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    # bugfix-358: mention format is now inline tag
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-a"/> please respond',
    )

    results = relay_service.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="idem-group-1",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    # 一条 relay 对应一个 participant agent
    assert len(results) == 2
    agent_ids = {r.relay_task.payload["agent_id"] for r in results}
    assert agent_ids == {"agent-a", "agent-b"}
    # 每条 relay 均已创建（非幂等复用）
    assert all(r.created for r in results)


def test_direct_chat_creates_single_relay(tmp_path: Path) -> None:
    """直聊 enqueue_message_relay_all 返回单条 relay（保持原有行为）。"""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    owner = alice
    profiles.upsert_profile(
        agent_id="agent-a",
        owner_id=owner.owner_id,
        display_name="Agent A",
        description="profile a",
        system_prompt="You are agent-a.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    conversation = conversations.create_conversation(
        title="direct",
        participant_ids=[alice.id, agent_a_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello agent",
    )

    results = relay_service.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="idem-direct-1",
        sender_user_id=alice.id,
        conversation_type="direct",
    )

    assert len(results) == 1
    assert results[0].relay_task.payload["agent_id"] == "agent-a"
    assert results[0].created is True


def test_group_relay_each_carries_mentioned_agent_ids(tmp_path: Path) -> None:
    """群聊每条 relay 的 metadata.mentioned_agent_ids 包含消息中的 mention 列表（供 gateway 判断执行/缓存）。"""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    owner = alice
    for aid, aname in [("agent-a", "Agent A"), ("agent-b", "Agent B")]:
        profiles.upsert_profile(
            agent_id=aid,
            owner_id=owner.owner_id,
            display_name=aname,
            description=f"profile {aid}",
            system_prompt=f"You are {aid}.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    # bugfix-358: mention 改为 inline tag 格式，旧式 @agent-id 文本不再路由
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="agent-a"/> please respond',
    )

    results = relay_service.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="idem-mentioned",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    # 每条 relay 均携带相同的 mentioned_agent_ids
    for result in results:
        meta = result.relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == ["agent-a"], (
            f"relay for agent {result.relay_task.payload.get('agent_id')} missing mentioned_agent_ids"
        )
        assert meta["conversation_type"] == "group"


def test_group_relay_idempotency_is_per_agent(tmp_path: Path) -> None:
    """群聊中同一消息重复 enqueue 时，每个 agent 的 relay task 保持幂等（不重复创建）。"""
    relay_service, messages, conversations, users, profiles = _build_fixture(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent_a_user = users.create_user(username="agent:agent-a", display_name="Agent A")
    agent_b_user = users.create_user(username="agent:agent-b", display_name="Agent B")
    owner = alice
    for aid, aname in [("agent-a", "Agent A"), ("agent-b", "Agent B")]:
        profiles.upsert_profile(
            agent_id=aid,
            owner_id=owner.owner_id,
            display_name=aname,
            description=f"profile {aid}",
            system_prompt=f"You are {aid}.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )
    conversation = conversations.create_conversation(
        title="group",
        participant_ids=[alice.id, agent_a_user.id, agent_b_user.id],
    )
    message = messages.create_message(
        conversation_id=conversation.id,
        sender_user_id=alice.id,
        content="hello group",
    )

    first_results = relay_service.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="idem-idem-test",
        sender_user_id=alice.id,
        conversation_type="group",
    )
    second_results = relay_service.enqueue_message_relay_all(
        message=message,
        target_node_id="node-1",
        idempotency_key_base="idem-idem-test",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert len(first_results) == 2
    assert len(second_results) == 2
    # 第一次：全部新建
    assert all(r.created for r in first_results)
    # 第二次：全部复用（幂等）
    assert all(not r.created for r in second_results)
    # relay_task_id 一致
    first_ids = {r.relay_task.relay_task_id for r in first_results}
    second_ids = {r.relay_task.relay_task_id for r in second_results}
    assert first_ids == second_ids
