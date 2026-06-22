"""关键路径 9:工具权限审批人在回路可用(approve / deny 双向)。

spec Req「工具权限审批人在回路可用」。两个 Scenario：

1. **批准后运行继续**:agent 要调一个需许可的工具,用户在 IM 收到 ``permission.request`` →
   批准(``allow_once``) → 工具执行 → 用户最终收到带结果的回复。
2. **拒绝后工具不执行**:同样的需许可工具 → 收到 ``permission.request`` → 拒绝(``deny``) →
   该工具不执行,run 据此收口。

鲁棒断言(design 决策 4)——审批的「工具是否真执行」必须有一个不受 LLM 措辞影响的确定锚:
- 触发审批用 ``write`` 工具写一个 **dangerous basename**(``.gitconfig``)。该工具对敏感
  basename **硬性返回 behavior="ask"**(write.check_permissions,bypass-immune),不依赖
  LLM classifier 的概率判定 → 审批**必然**触发,稳。文件落在 agent 隔离 workspace
  (``<wt>/.gateway-workspace/<agent_id>/``),不污染真实环境。
- 工具是否执行的**确定性锚 = 文件系统副作用**:approve → 那个 ``.gitconfig`` 真被写出
  且含哨兵;deny → 它根本不存在。这是「工具有没有跑」的铁证,比断 LLM 回复措辞稳得多。
- 协议锚:正向 ``permission.request`` / ``permission.resolved`` 事件 + run 收口
  ``message.completed``。
"""

from __future__ import annotations

import glob
import os
import secrets
import time

import pytest

from ._im_client import IMClient
from .conftest import E2EStack

# write 工具对该 basename 硬性 ask(dangerous_paths.DANGEROUS_FILES),触发必然审批。
_DANGEROUS_BASENAME = ".gitconfig"


def _find_written_sentinel(wt_dir: str, sentinel: str) -> str | None:
    """在整个 gateway workspace 树里找含哨兵的 ``.gitconfig``。

    不锁定具体 agent 子目录:直聊实际由哪个 agent 处理、其 workspace 子目录名,都不该由
    测试臆测(`first_agent_id` 只是 IM 列表里的第一个,未必等于实际处理消息那个 agent)。
    哨兵随机唯一,递归搜即可精确归因——文件出现 = 工具执行,这是确定性副作用锚。
    """
    pattern = os.path.join(wt_dir, ".gateway-workspace", "**", _DANGEROUS_BASENAME)
    for path in glob.glob(pattern, recursive=True):
        try:
            if sentinel in open(path).read():
                return path
        except OSError:
            continue
    return None


def _trigger_write_permission(im_user: IMClient, conv_id: str, sentinel: str) -> None:
    """让 agent 用 write 工具写一个 dangerous basename(必触发 ask),内容含哨兵。"""
    im_user.send_message(
        conv_id,
        f"请用 write 工具，在你的当前工作目录下创建一个名为 {_DANGEROUS_BASENAME} 的文件，"
        f"文件内容就是这一行：{sentinel}",
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
def test_permission_approve_lets_tool_run(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """批准 → 工具执行 → 那个 dangerous 文件真被写出且含哨兵。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)
    # 哨兵随机唯一 → 文件是否出现可精确归因到本次 approve,无需 pre-clean。
    sentinel = "PERMOK" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        _trigger_write_permission(im_user, conversation_id, sentinel)
        conv_id, message_id, request_id = _wait_permission_request(ws)

        # 批准 → 工具执行。
        im_user.resolve_permission(conv_id, request_id, message_id, "allow_once")
        ws.wait_for_event("permission.resolved", timeout=60.0)
        ws.wait_for_event("message.completed", timeout=90.0)
    finally:
        ws.close()

    # 确定性锚:approve 后那个 dangerous 文件真被写出且含哨兵(工具真执行了)。
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if _find_written_sentinel(e2e_stack.wt_dir, sentinel):
            break
        time.sleep(1.0)
    else:
        raise AssertionError(
            f"approved write produced no .gitconfig containing sentinel {sentinel!r} "
            "anywhere under the workspace — approval did not let the tool run"
        )


@pytest.mark.e2e
def test_permission_deny_blocks_tool(im_user: IMClient, e2e_stack: E2EStack) -> None:
    """拒绝 → 工具不执行 → 那个 dangerous 文件根本不存在,run 据此收口。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)
    # 哨兵随机唯一 → 「该哨兵的文件从未出现」可干净归因到 deny,无需 pre-clean。
    sentinel = "PERMNO" + secrets.token_hex(4).upper()

    ws = im_user.connect_ws()
    try:
        _trigger_write_permission(im_user, conversation_id, sentinel)
        conv_id, message_id, request_id = _wait_permission_request(ws)

        # 拒绝 → 工具不执行。
        im_user.resolve_permission(conv_id, request_id, message_id, "deny")
        ws.wait_for_event("permission.resolved", timeout=60.0)
        # run 据此收口(被拒绝后 agent 仍产出一条收尾回复 → message.completed 到达即没卡死)。
        ws.wait_for_event("message.completed", timeout=90.0)
    finally:
        ws.close()

    # 确定性锚:deny 后含该哨兵的 dangerous 文件在有界窗口内始终不出现(工具没跑)。
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        hit = _find_written_sentinel(e2e_stack.wt_dir, sentinel)
        if hit:
            pytest.fail(
                f"denied write still created {hit!r} — deny did not block the tool"
            )
        time.sleep(2.0)
