"""Integration test: group mention routing via HTTP IM API — bugfix-358.

Tests that:
1. `_resolve_all_participants` emits agent_id/user_id (not synth UUID) in relay payload
2. `_resolve_mentioned_agent_ids_from_tags` correctly parses <mention/> tags
3. display_name fallback branch is gone (old @display_name text does not route)
4. Same-name orphan agents cannot hijack routing when inline tags carry correct target_id

These tests operate at the RelayService API level (no HTTP server needed), which
gives us the full real-database integration without the 401-gating complexity of
the IM HTTP app routes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.repositories import AgentProfileRepository, ConversationRepository, MessageRepository, UserRepository


# ─── fixture ────────────────────────────────────────────────────────────────


def _setup(
    tmp_path: Path,
) -> tuple[RelayService, MessageRepository, ConversationRepository, UserRepository, AgentProfileRepository]:
    conn = connect(tmp_path / "im.db")
    initialize_schema(conn)
    return (
        RelayService(conn),
        MessageRepository(conn),
        ConversationRepository(conn),
        UserRepository(conn),
        AgentProfileRepository(conn),
    )


# ─── agent → agent mention routing ─────────────────────────────────────────

def test_agent_to_agent_mention_routing_with_inline_tag(tmp_path: Path) -> None:
    """Agent reply 含 <mention> 标签 → mentioned_agent_ids 正确包含目标 agent。

    复现 bugfix-358 incident: agent Arch 回复里 @ArchA 时，IM 必须正确解析 tag 并
    把 mentioned_agent_ids=['ArchA'] 送给 gateway，ArchA 才能被触发而非静默 buffer。
    """
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

    alice = users.create_user(username="alice", display_name="Alice")
    arch_user = users.create_user(username="agent:Arch", display_name="架构")
    archa_user = users.create_user(username="agent:ArchA", display_name="Q")

    for aid, disp in [("Arch", "架构"), ("ArchA", "Q")]:
        profiles.upsert_profile(
            agent_id=aid,
            owner_id=alice.owner_id,
            display_name=disp,
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )

    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, arch_user.id, archa_user.id],
    )

    # Agent Arch replies with inline tag mentioning ArchA
    agent_reply = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=arch_user.id,
        content='<mention type="agent" target_id="ArchA"/> 要不我们从认识论聊起？',
    )

    results = relay_svc.enqueue_message_relay_all(
        message=agent_reply,
        target_node_id="node-1",
        idempotency_key_base="incident-key",
        sender_user_id=arch_user.id,
        conversation_type="group",
    )

    for result in results:
        meta = result.relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == ["ArchA"], (
            f"agent→agent: ArchA must be in mentioned_agent_ids; got {meta['mentioned_agent_ids']}"
        )


def test_user_to_agent_mention_routing_with_inline_tag(tmp_path: Path) -> None:
    """User 通过 picker 发出 inline tag → mentioned_agent_ids 包含目标 agent。"""
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

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

    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, arch_user.id],
    )

    # Frontend picker produces inline tag; user sends it
    user_msg = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="Arch"/> 你好',
    )

    results = relay_svc.enqueue_message_relay_all(
        message=user_msg,
        target_node_id="node-1",
        idempotency_key_base="user-to-agent-key",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    for result in results:
        meta = result.relay_task.payload["metadata"]
        assert "Arch" in meta["mentioned_agent_ids"], (
            f"user→agent: Arch not in mentioned_agent_ids: {meta['mentioned_agent_ids']}"
        )


def test_agent_to_user_mention_routing_with_inline_tag(tmp_path: Path) -> None:
    """Agent reply 含 user mention tag → relay payload.participants 含 user_id。

    user mention tag 不进 mentioned_agent_ids（那是 agent list），但
    participants 字典里 user 条目携带 user_id 供前端渲染成 chip。
    """
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

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

    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, arch_user.id],
    )

    # Agent mentions user by user_id in inline tag
    agent_reply = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=arch_user.id,
        content=f'<mention type="user" target_id="{alice.id}"/> 我同意你说的',
    )

    results = relay_svc.enqueue_message_relay_all(
        message=agent_reply,
        target_node_id="node-1",
        idempotency_key_base="agent-to-user-key",
        sender_user_id=arch_user.id,
        conversation_type="group",
    )

    assert len(results) == 1  # Only one agent (Arch) in this group
    payload = results[0].relay_task.payload
    participants = payload["participants"]

    user_entries = [p for p in participants if p.get("type") == "user"]
    assert len(user_entries) == 1
    assert user_entries[0]["user_id"] == alice.id, (
        f"user participant must carry user_id, got {user_entries[0]}"
    )


def test_display_name_at_text_does_not_route(tmp_path: Path) -> None:
    """旧式 @display_name 文本不进 mentioned_agent_ids（display_name fallback 已删）。

    复现 bugfix-358 incident 根因：display_name fallback 导致孤儿 agent 截胡。
    修复后，@架构 这种文本不路由——only inline tags route。
    """
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

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

    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, arch_user.id],
    )

    old_style_msg = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=alice.id,
        content="@架构 你怎么看？",
    )

    results = relay_svc.enqueue_message_relay_all(
        message=old_style_msg,
        target_node_id="node-1",
        idempotency_key_base="old-style-key",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    for result in results:
        meta = result.relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == [], (
            f"@display_name text must not route; got {meta['mentioned_agent_ids']}"
        )


def test_orphan_agent_does_not_hijack_inline_tag_routing(tmp_path: Path) -> None:
    """孤儿 agent 与群成员同 display_name 时，inline tag 仍正确路由到目标 agent。

    复现 bugfix-358 incident 复现 B: 用户 @Q，IM 按 display_name fallback 命中孤儿 'Q'，
    真实 agent ArchA 被静默 buffer。inline tag 修复后：tag 携带 target_id='ArchA'，
    只认 agent_id 精确匹配，孤儿不截胡。
    """
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

    alice = users.create_user(username="alice", display_name="Alice")
    real_user = users.create_user(username="agent:ArchA", display_name="Q")
    # 孤儿 agent：agent_id='Q' 与 ArchA 的 display_name 一致
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

    # 孤儿不在这个 conversation
    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, real_user.id],
    )

    # 使用 inline tag，target_id=ArchA（正确）
    msg = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="ArchA"/> 你说呢',
    )

    results = relay_svc.enqueue_message_relay_all(
        message=msg,
        target_node_id="node-1",
        idempotency_key_base="orphan-test-key",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    assert len(results) == 1
    meta = results[0].relay_task.payload["metadata"]
    assert meta["mentioned_agent_ids"] == ["ArchA"], (
        f"orphan Q must not intercept ArchA routing; got {meta['mentioned_agent_ids']}"
    )
    # Confirm that 'Q' (orphan) is not in mentioned_agent_ids
    assert "Q" not in meta["mentioned_agent_ids"]


def test_same_name_agents_disambiguation_via_different_target_ids(tmp_path: Path) -> None:
    """两个 display_name 同为"助手"的 agent，通过不同 target_id 可独立路由。"""
    relay_svc, messages, convs, users, profiles = _setup(tmp_path)

    alice = users.create_user(username="alice", display_name="Alice")
    assistant1_user = users.create_user(username="agent:assistant-1", display_name="助手")
    assistant2_user = users.create_user(username="agent:assistant-2", display_name="助手")

    for aid in ["assistant-1", "assistant-2"]:
        profiles.upsert_profile(
            agent_id=aid,
            owner_id=alice.owner_id,
            display_name="助手",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="mention",
            default_model=None,
            workspace_root=None,
        )

    conv = convs.create_conversation(
        title="group",
        participant_ids=[alice.id, assistant1_user.id, assistant2_user.id],
    )

    # Mentioning only assistant-1
    msg = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=alice.id,
        content='<mention type="agent" target_id="assistant-1"/> 请你做X',
    )

    results = relay_svc.enqueue_message_relay_all(
        message=msg,
        target_node_id="node-1",
        idempotency_key_base="same-name-key",
        sender_user_id=alice.id,
        conversation_type="group",
    )

    for result in results:
        meta = result.relay_task.payload["metadata"]
        assert meta["mentioned_agent_ids"] == ["assistant-1"], (
            f"only assistant-1 should be mentioned; got {meta['mentioned_agent_ids']}"
        )
        assert "assistant-2" not in meta["mentioned_agent_ids"]
