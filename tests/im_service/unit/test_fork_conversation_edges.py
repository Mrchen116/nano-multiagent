"""feat-445-M2: fork edge-path regressions (round-1 fixes #3/#4/#5/#6/#8).

Long-conversation full read, orchestration reorder, recursive-fork uuid remap, protected
rollback, and preserved delivery_status. Shares the same in-memory repo harness as
test_fork_conversation.py (split out to keep each file under the 400-line cap).
"""

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


def _ok_fork(calls, id_map=None):
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
        return {
            "ok": True,
            "new_session_id": "ksess-new",
            "id_map": id_map or {},
        }

    return _req


# ---------------------------------------------------------------------------
# feat-445-M2 R2 (#3): 长对话(>200)fork 取全量历史，不被 list_messages 的 200 上限截断
# ---------------------------------------------------------------------------


def _seed_long(messages: MessageRepository, conv_id, human, agent_user, n_pairs: int):
    """Seed n_pairs (user, agent-with-kernel-id) message pairs. Returns the agent msgs."""
    agents = []
    for i in range(n_pairs):
        messages.create_message(
            conversation_id=conv_id,
            sender_user_id=human.id,
            content=f"u{i}",
            sender_type="user",
        )
        a = messages.create_message(
            conversation_id=conv_id,
            sender_user_id=agent_user.id,
            content=f"a{i}",
            sender_type="agent",
            kernel_message_id=f"kmsg-{i}",
            allow_empty=True,
        )
        agents.append(a)
    return agents


@pytest.mark.asyncio
async def test_fork_point_outside_last_200_is_found(tmp_path: Path) -> None:
    """fork 点在末 200 之外（早期 agent 回复）→ 不再报 400「消息不存在」，分支精确到该点。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    agents = _seed_long(messages, conv.id, human, agent_user, n_pairs=130)  # 260 msgs
    early = agents[1]  # index ~3 in timeline — far outside the last 200

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=early.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([]),
    )
    copied = messages.list_all_messages(conversation_id=new_conv.id)
    # branch = u0,a0,u1,a1 (start..early inclusive)
    assert [m.content for m in copied] == ["u0", "a0", "u1", "a1"]


@pytest.mark.asyncio
async def test_fork_at_end_of_long_conversation_copies_full_history(
    tmp_path: Path,
) -> None:
    """对话 >200 条、fork 末尾 → 分支复制起点→fork 点**全部**消息（展示=记忆，非只末 200）。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    agents = _seed_long(messages, conv.id, human, agent_user, n_pairs=130)  # 260 msgs
    last = agents[-1]

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=last.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([]),
    )
    copied = messages.list_all_messages(conversation_id=new_conv.id)
    # all 260 messages carried (not truncated to the last 200)
    assert len(copied) == 260
    assert copied[0].content == "u0"  # earliest message present
    assert copied[-1].content == "a129"


# ---------------------------------------------------------------------------
# feat-445-M2 R3 (#4/#5/#6/#8): 编排重排 + 递归映射 + 回滚健壮 + 保留状态
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_copies_display_history_only_after_binding(tmp_path: Path) -> None:
    """#4: 展示历史复制必须发生在 request_fork（绑定 kernel session）之后——绑定前新会话
    须为空，否则 RPC 窗口内用户点进半建会话发消息会被回滚 CASCADE 吞掉。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    observed = {}

    async def _req(
        *, agent_id, source_conversation_id, new_conversation_id, fork_message_id
    ):
        # At binding time the branch conversation must still be empty (copy comes later).
        observed["count_at_bind"] = len(
            messages.list_all_messages(conversation_id=new_conversation_id)
        )
        return {"ok": True, "new_session_id": "ksess-new", "id_map": {"kmsg-a1": "b1"}}

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a1.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_req,
    )
    assert observed["count_at_bind"] == 0, "branch must be empty until binding succeeds"
    # after success the history is copied
    assert [
        m.content for m in messages.list_all_messages(conversation_id=new_conv.id)
    ] == [
        "u1",
        "a1",
    ]


@pytest.mark.asyncio
async def test_fork_unmapped_kernel_id_becomes_none(tmp_path: Path) -> None:
    """#5: 复制行的源 kernel id 不在 map（如被 compact 掉的前界气泡）→ 分支行 kernel_message_id
    置 None（分支不可再 fork 它，诚实），而非保留指向源 JSONL 的失效 id。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    a1, a2 = _seed_history(messages, conv.id, human, agent_user)
    # fork at a2; map only covers a2 (a1 simulated as compacted-out of the as-of-M view)
    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=a2.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([], id_map={"kmsg-a2": "branch-a2"}),
    )
    copied = messages.list_all_messages(conversation_id=new_conv.id)
    by_content = {m.content: m for m in copied}
    assert by_content["a2"].kernel_message_id == "branch-a2"  # mapped
    assert by_content["a1"].kernel_message_id is None  # not in map → None


