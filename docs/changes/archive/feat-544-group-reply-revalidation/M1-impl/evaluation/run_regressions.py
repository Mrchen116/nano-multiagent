import json, time
from pathlib import Path
from tests.e2e.critical_paths._im_client import IMClient

c = IMClient(__import__("os").environ["IM_URL"])
c.register_or_login("nano", "nano1234")
out = Path("output/feat544")


def await_reply(cid):
    end = time.monotonic() + 90
    while time.monotonic() < end:
        msgs = c.list_messages(cid)
        a = [m for m in msgs if m["sender_type"] == "agent"]
        if a and all(m["delivery_status"] == "completed" for m in a):
            return msgs
        time.sleep(0.3)
    raise TimeoutError(cid)


cid = c.create_direct_conversation("feat544-eval", title="feat544 direct regression")
c.send_message(cid, "请只回复：直聊正常。不要使用工具。")
msgs = await_reply(cid)
assert any("直聊正常" in m["content"] for m in msgs if m["sender_type"] == "agent")
assert not any(m["reply_process"] for m in msgs)
(out / "direct-regression.json").write_text(
    json.dumps({"conversation_id": cid, "messages": msgs}, ensure_ascii=False, indent=2)
)
aid = "feat544-mention"
if not any(a["agent_id"] == aid for a in c.list_agents()):
    c.create_agent(
        c.wait_for_online_node(),
        aid,
        custom_prompt="按用户要求简短回复。",
        group_reply_policy="MENTION",
        default_model="deepseek:deepseek-v4-flash",
    )
    c.wait_for_agent_listed(aid)
cid = c.create_group_conversation([aid, "e2e-peer"], title="feat544 mention regression")
mid = c.send_message(cid, "这是没有@的背景消息：记号是蓝鸟。")
time.sleep(3)
before = c.list_messages(cid)
assert not any(m["sender_type"] == "agent" for m in before)
c.send_message(cid, "请说出背景消息中的记号，只回复该记号。", mentions=[aid])
after = await_reply(cid)
assert any("蓝鸟" in m["content"] for m in after if m["sender_type"] == "agent")
(out / "mention-regression.json").write_text(
    json.dumps(
        {
            "conversation_id": cid,
            "ignored_id": mid,
            "before_mention": before,
            "messages": after,
        },
        ensure_ascii=False,
        indent=2,
    )
)
print("direct + MENTION real-model regression passed")
