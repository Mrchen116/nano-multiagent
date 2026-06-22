"""关键路径 11:经 IM 创建 agent 并落地可聊。

spec Req「经 IM 创建的 agent 落地后可聊」。

旅程:已有一个在线节点 → 用户经 IM 配置中心(``POST /nodes/{node_id}/agents``)新建一个
agent → 它在节点落地 workspace 并上线(出现在 ``GET /agents`` 列表) → 用户给它建直聊、
发消息,收到回复。

鲁棒断言(design 决策 4):新 agent 带一个随机后缀的 agent_id(避免跨 run 撞);落地以「它
出现在 IM agent 列表」为准;可聊以「直聊里收到一条含哨兵的 agent 回复」为准。哨兵注入进
prompt 让 agent 原样回出,只锚哨兵 + 协议级 ``message.completed``,不锁 LLM 措辞。
"""

from __future__ import annotations

import secrets
import time

import pytest

from ._im_client import IMClient
from .conftest import E2EStack


def _wait_for_agent_listed(im_user: IMClient, agent_id: str, *, timeout: float) -> None:
    """轮询 ``GET /agents`` 直到新建的 agent_id 出现(落地上线信号)。"""
    deadline = time.monotonic() + timeout
    last: list[str] = []
    while time.monotonic() < deadline:
        last = [a["agent_id"] for a in im_user.list_agents()]
        if agent_id in last:
            return
        time.sleep(1.0)
    raise AssertionError(
        f"created agent {agent_id!r} never appeared in IM agent list within "
        f"{timeout}s; last list: {last}"
    )


@pytest.mark.e2e
def test_agent_created_via_im_lands_and_replies(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """经 IM 建 agent → 落地上线 → 建直聊发消息收到含哨兵回复。"""
    node_id = im_user.wait_for_online_node(timeout=40)

    new_agent_id = "e2eNew" + secrets.token_hex(3)
    im_user.create_agent(
        node_id,
        new_agent_id,
        display_name=f"E2E New {new_agent_id}",
        system_prompt="你是一个测试助手。用户让你原样回复某个 token 时，只回复那个 token 本身。",
        default_model="kimiCoding:K2.6",
    )

    # 落地上线信号:新 agent 出现在 IM agent 列表。
    _wait_for_agent_listed(im_user, new_agent_id, timeout=40)

    conversation_id = im_user.create_direct_conversation(new_agent_id)
    sentinel = "NEW" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        im_user.send_message(
            conversation_id,
            f"请把这个 token 原样回复给我，只回 token 本身：{sentinel}",
        )
        frame = ws.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        assert sentinel in (frame.data.get("content") or "")
    finally:
        ws.close()
