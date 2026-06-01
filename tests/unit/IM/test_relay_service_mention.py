"""Unit tests for bugfix-358: relay participants schema + mention tag parsing.

R1: participants payload 携带 agent_id / user_id 而非 synth user UUID。
R2: mention 解析只认 <mention type="agent" target_id="X"/> 标签；删除 display_name fallback。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


# ─── fixture builder ────────────────────────────────────────────────────────


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


# ─── R1: participants schema ─────────────────────────────────────────────────


class TestParticipantsSchema:
    """relay payload.participants 携带 agent_id / user_id, 不再有 id=<synth_uuid> 字段。"""

    def test_agent_participant_carries_agent_id_not_synth_uuid(
        self, tmp_path: Path
    ) -> None:
        """agent 参与者的字典必须包含 agent_id 字段，不能只有 id 字段（synth user UUID）。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content="hello",
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r1a",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        assert len(results) == 1
        participants = results[0].relay_task.payload["participants"]
        agent_entries = [p for p in participants if p.get("type") == "agent"]
        assert len(agent_entries) == 1, "agent participant missing"
        agent_p = agent_entries[0]

        # 必须有 agent_id 字段，值为真实 agent_id（不是 synth UUID）
        assert "agent_id" in agent_p, (
            f"participants agent entry missing agent_id field: {agent_p}"
        )
        assert agent_p["agent_id"] == "Arch", (
            f"agent_id should be 'Arch', got {agent_p}"
        )

        # 不应含 id 字段（旧的 synth user UUID 字段）
        assert "id" not in agent_p, (
            f"agent participant should not have old 'id' field: {agent_p}"
        )

    def test_user_participant_carries_user_id_not_id(self, tmp_path: Path) -> None:
        """user 参与者的字典必须包含 user_id 字段。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content="hello",
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r1b",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        assert len(results) == 1
        participants = results[0].relay_task.payload["participants"]
        user_entries = [p for p in participants if p.get("type") == "user"]
        assert len(user_entries) == 1, "user participant missing"
        user_p = user_entries[0]

        # 必须有 user_id 字段
        assert "user_id" in user_p, f"user participant missing user_id field: {user_p}"
        assert user_p["user_id"] == alice.id, (
            f"user_id should be alice's real UUID, got {user_p}"
        )

        # 不应含 id 字段
        assert "id" not in user_p, (
            f"user participant should not have old 'id' field: {user_p}"
        )

    def test_sender_info_agent_carries_agent_id(self, tmp_path: Path) -> None:
        """agent 发送者的 sender 字典应含 agent_id，不含 id=<synth_uuid>。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        # agent 作为发送者
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=arch_user.id,
            content="hello from agent",
        )

        result = relay_service.enqueue_message_relay(
            message=msg,
            target_node_id="n1",
            idempotency_key="key-r1c",
            sender_user_id=arch_user.id,
            conversation_type="group",
            _override_agent_id="Arch",
        )

        sender = result.relay_task.payload.get("sender")
        assert sender is not None, "relay payload missing sender"
        assert sender.get("type") == "agent"

        # agent sender 应携带 agent_id 字段
        assert "agent_id" in sender, f"agent sender missing agent_id: {sender}"
        assert sender["agent_id"] == "Arch"

        # 不应含旧 id 字段
        assert "id" not in sender, (
            f"agent sender should not have old 'id' field: {sender}"
        )


# ─── R2: mention tag parsing ─────────────────────────────────────────────────


