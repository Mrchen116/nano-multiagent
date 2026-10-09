"""关键路径 2:bash 前台超时不卡死会话。

spec Req「bash 前台超时不卡死会话」。

旅程:短 timeout 的长命令按原生 bash 策略转后台或超时收口，主会话仍可回复。

鲁棒断言(design 决策 4):只锚定我们注入的随机哨兵 + 协议级 ``message.completed`` 事件。
不锁 LLM 措辞,也不断言工具内部状态(那是实现细节);只验「会话没卡死、用户最终收到回复」
这条用户可观察契约——超时如果把 session 卡死,这条 message.completed 永远不会到,测试超时即红。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient


@pytest.mark.e2e
def test_foreground_bash_timeout_still_replies(im_user: IMClient) -> None:
    """前台 bash 超时后 session 不卡死,用户最终仍收到含哨兵的回复。"""
    agent_id = im_user.first_agent_id()
    im_user.update_agent_config(
        agent_id, tool_allowlist=["bash", "job_output", "job_kill"]
    )
    conversation_id = im_user.create_direct_conversation(agent_id)

    ws = im_user.connect_ws()
    try:
        sentinel = "TMO" + secrets.token_hex(4).upper()
        im_user.send_message(
            conversation_id,
            "请用 bash 工具运行 `sleep 30`，并且给这次 bash 调用设置 timeout 参数为 3 秒。"
            "它一定会超时——这正是我要观察的。无论这条命令超时与否，"
            f"请在最后务必回复我这个 token：{sentinel}",
        )

        frame = ws.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        content = frame.data.get("content") or ""
        assert sentinel in content, f"reply missing sentinel after timeout: {content!r}"
        assert content.strip()
        assert "Traceback" not in content
    finally:
        ws.close()
