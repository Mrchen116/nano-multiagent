"""关键路径 5:/stop 中止正在执行的运行。

spec Req「/stop 中止正在执行的运行」。

旅程:用户先发一条会让 agent 跑一阵的消息(跑一个长 bash)制造一个**活跃 run** → 趁它还在
跑时发 ``/stop`` → 运行被中止,用户在 IM 上观察到一条「已停止」ack,且被中止的 run 不再
继续产出新内容。

鲁棒断言(design 决策 4):
- 正向锚:``/stop`` 的 ack 文案 ``已停止当前操作。`` 是 Gateway **硬编码固定串**(非 LLM
  生成,见 inbound_pipeline `_handle_stop_command`),可逐字断言;无活跃 run 时 ack 会是
  ``当前没有正在执行的操作。``——所以先确保 run 真的在跑(等到 run 启动信号)再发 /stop。
- 否定锚:发完 /stop 后,在有界窗口内不应再出现「被中止 run 的长任务完成哨兵」
  (assert_no_event 风格的消息历史否定断言)——run 真被中止则那个哨兵永远不会到。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient
from ._im_polling import assert_absent_within


@pytest.mark.e2e
def test_stop_aborts_active_run(im_user: IMClient) -> None:
    """制造活跃 run → /stop → 收到固定 ack 且被中止的任务不再产出其哨兵。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)

    # 这个哨兵只有在「长任务真跑完」时才会被 agent 回出——/stop 成功中止后它应当永不出现。
    never_sentinel = "STOP" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        # 1) 制造一个活跃 run:让 agent 先跑一个长 bash(sleep),跑完后才回 never_sentinel。
        im_user.send_message(
            conversation_id,
            "请用 bash 工具运行 `sleep 45`（前台、不要后台、不要设短 timeout），"
            f"完整等它跑完之后，再回复我这个 token：{never_sentinel}。",
        )

        # 2) 等 run 真正启动(出现 tool_call.upserted 即 agent 已进工具循环、run 活跃)。
        ws.wait_for_event("tool_call.upserted", timeout=60.0)

        # 3) 趁 run 还在 sleep 时发 /stop。
        im_user.send_message(conversation_id, "/stop")

        # 4) 正向:收到 Gateway 硬编码的停止 ack(固定文案,非 LLM 措辞)。
        ack = ws.wait_for_event(
            "message.completed",
            lambda f: "已停止当前操作。" in (f.data.get("content") or ""),
            timeout=60.0,
        )
        assert "已停止当前操作。" in (ack.data.get("content") or "")
    finally:
        ws.close()

    # 5) 否定:被中止的长任务的哨兵不应在随后窗口里出现(run 真停了 → never_sentinel 永不到)。
    def _has_never_sentinel(msgs: list[dict]) -> bool:
        return any(
            m.get("sender_type") == "agent"
            and never_sentinel in (m.get("content") or "")
            for m in msgs
        )

    assert_absent_within(
        lambda: im_user.list_messages(conversation_id),
        _has_never_sentinel,
        window=20.0,
        desc=f"aborted-run completion sentinel {never_sentinel!r} (/stop should block it)",
    )
