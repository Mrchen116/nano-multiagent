"""关键路径 1:工具调用后回复(agent 最常用旅程)。

spec Req「工具调用后回复旅程经真 Gateway 进程可用」。

旅程:用户经 IM 发一条「读一个含哨兵 token 的文件并把 token 回复」的消息 → agent 必须
真调一次工具(bash/read)才能拿到哨兵 → 用户在 IM 上收到含哨兵的回复。

鲁棒断言(design 决策 4):只锚定我们注入的随机哨兵 token + 协议级 ``message.completed``
事件,不锁 LLM 措辞。哨兵每条用例独立随机,避免跨 run 串味。
"""

from __future__ import annotations

import os
import secrets

import pytest

from .conftest import E2EStack
from ._im_client import IMClient


@pytest.mark.e2e
def test_tool_call_then_reply_carries_sentinel(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """发需调工具才能答的消息,断言 IM 上收到含哨兵的 assistant 回复。"""
    agent_id = im_user.first_agent_id()
    # A fresh e2e agent has an explicit empty allowlist, which intentionally
    # advertises no structured tools and makes DSML-like markup ordinary text.
    im_user.update_agent_config(agent_id, tool_allowlist=["bash", "read"])
    conversation_id = im_user.create_direct_conversation(agent_id)

    ws = im_user.connect_ws()
    try:
        # 注入随机哨兵到一个文件,只有真读它才拿得到 → 强制走工具调用主循环。
        sentinel = "SENT" + secrets.token_hex(4).upper()
        # Keep the secret out of the path and prompt. Otherwise an unexecuted raw
        # tool-call markup that merely repeats its command can satisfy the assertion.
        sentinel_file = os.path.join(
            e2e_stack.wt_dir, f"tool-read-{secrets.token_hex(4)}.txt"
        )
        with open(sentinel_file, "w") as f:
            f.write(sentinel + "\n")

        im_user.send_message(
            conversation_id,
            f"用 bash 或 read 工具读取文件 {sentinel_file} 的内容，"
            f"然后把文件里的那个 token 原样回复给我。只回复 token 本身。",
        )

        # First terminal reply is the asserted user-visible result. Waiting only
        # for a token match masks malformed raw tool markup until the long timeout.
        frame = ws.wait_for_event(
            "message.completed",
            lambda f: f.conversation_id == conversation_id,
        )
        content = frame.data.get("content") or ""
        assert sentinel in content, f"reply missing sentinel: {content!r}"
        assert "<tool_calls" not in content
        # 非空 + 不含内部报错(spec Scenario)。
        assert content.strip()
        assert "Traceback" not in content
    finally:
        ws.close()
