import json, time
from pathlib import Path
from tests.e2e.critical_paths._im_client import IMClient

c = IMClient(__import__("os").environ["IM_URL"])
c.register_or_login("nano", "nano1234")
aid = "feat544-corrector"
if not any(a["agent_id"] == aid for a in c.list_agents()):
    c.create_agent(
        c.wait_for_online_node(),
        aid,
        custom_prompt="本次隔离协作测试中，你持有的最终会议日期是9月19日。被用户@后，只回复：更正，日期改为9月19日，地点不变。不要@任何Agent，不用工具。",
        group_reply_policy="MENTION",
        default_model="deepseek:deepseek-v4-flash",
    )
    c.wait_for_agent_listed(aid)
cid = c.create_group_conversation(
    ["feat544-eval", aid], title="feat544 peer correction"
)
text = "feat544-eval：请写一份约600字的会议通知，日期9月12日，地点A会议室，不用工具。feat544-corrector：请检查日期并简短指出更正。"
d = {
    "case": "peer-correction",
    "conversation_id": cid,
    "input": text,
    "started_at": time.time(),
}
d["input_id"] = c.send_message(cid, text, mentions=[aid])
end = time.monotonic() + 100
while time.monotonic() < end:
    msgs = c.list_messages(cid)
    d["messages"] = msgs
    Path("output/feat544/peer-correction-fixed.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2)
    )
    a = [m for m in msgs if m["sender_type"] == "agent"]
    sources = [x for m in a for x in m["reply_process"] if x["kind"] == "revalidation"]
    if sources and a and all(m["delivery_status"] == "completed" for m in a):
        break
    time.sleep(0.3)
print(
    json.dumps(
        [
            (m["sender"]["id"], m["content"][:160], m["reply_process"])
            for m in d["messages"]
            if m["sender_type"] == "agent"
        ],
        ensure_ascii=False,
    )
)
