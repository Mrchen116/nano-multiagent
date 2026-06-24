"""关键路径 3:bash 后台任务完成后送达跟进通知。

spec Req「bash 后台任务完成后送达跟进通知」。

旅程:用户让 agent 把一条耗时 bash 丢到**后台**(``run_in_background``)并立即先回一句确认 →
后台作业跑完后,agent 在**同一对话**里**再**收到一条跟进消息,带回作业产出的哨兵。

鲁棒断言(design 决策 4):哨兵由后台命令自己 ``echo`` 产出,只有作业真跑完、通知真回流、
agent 真把结果作为第二条消息推回 IM,用户才看得到它。断言走 REST 历史轮询
(``wait_for_agent_reply_with``)——后台通知的最终态在消息历史里最稳(M1 client 注释已说明)。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient


@pytest.mark.e2e
def test_background_bash_completion_sends_followup(im_user: IMClient) -> None:
    """后台 bash 完成后,用户在同一对话再收到一条带哨兵的跟进消息。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)

    sentinel = "BGN" + secrets.token_hex(4).upper()
    # 哨兵由后台命令本身打印:只有「丢后台 → 跑完 → 通知回流 → agent 再发一条」整条链路
    # 真打通,用户历史里才会出现含哨兵的第二条消息。给个几秒 sleep 制造真实的「耗时」。
    im_user.send_message(
        conversation_id,
        "请用 bash 工具在**后台**运行这条命令（设置 run_in_background 为 true）："
        f"`sleep 3 && echo {sentinel}`。"
        "丢到后台后先回我一句确认。等这个后台作业完成、你收到它的结果后，"
        f"再发一条消息把命令输出里的那个 token（{sentinel}）原样告诉我。",
    )

    # 跟进消息在后台作业完成后才到,给宽超时;只认含哨兵的 agent 消息(即跟进那条)。
    followup = im_user.wait_for_agent_reply_with(
        conversation_id, sentinel, timeout=120.0
    )
    assert sentinel in (followup.get("content") or "")
    assert "Traceback" not in (followup.get("content") or "")
