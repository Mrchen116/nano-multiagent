"""关键路径 10:进程重启后会话续接。

spec Req「进程重启后会话上下文不丢」。

旅程:用户发消息让 agent 记住一个随机哨兵 token 并收到确认 → **重启 Gateway 进程**
(复用同 config 同 node_id / workspace) → 再发一条「复述刚才那个 token」的消息 →
agent 的回复仍带回重启前记住的哨兵。

鲁棒断言(design 决策 4):哨兵是上下文里唯一确定锚——agent 只有真从重启前的会话历史
里取到它才答得出,纯文本续接(非工具)即可验「上下文不丢」这条接缝。
"""

from __future__ import annotations

import secrets

import pytest

from .conftest import E2EStack
from ._im_client import IMClient, restart_gateway


@pytest.mark.e2e
def test_context_survives_gateway_restart(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """建上下文 → 重启 Gateway → agent 仍记得重启前的哨兵 token。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)

    # 阶段 1:让 agent 记住一个随机哨兵,等到一条确认回复(只断「有回复」,不锁措辞)。
    sentinel = "MEMO" + secrets.token_hex(4).upper()
    ws = im_user.connect_ws()
    try:
        im_user.send_message(
            conversation_id,
            f"请记住这个暗号:{sentinel}。稍后我会让你复述它。先回复确认你记住了。",
        )
        ws.wait_for_event("message.completed")
    finally:
        ws.close()

    # 阶段 2:重启 Gateway 进程(同 config → node_id / workspace / 会话历史不变)。
    restart_gateway(e2e_stack.wt_dir, e2e_stack.im_port)
    # 重启后等节点重新上线再发后续消息。
    im_user.wait_for_online_node(timeout=40)

    # 阶段 3:重连 WS,让 agent 复述哨兵,断言回复仍含它 → 上下文确实续接。
    ws2 = im_user.connect_ws()
    try:
        im_user.send_message(
            conversation_id,
            "我刚才让你记住的那个暗号是什么?请原样复述它。",
        )
        frame = ws2.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        assert sentinel in (frame.data.get("content") or ""), (
            f"agent forgot context across restart; reply: {frame.data.get('content')!r}"
        )
    finally:
        ws2.close()
