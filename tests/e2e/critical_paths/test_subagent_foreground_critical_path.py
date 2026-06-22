"""关键路径 4:前台子 agent 可用,产出回带。

spec Req「前台子 agent 可用且失败被隔离」。

旅程(#117 的直接守护场景):用户的请求促使 agent 派一个**前台子 agent** 去干活,子 agent
把哨兵 token 产出,父 agent 在回复里把它带回来。这正是 #117(子 agent 跨事件循环崩溃)曾经
完全不可用、却无任何 e2e 拦住的那条路径——经真 Gateway 进程跑一遍,跨事件循环的崩裂当场暴露。

鲁棒断言(design 决策 4):只锚定哨兵 + 协议级 ``message.completed``。哨兵要求由子 agent
回出、父 agent 带回,确保确实走了「派子 agent → 收子 agent 产出 → 综合回复」这条链路,
而非父 agent 自己直接答(子 agent 真崩的话父 agent 拿不到哨兵,断言即红)。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient


@pytest.mark.e2e
def test_foreground_subagent_carries_back_output(im_user: IMClient) -> None:
    """派前台子 agent,父 agent 回复带回子 agent 产出的哨兵。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)

    ws = im_user.connect_ws()
    try:
        sentinel = "SUB" + secrets.token_hex(4).upper()
        # 显式要求派一个子 agent,并让子 agent 回出哨兵——强制走子 agent 链路而非父直接答。
        im_user.send_message(
            conversation_id,
            "请用 agent 工具派一个前台子 agent 去完成这件小事："
            f"让那个子 agent 把这个 token 原样返回：{sentinel}。"
            "等子 agent 完成后，把它返回的 token 原样转达给我。",
        )

        frame = ws.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        content = frame.data.get("content") or ""
        assert sentinel in content, f"subagent output not carried back: {content!r}"
        assert "Traceback" not in content
    finally:
        ws.close()
