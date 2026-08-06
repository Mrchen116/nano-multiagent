"""feat-445-M1 R4: WebIMService.fork_conversation 编排 — 建会话 + 复制 0→fork 点展示历史
+ agent 在线校验 + gateway RPC 委托 + 失败原子回滚 + 旧气泡(无 kernel message_id)拒 fork。"""

from pathlib import Path

import pytest

from IM.domain.models import SystemNotice
from IM.application.web_im_service import (
    AgentOfflineError,
    ForkDelegationError,
    ForkNotFoundError,
    ForkValidationError,
    WebIMService,
)
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.config_boundaries import AgentConfigBoundaryRepository
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserRepository


def _setup(tmp_path: Path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    boundaries = AgentConfigBoundaryRepository(connection)
    service = WebIMService(
        conversations=conversations, messages=messages, boundaries=boundaries
    )

    human = users.create_user(username="alice", display_name="Alice")
    agent_user = users.create_user(username="agent:planner", display_name="Planner")
    connection.execute(
        "UPDATE users SET owner_id = ? WHERE id = ?", (human.owner_id, agent_user.id)
    )
    connection.commit()
    conv = conversations.create_conversation(
        title="Planner",
        participant_ids=[f"user:{human.id}", "agent:planner"],
        caller_owner_id=human.owner_id,
    )
    return service, conversations, messages, boundaries, human, agent_user, conv


def _seed_history(messages: MessageRepository, conv_id, human, agent_user):
    """u1 → a1(completed, kernel id) → u2 → a2(completed, kernel id) → trailing later msg."""
    messages.create_message(
        conversation_id=conv_id,
        sender_user_id=human.id,
        content="u1",
        sender_type="user",
    )
    a1 = messages.create_message(
        conversation_id=conv_id,
        sender_user_id=agent_user.id,
        content="a1",
        sender_type="agent",
        kernel_message_id="kmsg-a1",
        allow_empty=True,
    )
    messages.create_message(
        conversation_id=conv_id,
        sender_user_id=human.id,
        content="u2",
        sender_type="user",
    )
    a2 = messages.create_message(
        conversation_id=conv_id,
        sender_user_id=agent_user.id,
        content="a2",
        sender_type="agent",
        kernel_message_id="kmsg-a2",
        allow_empty=True,
    )
    return a1, a2


def _online(_agent_id):
    async def _check(agent_id):
        return True

    return _check


def _offline():
    async def _check(agent_id):
        return False

    return _check


def _ok_fork(calls, id_map=None):
    async def _req(
        *,
        agent_id,
        source_conversation_id,
        new_conversation_id,
        fork_message_id,
        source_external_source=None,
        source_external_chat_id=None,
    ):
        call = {
            "agent_id": agent_id,
            "source_conversation_id": source_conversation_id,
            "new_conversation_id": new_conversation_id,
            "fork_message_id": fork_message_id,
        }
        if source_external_source is not None:
            call["source_external_source"] = source_external_source
        if source_external_chat_id is not None:
            call["source_external_chat_id"] = source_external_chat_id
        calls.append(call)
        return {
            "ok": True,
            "new_session_id": "ksess-new",
            "id_map": id_map or {},
        }

    return _req


@pytest.mark.asyncio
async def test_fork_copies_history_through_M_and_delegates(tmp_path: Path) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    a1, a2 = _seed_history(messages, conv.id, human, agent_user)
    calls: list[dict] = []

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a1.id,  # fork at the FIRST agent reply
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        # #5: gateway returns the source→branch kernel-uuid map; the copied bubble's
        # kernel_message_id must be REWRITTEN to the branch uuid (not kept as the source).
        request_fork=_ok_fork(calls, id_map={"kmsg-a1": "branch-kmsg-a1"}),
    )

    # new conversation is a direct user-agent chat titled with the agent name
    assert new_conv.id != conv.id
    assert new_conv.title == "Planner"
    assert new_conv.direct_kind == "user-agent"

    # copied display history = start..a1 (inclusive); a1 之后 (u2/a2) NOT copied
    copied = messages.list_messages(conversation_id=new_conv.id, limit=100)
    assert [m.content for m in copied] == ["u1", "a1"]
    # #5: branch row carries the MAPPED branch kernel id (== branch JSONL uuid), so a
    # recursive fork from this copied bubble resolves in the branch session (no 502).
    assert copied[-1].kernel_message_id == "branch-kmsg-a1"

    # gateway delegation carries the KERNEL message id (= JSONL turn uuid), not the IM
    # row id — the kernel forks its session by the kernel anchor (live e2e caught this).
    assert calls == [
        {
            "agent_id": "planner",
            "source_conversation_id": conv.id,
            "new_conversation_id": new_conv.id,
            "fork_message_id": "kmsg-a1",
        }
    ]

    # source conversation unchanged
    assert [
        m.content for m in messages.list_messages(conversation_id=conv.id, limit=100)
    ] == [
        "u1",
        "a1",
        "u2",
        "a2",
    ]


