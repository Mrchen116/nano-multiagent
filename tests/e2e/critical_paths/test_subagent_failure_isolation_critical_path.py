"""关键路径 4(配套):子 agent 失败被隔离,不拖垮常驻 Gateway 进程。

spec Req「前台子 agent 可用且失败被隔离」第 2 个 Scenario:
- GIVEN 一个会失败的子 agent 任务
- WHEN 该子 agent 执行失败
- THEN 失败被隔离在该次结果内,Gateway 进程存活,后续消息仍能正常处理。

这是 #117 的核心一半:#117 暴露的不仅是「子 agent 跨事件循环崩溃」,更是「一个子 agent 出问题
会不会带崩整个常驻进程」。catalog 把本 scenario 声明在守护范围内,本测试让该声明成真。

旅程:① 让父 agent 派一个**注定失败**的前台子 agent(子 agent 被要求跑一条必然非零退出的
命令并「必须成功」)→ 父 agent 仍给出一条回复(失败被隔离、没崩进程)。② 紧接着在**同一对话**
发一条普通的「回哨兵」消息 → 仍能正常收到含哨兵的回复 = Gateway 进程存活、后续消息正常处理。

鲁棒断言(决策 4):隔离的确定性锚不是「子 agent 失败时父 agent 回了什么」(措辞不定),而是
**第二轮普通消息能否正常收到含哨兵回复**——只有 Gateway 进程在子 agent 失败后仍存活、事件
循环没崩,这条才答得出来。第一轮只断「有 message.completed 到达」(进程没卡死/没崩)。
"""

from __future__ import annotations

import secrets

import pytest

from ._im_client import IMClient


@pytest.mark.e2e
def test_failed_subagent_isolated_from_main_process(im_user: IMClient) -> None:
    """子 agent 失败被隔离:父 agent 不崩、Gateway 存活、后续消息仍正常处理。"""
    agent_id = im_user.first_agent_id()
    conversation_id = im_user.create_direct_conversation(agent_id)

    ws = im_user.connect_ws()
    try:
        # ① 派一个注定失败的子 agent:要求子 agent 跑一条必然非零退出的命令并「必须成功」,
        #    它无论如何完不成 → 子 agent 任务以失败收场。父 agent 仍应给出一条回复(没崩)。
        im_user.send_message(
            conversation_id,
            "请用 agent 工具派一个前台子 agent，要求它运行命令 `bash -c 'exit 7'` "
            "并且必须让这条命令成功返回 0；只有命令成功了才算完成任务。"
            "（这条命令注定会失败——我就是要观察一个失败的子 agent 任务。）"
            "等子 agent 结束后，简短告诉我结果。",
        )
        # 第一轮只验「进程没崩/没卡死」:父 agent 最终产出了一条完成消息。
        ws.wait_for_event("message.completed", timeout=120.0)
    finally:
        ws.close()

    # ② 隔离的确定性锚:子 agent 失败后,同一对话再发一条普通消息,仍能正常收到回复。
    #    只有 Gateway 进程存活、事件循环未崩,这条才答得出含哨兵的回复。
    ws2 = im_user.connect_ws()
    try:
        sentinel = "ISO" + secrets.token_hex(4).upper()
        im_user.send_message(
            conversation_id,
            f"请把这个 token 原样回复给我，只回 token 本身：{sentinel}",
        )
        frame = ws2.wait_for_event(
            "message.completed",
            lambda f: sentinel in (f.data.get("content") or ""),
        )
        content = frame.data.get("content") or ""
        assert sentinel in content, (
            f"Gateway did not process a follow-up message after subagent failure "
            f"(isolation broken); reply: {content!r}"
        )
        assert "Traceback" not in content
    finally:
        ws2.close()
