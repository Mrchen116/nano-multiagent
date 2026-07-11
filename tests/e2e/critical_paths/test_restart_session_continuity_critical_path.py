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
def test_restart_readiness_rejects_pre_restart_online_snapshot(monkeypatch) -> None:
    """A durable old online row must not satisfy replacement-Gateway readiness."""
    client = IMClient("http://unused")
    snapshots = iter(
        [
            [
                {
                    "node_id": "node-1",
                    "status": "online",
                    "last_heartbeat_at": "2026-07-11T11:00:00Z",
                }
            ],
            [
                {
                    "node_id": "node-1",
                    "status": "offline",
                    "last_heartbeat_at": "2026-07-11T11:00:00Z",
                }
            ],
            [
                {
                    "node_id": "node-1",
                    "status": "online",
                    "last_heartbeat_at": "2026-07-11T11:00:01Z",
                }
            ],
        ]
    )
    monkeypatch.setattr(client, "list_nodes", lambda: next(snapshots))

    reconnected = client.wait_for_node_reconnect(
        node_id="node-1",
        previous_last_heartbeat_at="2026-07-11T11:00:00Z",
        timeout=2.0,
    )

    assert reconnected["last_heartbeat_at"] == "2026-07-11T11:00:01Z"
    client.close()


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
    before_restart = next(
        node
        for node in im_user.list_nodes()
        if node.get("node_id") == e2e_stack.node_id
    )
    previous_last_heartbeat_at = before_restart.get("last_heartbeat_at")
    assert isinstance(previous_last_heartbeat_at, str) and previous_last_heartbeat_at
    restart_gateway(e2e_stack.wt_dir, e2e_stack.im_port)
    # 仅有 durable online 不足以证明 replacement WS 已注册；必须观察到
    # 同 node 的 heartbeat generation 严格前进后才发后续消息。
    im_user.wait_for_node_reconnect(
        node_id=e2e_stack.node_id,
        previous_last_heartbeat_at=previous_last_heartbeat_at,
        timeout=40,
    )

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
