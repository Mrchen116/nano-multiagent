"""关键路径 6:cron 定时任务自动推送(slow)。

spec Req「cron 定时任务自动推送」。

旅程:agent 配一个即将触发的 cron 任务 → 到达触发时刻 → 用户在 IM 直聊收到该 cron 任务
自动推送的一条消息。

经 Gateway 的真端到端:cron 没有对外触发路由(design 决策 5),只能「让 agent 经 cron 工具
注册一个秒级周期任务,然后等它自跑、观察 IM 直聊是否收到推送」。cron 工具仅在
``features['cron_scheduling']`` 开启时对 agent 可用 → 测试自建一个开了该 feature 的 agent。

@pytest.mark.slow(决策 5):时间驱动 + 最易 flaky,隔离成 slow 子集,`-m "not slow"` 可筛掉。
鲁棒断言(决策 4):
- 哨兵 + 宽超时,只锚「直聊里冒出含哨兵的 agent 消息」,不锁措辞、不锁次数。
- **排除注册确认的混淆**:注册 cron 时 agent 的确认回复可能也复述哨兵 → 先记下注册阶段
  已出现的含哨兵消息 id,只认一条**新的、id 不在已见集合**的含哨兵 agent 消息(= cron 真触发
  自跑推送的那条),而非注册回声。
"""

from __future__ import annotations

import secrets
import time

import pytest

from ._im_client import IMClient


def _agent_msg_ids_with(im_user: IMClient, conv_id: str, sentinel: str) -> set[str]:
    return {
        m["id"]
        for m in im_user.list_messages(conv_id)
        if m.get("sender_type") == "agent" and sentinel in (m.get("content") or "")
    }


@pytest.mark.e2e
@pytest.mark.slow
def test_cron_job_auto_pushes_message(im_user: IMClient) -> None:
    """开了 cron feature 的 agent 注册秒级 cron → 到点自动推一条含哨兵消息到直聊。"""
    node_id = im_user.wait_for_online_node(timeout=40)
    agent_id = "cronBot" + secrets.token_hex(3)
    im_user.create_agent(
        node_id,
        agent_id,
        display_name=agent_id,
        system_prompt="你是一个测试助手，会用 cron 工具按用户要求注册定时任务。",
        default_model="kimiCoding:K2.6",
    )
    # cron 工具仅在 features['cron_scheduling'] 开启时注册进 agent 工具集(product.py)。
    im_user.update_agent_config(agent_id, features={"cron_scheduling": True})

    # 等 feature 同步到 gateway 后 agent 重新就绪。
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if agent_id in [a["agent_id"] for a in im_user.list_agents()]:
            break
        time.sleep(1.0)

    conversation_id = im_user.create_direct_conversation(agent_id)
    sentinel = "CRON" + secrets.token_hex(4).upper()

    im_user.send_message(
        conversation_id,
        "请用 cron 工具注册一个定时任务："
        "schedule 用 every 模式、间隔 5 秒（everyMs 设为 5000），"
        f"任务内容（payload 的 message）是把这个 token 原样发出来：{sentinel}。"
        "注册好后先回我一句确认。",
    )

    # 等注册完成(注册确认回复可能含哨兵 → 记为「已见」基线,后续只认更新的那条)。
    registration = im_user.wait_for_agent_reply_with(
        conversation_id, sentinel, timeout=90.0
    )
    seen_before = _agent_msg_ids_with(im_user, conversation_id, sentinel)
    seen_before.add(registration["id"])

    # 等 cron 到点自跑、推一条**新的**含哨兵消息(id 不在注册阶段已见集合)。
    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        now = _agent_msg_ids_with(im_user, conversation_id, sentinel)
        if now - seen_before:
            return
        time.sleep(3.0)
    raise AssertionError(
        f"cron job did not auto-push a new message with sentinel {sentinel!r} "
        "within 180s after registration"
    )