class TestMentionTagParsing:
    """mention 解析只认 <mention type='agent' target_id='X'/> 标签，删除 display_name fallback。"""

    def test_mention_tag_agent_extracted(self, tmp_path: Path) -> None:
        """content 中合法 inline tag 被正确提取为 mentioned_agent_ids。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        # 使用 inline tag 格式
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content='<mention type="agent" target_id="Arch"/> 你怎么看？',
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r2a",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        assert len(results) == 1
        meta = results[0].relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == ["Arch"], (
            f"expected ['Arch'], got {meta['mentioned_agent_ids']}"
        )

    def test_at_display_name_no_longer_resolves(self, tmp_path: Path) -> None:
        """旧式 @display_name 文本不再被解析为 mention；mentioned_agent_ids 为空。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        # 旧式 @display_name 文本（display_name fallback 已删除，不应命中）
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content="@架构 你怎么看？",
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r2b",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        for result in results:
            meta = result.relay_task.payload["metadata"]
            assert meta["mentioned_agent_ids"] == [], (
                f"display_name @mention should not resolve: got {meta['mentioned_agent_ids']}"
            )

    def test_mention_tag_outside_participants_ignored(self, tmp_path: Path) -> None:
        """target_id 不在 participants 中的标签被过滤掉，不进 mentioned_agent_ids。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        profiles.upsert_profile(
            agent_id="Arch",
            owner_id=alice.owner_id,
            display_name="架构",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id],
        )
        # 提到一个不在这个会话里的 agent
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content='<mention type="agent" target_id="GhostAgent"/> 你好',
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r2c",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        for result in results:
            meta = result.relay_task.payload["metadata"]
            assert "GhostAgent" not in meta["mentioned_agent_ids"], (
                f"out-of-participants target_id should be filtered: {meta['mentioned_agent_ids']}"
            )

    def test_multiple_mention_tags_all_extracted(self, tmp_path: Path) -> None:
        """content 中多个 mention 标签全部提取。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        arch_user = users.create_user(username="agent:Arch", display_name="架构")
        archa_user = users.create_user(username="agent:ArchA", display_name="Q")
        for aid, aname in [("Arch", "架构"), ("ArchA", "Q")]:
            profiles.upsert_profile(
                agent_id=aid,
                owner_id=alice.owner_id,
                display_name=aname,
                description="",
                system_prompt="",
                skills=[],
                tool_allowlist=[],
                group_reply_policy="mention",
                default_model=None,
                workspace_root=None,
            )
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, arch_user.id, archa_user.id],
        )
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content='<mention type="agent" target_id="Arch"/> 和 <mention type="agent" target_id="ArchA"/> 请各自回答',
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r2d",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        for result in results:
            meta = result.relay_task.payload["metadata"]
            assert sorted(meta["mentioned_agent_ids"]) == ["Arch", "ArchA"], (
                f"expected both agents mentioned, got {meta['mentioned_agent_ids']}"
            )

    def test_duplicate_display_name_no_orphan_hijack(self, tmp_path: Path) -> None:
        """孤儿 agent display_name 与当前群 agent 重名时，inline tag 仍正确路由到目标 agent。"""
        relay_service, messages, conversations, users, profiles = _build_fixture(
            tmp_path
        )
        alice = users.create_user(username="alice", display_name="Alice")
        # 真实 agent
        real_user = users.create_user(username="agent:ArchA", display_name="Q")
        # 孤儿 agent (agent_id="Q" 与 display_name 相同，历史遗留)
        orphan_user = users.create_user(username="agent:Q", display_name="Q")
        profiles.upsert_profile(
            agent_id="ArchA",
            owner_id=alice.owner_id,
            display_name="Q",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        profiles.upsert_profile(
            agent_id="Q",
            owner_id=alice.owner_id,
            display_name="Q",
            description="orphan",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )
        # 孤儿不在这个会话里
        conv = conversations.create_conversation(
            title="group",
            participant_ids=[alice.id, real_user.id],
        )
        # 使用 inline tag（带正确的 target_id="ArchA"）
        msg = messages.create_message(
            conversation_id=conv.id,
            sender_user_id=alice.id,
            content='<mention type="agent" target_id="ArchA"/> 你说呢',
        )

        results = relay_service.enqueue_message_relay_all(
            message=msg,
            target_node_id="n1",
            idempotency_key_base="key-r2e",
            sender_user_id=alice.id,
            conversation_type="group",
        )

        assert len(results) == 1
        meta = results[0].relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == ["ArchA"], (
            f"should route to ArchA not orphan Q: {meta['mentioned_agent_ids']}"
        )
