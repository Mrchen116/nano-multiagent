"""J2: one Global main Session coordinates a real child across two chats.

Uses the existing live-proxy gate and isolated e2e_stack. Public work records
prove actual Inbox consumption, delegation, same-child follow-up and dispatch;
a workspace marker controls only task timing, never model responses or events.
"""

from __future__ import annotations

import csv
import json
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from .conftest import E2EStack


def _get(http: httpx.Client, path: str, **params: Any) -> dict:
    response = http.get(path, params=params)
    response.raise_for_status()
    return response.json()


def _work(http: httpx.Client, base: str) -> dict:
    """Read all main turns/items through the same pagination used by the UI."""
    view = _get(http, base, limit=50)
    turns = list(view["turns"])
    cursor = view["next_cursor"]
    while cursor:
        page = _get(http, base, before_turn=cursor, limit=50)
        turns.extend(page["turns"])
        cursor = page["next_cursor"]
    for turn in turns:
        cursor = turn["next_items_cursor"]
        while cursor:
            path = (
                f"{base}/sessions/{quote(turn['session_id'], safe='')}/turns/"
                f"{quote(turn['turn_id'], safe='')}/items"
            )
            page = _get(http, path, after_seq=cursor, limit=200)
            turn["items"].extend(page["items"])
            cursor = page["next_cursor"]
    return {**view, "turns": turns}


def _tools(view: dict, name: str) -> list[dict]:
    return sorted(
        [
            {**item["payload"], "session_id": turn["session_id"]}
            for turn in view["turns"]
            for item in turn["items"]
            if item["kind"] == "tool" and item["payload"].get("name") == name
        ],
        key=lambda item: item["seq"],
    )


def _consumed(view: dict, target: str, message_id: str) -> dict | None:
    for call in _tools(view, "inbox"):
        args = call.get("input", {})
        if (
            call.get("status") != "completed"
            or args.get("action") != "read"
            or args.get("target") != target
        ):
            continue
        messages = call.get("detail", {}).get("messages", [])
        has_body = any(message.get("message_id") == message_id for message in messages)
        committed = any(
            fact.get("type") == "inbox_read_committed"
            and any(
                ref.get("conversation_id") == target
                and ref.get("message_id") == message_id
                for ref in fact.get("source_refs", [])
            )
            for fact in call.get("work_facts", [])
        )
        if has_body and committed:
            return call
    return None


def _delegation(view: dict) -> dict | None:
    return next(
        (
            call
            for call in _tools(view, "agent")
            if call.get("status") == "completed"
            and not call.get("input", {}).get("agent_id")
            and call.get("input", {}).get("run_in_background") is True
            and call.get("detail", {}).get("agent_id")
        ),
        None,
    )


def _followup(view: dict, child_id: str, amendment: str) -> dict | None:
    return next(
        (
            call
            for call in _tools(view, "agent")
            if call.get("status") == "completed"
            and call.get("input", {}).get("agent_id") == child_id
            and amendment in call.get("input", {}).get("prompt", "")
        ),
        None,
    )


def _dispatches(view: dict, target: str) -> list[dict]:
    return [
        fact
        for call in _tools(view, "send_message")
        for fact in call.get("work_facts", [])
        if fact.get("type") == "dispatch_confirmed"
        and fact.get("conversation_id") == target
    ]


