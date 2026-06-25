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
from ._im_polling import assert_absent_within, poll_until
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


def _find_tool_call_with_approval(
    im_user: IMClient, conversation_id: str, approval: str
) -> dict | None:
    """在会话历史里找一条 ``tool_call.approval == approval`` 的工具调用（REST 服务的视图）。

    feat-434-M1: approval 标识必须从内核 gate 一路流到 IM REST 序列化，前端闸门区才能显
    「已授权/已拒绝」。这是端到端贯通的确定性锚——比断前端 DOM 稳，且证明的是同一条数据路径
    （内核→Gateway→IM 持久化→REST），前端只是读它。
    """
    for msg in im_user.list_messages(conversation_id):
        for tc in msg.get("tool_calls") or []:
            if tc.get("approval") == approval:
                return tc
    return None


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
    poll_until(
        lambda: _find_written_sentinel(e2e_stack.wt_dir, sentinel),
        lambda hit: hit is not None,
        timeout=15.0,
        interval=1.0,
        desc=f"approved-write .gitconfig containing sentinel {sentinel!r}",
    )

    # feat-434-M1 端到端锚:allow 成功工具的 approval=user_allow 经 内核→Gateway→IM 流出,
    # REST 历史(前端读的同一视图)真带上它 → 前端闸门区据此显「已授权」。allow 侧无现成
    # reason_code 载体,这条断言守护「最易漏一环」不再悄悄丢。
    poll_until(
        lambda: _find_tool_call_with_approval(im_user, conversation_id, "user_allow"),
        lambda hit: hit is not None,
        timeout=20.0,
        interval=1.0,
        desc="approved tool_call carries approval=user_allow in REST history",
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
    assert_absent_within(
        lambda: _find_written_sentinel(e2e_stack.wt_dir, sentinel),
        lambda hit: hit is not None,
        window=20.0,
        desc=f"denied-write .gitconfig with sentinel {sentinel!r} (deny should block it)",
    )

    # feat-434-M1 端到端锚:deny 的 approval=user_deny 经 内核(ToolError.details)→Gateway→IM
    # 流出,REST 历史带上它 → 前端闸门区显「已拒绝」。
    #
    # ⚠️ 弱断言(条件式):被拒工具是否**被持久化成一条 tool_call** 受 LLM run 走向影响——
    # 拒绝后内核可能在 emit denied tool_end 之前就收口该 run(没有文件系统副作用做锚,见上方
    # assert_absent_within)。当被拒 tool_call 确实出现时,它**必须**带 approval=user_deny;
    # 但「它是否出现」不是本字段能保证的属性(与既有 reason=denied 同源,同样不保证)。因此:
    #   - deny 阻断本身由 assert_absent_within(文件未写)确定性证明;
    #   - approval=user_deny 的传播链由 R1/R2 单测确定性覆盖(gate→ToolError.details→ToolResult
    #     →tool_end→IM encode/decode round-trip);
    #   - 这里只在 tool_call 出现时附加校验它带对了 approval,不强求其出现(避免 LLM 非确定 flaky)。
    def _denied_tool_call() -> dict | None:
        return next(
            (
                tc
                for msg in im_user.list_messages(conversation_id)
                for tc in (msg.get("tool_calls") or [])
                if tc.get("reason") == "denied" or tc.get("approval") is not None
            ),
            None,
        )

    deadline = time.monotonic() + 15.0
    denied_tc = _denied_tool_call()
    while denied_tc is None and time.monotonic() < deadline:
        time.sleep(1.0)
        denied_tc = _denied_tool_call()
    if denied_tc is not None:
        assert denied_tc.get("approval") == "user_deny", (
            f"a persisted denied tool_call must carry approval=user_deny, got {denied_tc!r}"
        )