@pytest.mark.asyncio
async def test_fork_copy_timestamps_preserve_source_order_at_browser_precision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rapid mixed-message copies remain ordered after browser millisecond parsing."""
    service, _conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    system = UserRepository(messages._connection).create_user(
        username="system", display_name="System"
    )
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="u1",
        sender_type="user",
    )
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="a1",
        sender_type="agent",
        kernel_message_id="kmsg-a1",
        allow_empty=True,
    )
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=system.id,
        content="notice",
        sender_type="system",
        system_notice=SystemNotice(
            kind="self_evolution_review",
            source_agent_id="planner",
            source_agent_display_name="Planner",
            updated_targets=("memory",),
        ),
    )
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="u2",
        sender_type="user",
    )
    anchor = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="a2",
        sender_type="agent",
        kernel_message_id="kmsg-a2",
        allow_empty=True,
    )
    monkeypatch.setattr(
        "IM.infra.repositories.messages.utc_now",
        lambda: "2026-08-06T10:48:20.132110Z",
    )

    branch = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=anchor.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork(
            [],
            id_map={"kmsg-a1": "branch-a1", "kmsg-a2": "branch-a2"},
        ),
    )

    copied = messages.list_messages(conversation_id=branch.id, limit=100)
    browser_milliseconds = [item.created_at[:23] for item in copied]
    assert [item.content for item in copied] == ["u1", "a1", "notice", "u2", "a2"]
    assert browser_milliseconds == sorted(browser_milliseconds)
    assert len(set(browser_milliseconds)) == len(copied)


@pytest.mark.asyncio
async def test_fork_copies_existing_boundary_with_mapped_anchor(tmp_path: Path) -> None:
    """Forks preserve only source boundaries whose anchors are copied."""
    service, _conversations, messages, boundaries, human, _agent_user, conv = _setup(
        tmp_path
    )
    a1, a2 = _seed_history(messages, conv.id, human, _agent_user)
    messages_in_source = messages.list_messages(conversation_id=conv.id, limit=100)
    first_user = messages_in_source[0]
    profiles = AgentProfileRepository(_conversations._connection)
    profiles.upsert_profile(
        agent_id="planner",
        owner_id=human.owner_id,
        node_id="node-1",
        display_name="Planner",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    boundaries.record_from_gateway(
        boundary_id="before-a1",
        node_id="node-1",
        owner_id=human.owner_id,
        conversation_id=conv.id,
        agent_id="planner",
        before_message_id=a1.id,
        runtime_fingerprint="runtime-a",
        fingerprint_schema="v1",
        profile_version=1,
        applied_at="2026-07-21T00:00:00Z",
    )
    boundaries.record_from_gateway(
        boundary_id="after-fork-point",
        node_id="node-1",
        owner_id=human.owner_id,
        conversation_id=conv.id,
        agent_id="planner",
        before_message_id=a2.id,
        runtime_fingerprint="runtime-b",
        fingerprint_schema="v1",
        profile_version=2,
        applied_at="2026-07-21T00:01:00Z",
    )

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a1.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([], id_map={"kmsg-a1": "branch-kmsg-a1"}),
    )

    copied_messages = messages.list_messages(conversation_id=new_conv.id, limit=100)
    copied_by_content = {message.content: message.id for message in copied_messages}
    copied_boundaries = boundaries.list_all(conversation_id=new_conv.id)
    assert [
        (item.before_message_id, item.runtime_fingerprint) for item in copied_boundaries
    ] == [(copied_by_content["a1"], "runtime-a")]
    assert first_user.id != copied_by_content["u1"]


@pytest.mark.asyncio
async def test_fork_external_shadow_conversation_forwards_external_identity(
    tmp_path: Path,
) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    conversations._connection.execute(
        """
        UPDATE conversations
        SET external_source = ?, external_chat_id = ?
        WHERE id = ?
        """,
        ("feishu", "oc_group", conv.id),
    )
    conversations._connection.commit()
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    calls: list[dict] = []

    await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a1.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork(calls, id_map={"kmsg-a1": "branch-kmsg-a1"}),
    )

    assert calls == [
        {
            "agent_id": "planner",
            "source_conversation_id": conv.id,
            "new_conversation_id": calls[0]["new_conversation_id"],
            "fork_message_id": "kmsg-a1",
            "source_external_source": "feishu",
            "source_external_chat_id": "oc_group",
        }
    ]


@pytest.mark.asyncio
async def test_fork_offline_agent_rejected_no_conversation_created(
    tmp_path: Path,
) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    before = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))

    with pytest.raises(AgentOfflineError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_offline(),
            request_fork=_ok_fork([]),
        )
    after = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))
    assert after == before, "offline fork must not create a conversation"


@pytest.mark.asyncio
async def test_fork_rpc_failure_rolls_back_new_conversation(tmp_path: Path) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    before = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))

    async def _fail_fork(**_kw):
        return {"ok": False, "error": "kernel boom"}

    with pytest.raises(ForkDelegationError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_fail_fork,
        )
    after = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))
    assert after == before, "failed fork must roll back the created conversation"


@pytest.mark.asyncio
async def test_fork_timeout_none_result_rolls_back(tmp_path: Path) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    before = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))

    async def _timeout_fork(**_kw):
        return None  # gateway not connected / timed out

    with pytest.raises(ForkDelegationError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_timeout_fork,
        )
    after = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))
    assert after == before


@pytest.mark.asyncio
async def test_fork_old_bubble_without_kernel_message_id_rejected(
    tmp_path: Path,
) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    # An agent message WITHOUT kernel_message_id (pre-feature bubble)
    old = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="legacy",
        sender_type="agent",
        allow_empty=True,
    )
    with pytest.raises(ForkValidationError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=old.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_ok_fork([]),
        )


@pytest.mark.asyncio
async def test_fork_user_message_rejected(tmp_path: Path) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    u = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="u1",
        sender_type="user",
    )
    with pytest.raises(ForkValidationError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=u.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_ok_fork([]),
        )


@pytest.mark.asyncio
async def test_fork_cross_tenant_not_found(tmp_path: Path) -> None:
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    with pytest.raises(ForkNotFoundError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id="someone-else-owner",
            actor_user_id="someone-else",
            check_agent_online=_online(None),
            request_fork=_ok_fork([]),
        )


@pytest.mark.asyncio
async def test_fork_group_conversation_rejected(tmp_path: Path) -> None:
    """群聊源 → 400（fork 只在 user↔单 agent 直聊可用；后端独立校验，不依赖前端隐藏入口）。"""
    service, conversations, messages, _boundaries, human, agent_user, conv = _setup(
        tmp_path
    )
    # second agent → a 3-participant group (direct_kind != "user-agent")
    from IM.infra.repositories.users import UserRepository

    users = UserRepository(conversations._connection)  # type: ignore[attr-defined]
    agent2 = users.create_user(username="agent:builder", display_name="Builder")
    conversations._connection.execute(
        "UPDATE users SET owner_id = ? WHERE id = ?", (human.owner_id, agent2.id)
    )
    conversations._connection.commit()
    group = conversations.create_conversation(
        title="Group",
        participant_ids=[f"user:{human.id}", "agent:planner", "agent:builder"],
        caller_owner_id=human.owner_id,
    )
    a1 = messages.create_message(
        conversation_id=group.id,
        sender_user_id=agent_user.id,
        content="hi from group",
        sender_type="agent",
        kernel_message_id="kmsg-g",
        allow_empty=True,
    )
    with pytest.raises(ForkValidationError):
        await service.fork_conversation(
            source_conversation_id=group.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_ok_fork([]),
        )