@pytest.mark.e2e
def test_global_agent_reads_cross_chat_amendment_and_follows_same_child(
    im_user: IMClient, e2e_stack: E2EStack
) -> None:
    """A delegates; B amends; the same child delivers the revised result to A."""
    node_id = im_user.wait_for_online_node(timeout=40)
    suffix = secrets.token_hex(4)
    agent_id = f"e2eGlobal{suffix}"
    amendment = f"AMEND{suffix.upper()}"
    with httpx.Client(
        base_url=im_user.im_url,
        headers={"Authorization": f"Bearer {im_user.token}"},
        timeout=60,
    ) as http:
        response = http.post(
            f"/im/v1/nodes/{node_id}/agents",
            json={
                "agent_id": agent_id,
                "owner_id": im_user.owner_id,
                "display_name": f"Global J2 {suffix}",
                "work_mode": "global",
                "group_reply_policy": "ALWAYS",
                "default_model": e2e_stack.llm_model,
                "tool_allowlist": [
                    "inbox",
                    "conversations",
                    "send_message",
                    "agent",
                    "bash",
                    "read",
                    "write",
                ],
                "skills": [],
                "custom_prompt": (
                    "你负责统筹用户在不同聊天提出的同一任务。先真实读取 Inbox 正文。"
                    "实质计算委派给后台子 Agent，收到修订用 agent 工具的 agent_id 跟进同一个子 Agent。"
                    "测试中不发确认、进度或中间结果；仅收到子 Agent 最终修订结果后，"
                    "用 send_message(to=原始任务聊天ID,text=结果)交付一次。"
                    "主 Agent 不替子 Agent 计算、不写测试文件、不创建 release 标记。"
                    "委派后可结束当前轮次，等待 Inbox 或后台返回唤醒。"
                ),
            },
        )
        response.raise_for_status()
        workspace = Path(response.json()["workspace_root"]).resolve()
        assert workspace.is_relative_to(
            (Path(e2e_stack.wt_dir) / ".gateway-workspace").resolve()
        )
        im_user.wait_for_agent_listed(agent_id, timeout=40)
        assert im_user.get_agent_config(agent_id)["work_mode"] == "global"
        # These are ordinary task inputs in the isolated workspace, not runtime state.
        task_dir = workspace / f"j2-{suffix}"
        task_dir.mkdir()
        dataset, release, result = (
            task_dir / "orders.csv",
            task_dir / "release",
            task_dir / "result.json",
        )
        rows = [(index, index * 17 + 23) for index in range(1, 121)]
        with dataset.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(["order_id", "amount"])
            writer.writerows(rows)
        expected = sum(amount - 3 for index, amount in rows if index % 2 == 0)
        chat_a = im_user.create_direct_conversation(agent_id, title=f"J2 A {suffix}")
        chat_b = im_user.create_direct_conversation(agent_id, title=f"J2 B {suffix}")
        assert chat_a != chat_b
        base = f"/im/v1/agents/{agent_id}/work"
        try:
            message_a = im_user.send_message(
                chat_a,
                f"订单汇总任务，最终只交付到本聊天 {chat_a}。数据：{dataset}。"
                "请立即用 agent(run_in_background=true)委派一个真实子 Agent 读取 CSV、"
                "核对行数并计算全部订单 amount 合计。稍后我会在另一聊天修订统计口径。"
                f"给子 Agent 的指令必须包含：在 {release} 出现前不得提交结果；"
                "可用 bash 每次最多等待 20 秒，再检查后续指令，总等待上限 600 秒。"
                "标记由测试夹具创建，任何 Agent 均不得创建它。"
                f"标记出现并处理后续修订后，将最终对象写入 {result}，"
                "格式为 {amendment:修订标识,total:最终整数,count:选中行数}，并原样返回。"
                "主 Agent 委派后保持可接收其他聊天的新消息，不轮询子 Agent、不发布中间消息。",
            )
            first = poll_until(
                lambda: _work(http, base),
                lambda view: bool(
                    _consumed(view, chat_a, message_a) and _delegation(view)
                ),
                timeout=240,
                interval=1,
                desc="A body committed and real background child created",
            )
            main_session = first["main_session_id"]
            assert main_session
            delegation = _delegation(first)
            assert delegation is not None
            child_id = delegation["detail"]["agent_id"]
            assert not im_user.agent_messages(chat_a, agent_id)
            assert not im_user.agent_messages(chat_b, agent_id)
            assert not release.exists()
            message_b = im_user.send_message(
                chat_b,
                f"修订同一订单任务，标识 {amendment}：只选择 order_id 为偶数的订单，"
                "每笔选中订单的 amount 扣减固定费用 3 后求和，count 是选中行数。"
                "必须先把这个标识和计算口径通过 agent(agent_id=原子AgentID,prompt=修订内容)"
                "发给刚才同一个子 Agent，不另起子 Agent，不由主 Agent 计算。"
                f"子 Agent 继续等待 {release}，夹具观察到真实跟进后会释放；"
                f"最终 JSON 的 amendment 必须为 {amendment}，只发回原聊天 {chat_a}。",
            )
            revised = poll_until(
                lambda: _work(http, base),
                lambda view: bool(
                    _consumed(view, chat_b, message_b)
                    and _followup(view, child_id, amendment)
                ),
                timeout=240,
                interval=1,
                desc="B body committed and amendment sent to the same child",
            )
            assert revised["main_session_id"] == main_session
            followup = _followup(revised, child_id, amendment)
            assert followup is not None
            assert followup["session_id"] == delegation["session_id"] == main_session
            assert followup["seq"] > delegation["seq"]
            assert not im_user.agent_messages(chat_a, agent_id)
            assert not im_user.agent_messages(chat_b, agent_id)
            release.write_text("continue\n", encoding="utf-8")
            final = poll_until(
                lambda: _work(http, base),
                lambda view: any(
                    amendment in fact.get("text", "")
                    and str(expected) in fact.get("text", "")
                    for fact in _dispatches(view, chat_a)
                ),
                timeout=240,
                interval=1,
                desc="actual final dispatch to A incorporates B amendment",
            )
            assert final["main_session_id"] == main_session
            assert {turn["session_id"] for turn in final["turns"]} == {main_session}
            assert json.loads(result.read_text(encoding="utf-8")) == {
                "amendment": amendment,
                "total": expected,
                "count": 60,
            }
            linked = [
                session
                for session in final["other_executions"]
                if session.get("child_agent_id") == child_id
            ]
            assert len(linked) == 1
            assert linked[0]["parent_session_id"] == main_session
            child = _get(
                http, f"{base}/sessions/{quote(linked[0]['session_id'], safe='')}/turns"
            )
            assert child["turns"], (
                "actual child Session must have a readable work trace"
            )
            deliveries = _dispatches(final, chat_a)
            messages = im_user.agent_messages(chat_a, agent_id)
            assert len(messages) == len(deliveries) == 1
            assert messages[0]["id"] == deliveries[0]["message_id"]
            assert amendment in messages[0]["content"]
            assert str(expected) in messages[0]["content"]
            assert not im_user.agent_messages(chat_b, agent_id)
            for message in messages:
                assert message["delivery_status"] == "completed"
                assert not message.get("tool_calls")
                assert not message.get("thinking")
                assert not message.get("permission_requests")
        finally:
            # Release a waiting child even on assertion failure; fixture owns shutdown.
            release.touch(exist_ok=True)
