"""关键路径 8:群聊里人与 agent 的定向 @ 双向可用。

spec Req「群聊里人与 agent 的定向 @ 双向可用」。两个 Scenario：

1. **人 @agent 再 agent @agent**:群里有用户 + A + B,用户 `@A 请 @B 让他做 X`(全程不直接
   @B) → 用户先看到 A 应答**且 A 的消息里带 `<mention type="agent" target_id="B"/>` 标签**
   (人→agent 唤醒) → 再看到 B 因被 A 点名而应答(agent→agent 唤醒)。这是多 agent 协作闭环。
2. **未被点名不抢话**:同群,用户只 @A → 只有 A 应答,B 在有界窗口内不发言(MENTION gate)。

鲁棒断言(design 决策 4):
- 群聊 @ **只认 XML 标签**(relay_service 正则),断言 A 消息含 `<mention type="agent"
  target_id="B"/>` 用正则匹配标签本身,不锁 A 的自然语言措辞。
- 发送者区分走 IM REST 历史的 ``sender.id``(== agent_id)——``message.completed`` WS 帧
  不带 sender,REST item 的 ``sender`` ActorPayload 才是黑盒区分 A/B 的稳锚。
- B 被唤醒以「历史里出现 B 发的含哨兵消息」为锚;哨兵透传确认链路真打通。
- 否定断言(B 不抢话)走「有界窗口内历史里 B 不发言」(REST 轮询窗口)。

两个 agent 由测试自建(owner 归属正确、system_prompt 明确群聊协作行为),比依赖现有 agent
配置更可控。group_reply_policy 用默认 MENTION(只有被 @ 的 agent 才应答)。
"""

from __future__ import annotations

import re
import secrets
import time

import pytest

from ._im_client import IMClient


def _make_group_agent(im_user: IMClient, node_id: str, agent_id: str) -> None:
    """建一个 MENTION-policy 群聊 agent,system_prompt 明确「被 @ 才答 + 如何 @ 别人」。"""
    im_user.create_agent(
        node_id,
        agent_id,
        display_name=agent_id,
        system_prompt=(
            "你在一个群聊里。规则：只有当有人在群里 @ 你时你才回应；没 @ 你时保持沉默。"
            "需要在群里点名另一个 agent 时，直接在回复中写 "
            '<mention type="agent" target_id="对方的agent_id"/> 标签来 @ 他。'
        ),
        group_reply_policy="MENTION",
        default_model="kimiCoding:K2.6",
    )


def _wait_listed(im_user: IMClient, agent_id: str, *, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if agent_id in [a["agent_id"] for a in im_user.list_agents()]:
            return
        time.sleep(1.0)
    raise AssertionError(f"agent {agent_id!r} not listed within {timeout}s")


def _agent_messages(im_user: IMClient, conv_id: str, agent_id: str) -> list[dict]:
    """该会话里由 ``agent_id`` 发出的消息(按 REST 历史 sender.id 区分)。"""
    out = []
    for msg in im_user.list_messages(conv_id):
        sender = msg.get("sender") or {}
        if sender.get("type") == "agent" and sender.get("id") == agent_id:
            out.append(msg)
    return out


def _wait_agent_message(
    im_user: IMClient,
    conv_id: str,
    agent_id: str,
    predicate,
    *,
    timeout: float = 90.0,
) -> dict:
    """轮询历史直到 ``agent_id`` 发出一条满足 ``predicate`` 的消息。"""
    deadline = time.monotonic() + timeout
    last: list[dict] = []
    while time.monotonic() < deadline:
        last = _agent_messages(im_user, conv_id, agent_id)
        for msg in last:
            if predicate(msg.get("content") or ""):
                return msg
        time.sleep(1.5)
    raise AssertionError(
        f"agent {agent_id!r} produced no matching message within {timeout}s; "
        f"its messages: {[m.get('content', '')[:60] for m in last]}"
    )


@pytest.mark.e2e
def test_human_mentions_a_then_a_mentions_b(im_user: IMClient) -> None:
    """用户 @A 让 A 去 @B：A 应答且消息含 B 的 mention 标签，B 因被点名而应答。"""
    node_id = im_user.wait_for_online_node(timeout=40)
    suffix = secrets.token_hex(3)
    agent_a = "grpA" + suffix
    agent_b = "grpB" + suffix
    _make_group_agent(im_user, node_id, agent_a)
    _make_group_agent(im_user, node_id, agent_b)
    _wait_listed(im_user, agent_a)
    _wait_listed(im_user, agent_b)

    conversation_id = im_user.create_group_conversation([agent_a, agent_b])
    sentinel = "GRP" + secrets.token_hex(4).upper()

    # 用户只 @A,要求 A 去 @B 让 B 回出哨兵——用户全程不直接 @B。
    im_user.send_message(
        conversation_id,
        f"请你在群里 @ {agent_b}（用 mention 标签），"
        f"让他把这个 token 原样发到群里：{sentinel}。",
        mentions=[agent_a],
    )

    # A 应答,且其消息里带 B 的 mention 标签(只认 XML 标签,正则匹配标签本身)。
    b_tag_re = re.compile(
        rf'<mention\s+type="agent"\s+target_id="{re.escape(agent_b)}"\s*/>',
        re.IGNORECASE,
    )
    _wait_agent_message(
        im_user, conversation_id, agent_a, lambda c: bool(b_tag_re.search(c))
    )

    # B 因被 A 点名而应答(agent→agent 唤醒),回出哨兵。
    _wait_agent_message(
        im_user, conversation_id, agent_b, lambda c: sentinel in c, timeout=120.0
    )


@pytest.mark.e2e
def test_unmentioned_agent_stays_silent(im_user: IMClient) -> None:
    """只 @A 时 B 不抢话：有界窗口内历史里 B 不发言。"""
    node_id = im_user.wait_for_online_node(timeout=40)
    suffix = secrets.token_hex(3)
    agent_a = "soloA" + suffix
    agent_b = "soloB" + suffix
    _make_group_agent(im_user, node_id, agent_a)
    _make_group_agent(im_user, node_id, agent_b)
    _wait_listed(im_user, agent_a)
    _wait_listed(im_user, agent_b)

    conversation_id = im_user.create_group_conversation([agent_a, agent_b])
    sentinel = "SOLO" + secrets.token_hex(4).upper()

    # 只 @A,且要求 A 不 @ 任何人 → B 不该被唤醒。
    im_user.send_message(
        conversation_id,
        f"请把这个 token 原样发到群里：{sentinel}。不要 @ 任何其他人。",
        mentions=[agent_a],
    )

    # 正向:A 确实应答了(确保群本身在工作,排除「整群都没动」假阴性)。
    _wait_agent_message(
        im_user, conversation_id, agent_a, lambda c: sentinel in c
    )

    # 否定:再等一个足够宽的窗口,B 始终不该发出任何消息(未被点名 → MENTION gate 拦住)。
    deadline = time.monotonic() + 25.0
    while time.monotonic() < deadline:
        b_msgs = _agent_messages(im_user, conversation_id, agent_b)
        if b_msgs:
            pytest.fail(
                f"unmentioned agent B spoke: {[m.get('content', '')[:60] for m in b_msgs]}"
            )
        time.sleep(2.5)