@pytest.mark.asyncio
async def test_fork_rollback_does_not_mask_original_error(tmp_path: Path) -> None:
    """#6: 回滚里 delete 自身抛错不得覆盖原 ForkDelegationError（否则路由 except 不命中 → 500）。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    a1, _ = _seed_history(messages, conv.id, human, agent_user)

    async def _fail(**_kw):
        return {"ok": False, "error": "kernel boom"}

    # Make rollback's delete raise — original ForkDelegationError must still surface.
    orig_delete = conversations.delete_conversation

    def _boom_delete(**kw):
        raise RuntimeError("delete failed")

    conversations.delete_conversation = _boom_delete  # type: ignore[method-assign]
    try:
        with pytest.raises(ForkDelegationError):
            await service.fork_conversation(
                source_conversation_id=conv.id,
                fork_message_id=a1.id,
                owner_id=human.owner_id,
                actor_user_id=human.id,
                check_agent_online=_online(None),
                request_fork=_fail,
            )
    finally:
        conversations.delete_conversation = orig_delete  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_fork_rolls_back_on_cancelled_error(tmp_path: Path) -> None:
    """#6: request_fork 被取消(CancelledError，BaseException)也要回滚，不留幽灵会话。"""
    import asyncio

    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    a1, _ = _seed_history(messages, conv.id, human, agent_user)
    before = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))

    async def _cancel(**_kw):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await service.fork_conversation(
            source_conversation_id=conv.id,
            fork_message_id=a1.id,
            owner_id=human.owner_id,
            actor_user_id=human.id,
            check_agent_online=_online(None),
            request_fork=_cancel,
        )
    after = len(conversations.list_conversations_for_owner(owner_id=human.owner_id))
    assert after == before, "cancelled fork must roll back the empty conversation"


@pytest.mark.asyncio
async def test_fork_preserves_failed_delivery_status(tmp_path: Path) -> None:
    """#8: 复制的气泡保留源 delivery_status（failed 不被改写成 completed）。"""
    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="u1",
        sender_type="user",
    )
    failed = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="boom",
        sender_type="agent",
        kernel_message_id="kmsg-failed",
        allow_empty=True,
    )
    messages.update_runtime_state(message_id=failed.id, delivery_status="failed")
    fork_at = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="ok-reply",
        sender_type="agent",
        kernel_message_id="kmsg-ok",
        allow_empty=True,
    )

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=fork_at.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork(
            [], id_map={"kmsg-failed": "b-failed", "kmsg-ok": "b-ok"}
        ),
    )
    copied = messages.list_all_messages(conversation_id=new_conv.id)
    by_content = {m.content: m for m in copied}
    assert by_content["boom"].delivery_status == "failed", (
        "failed bubble must stay failed"
    )
    assert by_content["ok-reply"].delivery_status == "completed"


@pytest.mark.asyncio
async def test_fork_copies_tool_calls_and_thinking(tmp_path: Path) -> None:
    # feat-445-M2 W1: fork 复制保留完整气泡形态（tool_calls + thinking），非只纯文本。
    from IM.domain.models import ToolCall

    service, conversations, messages, human, agent_user, conv = _setup(tmp_path)
    messages.create_message(
        conversation_id=conv.id,
        sender_user_id=human.id,
        content="q",
        sender_type="user",
    )
    rich = messages.create_message(
        conversation_id=conv.id,
        sender_user_id=agent_user.id,
        content="answer with a tool",
        sender_type="agent",
        kernel_message_id="kmsg-rich",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="bash",
                status="completed",
                input={"cmd": "ls"},
                output="a\nb",
            )
        ],
        allow_empty=True,
    )
    messages.append_thinking_segment(
        message_id=rich.id, text="let me think step by step"
    )

    new_conv = await service.fork_conversation(
        source_conversation_id=conv.id,
        fork_message_id=rich.id,
        owner_id=human.owner_id,
        actor_user_id=human.id,
        check_agent_online=_online(None),
        request_fork=_ok_fork([], id_map={"kmsg-rich": "branch-rich"}),
    )
    copied = messages.list_all_messages(conversation_id=new_conv.id)
    branch_agent = next(m for m in copied if m.content == "answer with a tool")
    assert branch_agent.tool_calls is not None
    assert [tc.name for tc in branch_agent.tool_calls] == ["bash"]
    assert branch_agent.tool_calls[0].output == "a\nb"
    assert branch_agent.thinking is not None
    assert [s.text for s in branch_agent.thinking] == ["let me think step by step"]
