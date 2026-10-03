"""feat-445-M3: round-2 code-review cleanups on the M2 fork diff.

清理-1 复制 failed 气泡时 message.delivered SSE 事件的 delivery_status（不再硬编码 completed）；
清理-2 copy loop 在 binding 成功后失败也回滚（不留 IM 半建 / 标孤儿 session）；
清理-3 _rollback_fork 捕 BaseException（与外层对称，不静默漏告警）；
清理-4 gateway 漏返回 id_map 时降级有 warning。
"""

from pathlib import Path

import pytest

from IM.application.web_im_service import ForkDelegationError, WebIMService
from IM.domain.models import ConversationEvent
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserRepository


def _setup(tmp_path: Path, *, capture_events: bool = False):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    captured: list[ConversationEvent] = []
    notify = captured.append if capture_events else None
    messages = MessageRepository(connection, notify)
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
    return service, conversations, messages, human, agent_user, conv, captured


def _online():
    async def _c(_agent_id):
        return True

    return _c


def _ok_fork(id_map=None):
    async def _req(
        *, agent_id, source_conversation_id, new_conversation_id, fork_message_id
    ):
        return {
            "ok": True,
            "new_session_id": "ksess-new",
            "id_map": id_map or {},
        }

    return _req


# ── 清理-1: message.delivered 事件 delivery_status 不硬编码 completed ──────────


def test_create_message_delivered_event_reflects_failed_status(tmp_path: Path) -> None:
    """复制 failed 气泡时，message.delivered SSE 事件的 delivery_status 必须是 failed（与 DB 行一致），
    否则订阅者瞬时看到 completed、刷新才翻回 failed。"""
    _, _, messages, human, agent_user, conv, captured = _setup(
        tmp_path, capture_events=True
    )
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="boom",
        sender_type="agent",
        delivery_status="failed",
        auto_complete_delivery=True,
        allow_empty=True,
    )
    delivered = [e for e in captured if e.event_type == "message.delivered"]
    assert delivered, "expected a message.delivered event"
    assert delivered[-1].delivery_status == "failed"


# ── 清理-2: copy loop 在 binding 后失败也回滚 ─────────────────────────────────


@pytest.mark.asyncio
async def test_copy_failure_after_binding_rolls_back(tmp_path: Path) -> None:
    service, conversations, messages, human, agent_user, conv, _ = _setup(tmp_path)
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="u1",
        sender_type="user",
    )
    a1 = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="a1",
        sender_type="agent",
        kernel_message_id="kmsg-a1",
        allow_empty=True,
    )
    before = len(conversations.list_conversations_for_member(user_id=human.id))

    # Make the copy step (create_message into the branch) fail after binding succeeded.
    orig_create = messages.create_message

    def _boom_create(**kw):
        if kw.get("conversation_id") != conv.id:  # only fail copies into the new branch
            raise RuntimeError("sqlite write failed mid-copy")
        return orig_create(**kw)

    messages.create_message = _boom_create  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError):
            await service.fork_conversation(
                source_conversation_id=conv.id,
                fork_message_id=a1.id,
                owner_id=human.owner_id,
                actor_user_id=human.id,
                check_agent_online=_online(),
                request_fork=_ok_fork({"kmsg-a1": "b1"}),
            )
    finally:
        messages.create_message = orig_create  # type: ignore[method-assign]
    after = len(conversations.list_conversations_for_member(user_id=human.id))
    assert after == before, "copy failure after binding must roll back the branch conv"


# ── 清理-3: _rollback_fork 捕 BaseException（不被 delete 的 BaseException 掩盖原错）──


@pytest.mark.asyncio
async def test_rollback_swallows_base_exception_from_delete(tmp_path: Path) -> None:
    service, conversations, messages, human, agent_user, conv, _ = _setup(tmp_path)
    a1 = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="a1",
        sender_type="agent",
        kernel_message_id="kmsg-a1",
        allow_empty=True,
    )

    async def _fail(**_kw):
        return {"ok": False, "error": "kernel boom"}

    class _Boom(BaseException):
        pass

    def _boom_delete(**_kw):
        raise _Boom("delete blew up with a BaseException")

    conversations.delete_conversation = _boom_delete  # type: ignore[method-assign]
    # The original ForkDelegationError must surface, not the delete's BaseException.
    with pytest.raises(ForkDelegationError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(),
            request_fork=_fail,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_revoked_wait_only_removes_its_empty_fork_scaffold(tmp_path, outcome):
    """Revocation rejects resumed work; exception cleanup still owns admission."""
    import asyncio
    from fastapi import HTTPException
    from IM.infra.company_gate import company_lease, await_outside_gate

    service, conversations, messages, human, agent_user, conv, _ = _setup(tmp_path)
    message = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="original",
        sender_type="agent",
        kernel_message_id="kernel-original",
        allow_empty=True,
    )
    gate = asyncio.Lock()
    waiting = asyncio.Event()
    result = asyncio.get_running_loop().create_future()
    revoked = False
    branch = []

    async def revalidate():
        if revoked:
            raise HTTPException(status_code=401, detail="session revoked")

    async def request(**kwargs):
        branch.append(kwargs["new_conversation_id"])
        waiting.set()
        return await await_outside_gate(result)

    original_delete = conversations.delete_conversation

    def delete_under_admission(**kwargs):
        assert gate.locked()
        return original_delete(**kwargs)

    conversations.delete_conversation = delete_under_admission

    async def fork():
        async with company_lease(gate, revalidate):
            return await service.fork_conversation(
                source_conversation_id=conv.id,
                fork_message_id=message.id,
                owner_id=human.owner_id,
                actor_user_id=human.id,
                check_agent_online=_online(),
                request_fork=request,
            )

    task = asyncio.create_task(fork())
    await asyncio.wait_for(waiting.wait(), 1)
    async with gate:
        revoked = True
        if outcome == "cancel":
            task.cancel()
        elif outcome == "error":
            result.set_exception(RuntimeError("gateway failed"))
        else:
            result.set_result(
                {"ok": True, "new_session_id": "remote-already-created", "id_map": {}}
            )
    with pytest.raises(HTTPException) as error:
        await asyncio.wait_for(task, 1)
    assert error.value.status_code == 401
    assert not gate.locked()
    remaining = conversations.list_conversations_for_member(user_id=human.id)
    assert [item.id for item in remaining] == [conv.id]
    assert messages.list_messages(conversation_id=conv.id)[0].content == "original"
    assert branch and branch[0] != conv.id
