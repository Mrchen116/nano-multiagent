"""关键路径:从某条 agent 回复 fork 出分支单聊，分支带记忆、原会话不变（feat-445）。

旅程:用户在与 agent 的单聊里立一个事实（暗号）→ agent 确认 → 用户在那条确认回复上 fork →
进入新分支单聊（同 agent）→ 在分支里基于历史追问暗号 → agent 答对（带着到 fork 点的记忆）→
原会话保持不变（两线独立）。

鲁棒断言:暗号由用户随机生成、只在 fork 点之前说过；只有「relay 落 kernel message_id →
IM 复制 0→M 展示历史 → gateway 按 kernel 锚点 fork → 新 session 绑定 → agent 真带记忆」整条
跨进程链路打通，分支 agent 才能在不重述的追问下答出暗号。走 REST 历史轮询（最稳）。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient


def _last_completed_agent_message(client: IMClient, conversation_id: str) -> dict:
    """Return the newest completed agent message that carries a kernel_message_id."""
    for msg in reversed(client.list_messages(conversation_id, limit=100)):
        sender = msg.get("sender") or {}
        if (
            sender.get("type") == "agent"
            and msg.get("delivery_status") == "completed"
            and msg.get("kernel_message_id")
        ):
            return msg
    raise AssertionError("no completed agent message with kernel_message_id found")


@pytest.mark.e2e
def test_fork_branch_carries_memory_and_leaves_source_intact(im_user: IMClient) -> None:
    agent_id = im_user.first_agent_id()
    source = im_user.create_direct_conversation(agent_id)

    codeword = "CODE" + secrets.token_hex(4).upper()
    im_user.send_message(
        source,
        f"Please remember this codeword and acknowledge in one short sentence: {codeword}.",
    )
    im_user.wait_for_agent_reply_with(source, codeword, timeout=120.0)
    fork_point = _last_completed_agent_message(im_user, source)

    # A later turn in the source — must NOT appear in the branch.
    later = "LATER" + secrets.token_hex(3).upper()
    im_user.send_message(
        source, f"Also remember this second token: {later}. Acknowledge."
    )
    im_user.wait_for_agent_reply_with(source, later, timeout=120.0)

    # Fork at the codeword reply.
    branch = im_user.fork_conversation(source, fork_point["id"])
    assert branch != source

    branch_contents = " ".join(
        (m.get("content") or "") for m in im_user.list_messages(branch, limit=100)
    )
    assert codeword in branch_contents, (
        "branch must carry history through the fork point"
    )
    assert later not in branch_contents, "branch must exclude post-fork-point messages"

    # The branch agent must REMEMBER the codeword (carried via the kernel fork).
    im_user.send_message(
        branch, "What was the codeword I told you earlier? Reply with just the word."
    )
    reply = im_user.wait_for_agent_reply_with(branch, codeword, timeout=120.0)
    assert codeword in (reply.get("content") or "")

    # Source conversation is unaffected (still has the later token; no branch follow-up).
    source_contents = " ".join(
        (m.get("content") or "") for m in im_user.list_messages(source, limit=100)
    )
    assert later in source_contents
    assert "What was the codeword" not in source_contents
