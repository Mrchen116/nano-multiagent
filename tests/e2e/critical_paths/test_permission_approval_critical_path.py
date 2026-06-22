"""关键路径 9:工具权限审批人在回路可用(approve / deny 双向)。

spec Req「工具权限审批人在回路可用」。两个 Scenario：

1. **批准后运行继续**:agent 要调一个需许可的工具,用户在 IM 收到 ``permission.request`` →
   批准(``allow_once``) → 工具执行 → 用户最终收到带结果的回复。
2. **拒绝后工具不执行**:同样的需许可工具 → 收到 ``permission.request`` → 拒绝(``deny``) →
   该工具不执行,run 据此收口,用户可观察到被拒绝的结果。

鲁棒断言(design 决策 4):
- 触发审批用「需 review 的 bash 命令」(``bash -c "echo <哨兵>"``——``bash`` 执行任意脚本
  不在白名单 → review → classifier 走 ask),哨兵**由命令自己产出**:只有工具真执行,
  stdout 才含哨兵 → agent 才转达得出。approve → 哨兵出现;deny → 工具没跑,哨兵永不出现。
- 正向锚:``permission.request`` / ``permission.resolved`` 协议事件 + 哨兵透传。
- deny 的否定锚:有界窗口内不出现含哨兵的 agent 回复(工具没执行 → 命令输出的哨兵不存在)。
"""

from __future__ import annotations

import secrets
import time

import pytest

from ._im_client import IMClient


def _trigger_permission(im_user: IMClient, conv_id: str, sentinel: str) -> None:
    """发一条迫使 agent 调需许可 bash(命令产出哨兵)的消息。"""
    im_user.send_message(
        conv_id,
        f'请用 bash 工具运行这条命令：`bash -c "echo {sentinel}"`。'
        "运行成功后，把命令打印出来的那个 token 原样回复给我。",
    )


def _wait_permission_request(ws, *, timeout: float = 90.0):
    """等一帧 permission.request,返回 (conversation_id, message_id, request_id)。"""
    frame = ws.wait_for_event("permission.request", timeout=timeout)
    pr = frame.data.get("permission_request") or {}
    request_id = pr.get("request_id")
    message_id = frame.data.get("message_id")
    conversation_id = frame.conversation_id or frame.data.get("conversation_id")
    assert request_id and message_id and conversation_id, (
        f"permission.request missing ids: {frame.data!r}"
    )
    return conversation_id, message_id, request_id


@pytest.mark.e2e
def test_permission_approve_lets_run_continue(im_user: IMClient) -> None:
    """批准需许可工具 → 工具执行 → 用户收到含哨兵的结果。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)
    sentinel = "PERMOK" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        _trigger_permission(im_user, conversation_id, sentinel)
        conv_id, message_id, request_id = _wait_permission_request(ws)

        # 批准 → 工具执行。
        im_user.resolve_permission(conv_id, request_id, message_id, "allow_once")

        # 工具执行后,命令输出的哨兵被 agent 转达回来。
        frame = ws.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        assert sentinel in (frame.data.get("content") or "")
    finally:
        ws.close()


@pytest.mark.e2e
def test_permission_deny_blocks_tool(im_user: IMClient) -> None:
    """拒绝需许可工具 → 工具不执行 → 命令输出的哨兵永不出现,run 据此收口。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)
    sentinel = "PERMNO" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        _trigger_permission(im_user, conversation_id, sentinel)
        conv_id, message_id, request_id = _wait_permission_request(ws)

        # 拒绝 → 工具不执行。
        im_user.resolve_permission(conv_id, request_id, message_id, "deny")

        # 正向:run 据此收口——拒绝后 agent 仍会产出一条「被拒绝」收尾回复
        # (message.completed 到达即 run 没卡死)。
        ws.wait_for_event("message.completed", timeout=90.0)
    finally:
        ws.close()

    # 否定:工具没执行 → 命令打印的哨兵在整段历史里永不出现(在有界窗口内复核)。
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        for msg in im_user.list_messages(conversation_id):
            if msg.get("sender_type") == "agent" and sentinel in (
                msg.get("content") or ""
            ):
                pytest.fail(
                    f"denied tool still produced its output sentinel {sentinel!r} — "
                    "deny did not actually block execution"
                )
        time.sleep(2.0)
