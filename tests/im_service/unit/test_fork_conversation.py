"""feat-445-M1 R4: WebIMService.fork_conversation 编排 — 建会话 + 复制 0→fork 点展示历史
+ agent 在线校验 + gateway RPC 委托 + 失败原子回滚 + 旧气泡(无 kernel message_id)拒 fork。"""

from pathlib import Path

import pytest

from IM.application.web_im_service import (
    AgentOfflineError,
    ForkDelegationError,
    ForkNotFoundError,
    ForkValidationError,
    WebIMService,
)
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def _setup(tmp_path: Path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    service = WebIMService(conversations=conversations, messages=messages)

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
    return service, conversations, messages, human, agent_user, conv


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


def _ok_fork(calls):
    async def _req(
        *, agent_id, source_conversation_id, new_conversation_id, fork_message_id
    ):
        calls.append(
            {
                "agent_id": agent_id,
                "source_conversation_id": source_conversation_id,
                "new_conversation_id": new_conversation_id,
                "fork_message_id": fork_message_id,
            }
        )
        return {"ok": True, "new_session_id": "ksess-new"}

    return _req


@pytest.mark.asyncio
async def test_fork_copies_history_through_M_and_delegates(tmp_path: Path) -> None:
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    a1, a2 = _seed_history(messages, conv.id, human, agent_user)
    calls: list[dict] = []

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a1.id,  # fork at the FIRST agent reply
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork(calls),
    )

    # new conversation is a direct user-agent chat titled with the agent name
    assert new_conv.id != conv.id
    assert new_conv.title == "Planner"
    assert new_conv.direct_kind == "user-agent"

    # copied display history = start..a1 (inclusive); a1 之后 (u2/a2) NOT copied
    copied = messages.list_messages(conversation_id=new_conv.id, limit=100)
    assert [m.content for m in copied] == ["u1", "a1"]
    assert copied[-1].kernel_message_id == "kmsg-a1"

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
async def test_fork_offline_agent_rejected_no_conversation_created(
    tmp_path: Path,
) -> None:
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
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
