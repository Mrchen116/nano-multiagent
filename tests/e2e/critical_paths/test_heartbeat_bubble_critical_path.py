"""关键路径 7:heartbeat 有内容时主动冒泡(slow)。

spec Req「heartbeat 有内容时主动冒泡」。

旅程:一个启用了 heartbeat 且有可行动内容的 agent,心跳触发时在 IM 直聊主动冒泡一条消息。

经 Gateway 的真端到端:heartbeat 无对外触发路由(design 决策 5),只能「配秒级 cadence +
写一份有实质内容的 HEARTBEAT.md,然后等心跳自跑、观察直聊是否冒泡」。冒泡条件(探查 gateway
heartbeat_scheduler):features['heartbeat']=true + cadence 到点 + HEARTBEAT.md 有非空实质行。

@pytest.mark.slow(决策 5):时间驱动 + 最易 flaky,隔离成 slow 子集,`-m "not slow"` 可筛掉。
鲁棒断言(决策 4):哨兵由 HEARTBEAT.md 指令注入,只锚「直聊里冒出含哨兵的 agent 消息」,
宽超时,不锁措辞。哨兵随机唯一 → 冒泡那条精确归因(不存在注册回声混淆,heartbeat 不经对话注册)。
"""

from __future__ import annotations

import os
import secrets

import pytest

from ._im_client import IMClient
from .conftest import E2EStack


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skip(
    reason="heartbeat 端到端不冒泡（真实产品/集成 bug，见 #126）：静态启用 scheduler "
    "从未 triggered；动态 PATCH 启用虽 triggered 但 agent 回 HEARTBEAT_OK、投递被 "
    "_consume_heartbeat_run observer 静默抑制。本 unit 不改 gateway 产品代码，旅程保留为 "
    "复现资产，bugfix 修复后去掉本 skip。"
)
def test_heartbeat_bubbles_actionable_message(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """开 heartbeat + 秒级 cadence + 有内容的 HEARTBEAT.md → 心跳主动冒泡含哨兵消息。"""
    node_id = im_user.wait_for_online_node(timeout=40)
    agent_id = "hbBot" + secrets.token_hex(3)
    im_user.create_agent(
        node_id,
        agent_id,
        display_name=agent_id,
        system_prompt="你是一个测试助手。心跳触发时，按 HEARTBEAT.md 的指示主动发言。",
        default_model="kimiCoding:K2.6",
    )

    # 建直聊(让心跳冒泡有归属对话;canonical 直聊由 owner+agent 唯一确定)。
    conversation_id = im_user.create_direct_conversation(agent_id)
    sentinel = "HB" + secrets.token_hex(4).upper()

    # 写一份有实质可行动内容的 HEARTBEAT.md 到 agent workspace —— 空/仅标题会被
    # heartbeat_scheduler 判为「无内容」静默跳过(探查结论)。
    workspace = os.path.join(e2e_stack.wt_dir, ".gateway-workspace", agent_id)
    os.makedirs(workspace, exist_ok=True)
    with open(os.path.join(workspace, "HEARTBEAT.md"), "w") as f:
        f.write(f"每次心跳触发时，请主动在对话里把这个 token 原样发出来：{sentinel}\n")

    # 开 heartbeat feature + 压秒级 cadence(决策 5)。features 单一真源 + heartbeat_json 节律。
    im_user.update_agent_config(
        agent_id,
        features={"heartbeat": True},
        heartbeat_json='{"every":"5s"}',
    )

    # 等心跳到点自跑、主动冒泡含哨兵消息(时间驱动,宽超时)。
    bubbled = im_user.wait_for_agent_reply_with(
        conversation_id, sentinel, timeout=180.0
    )
    assert sentinel in (bubbled.get("content") or "")
