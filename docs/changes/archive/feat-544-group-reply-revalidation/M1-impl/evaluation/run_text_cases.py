import json, time, sys
from pathlib import Path
from tests.e2e.critical_paths._im_client import IMClient

root = Path.cwd()
out = root / "output/feat544"
out.mkdir(exist_ok=True, parents=True)
imurl = __import__("os").environ["IM_URL"]
c = IMClient(imurl)
c.register_or_login("nano", "nano1234")
aid = "feat544-eval"
agents = c.list_agents()
if not any(a["agent_id"] == aid for a in agents):
    c.create_agent(
        c.wait_for_online_node(),
        aid,
        custom_prompt="你是群聊协作助手。准确遵循用户当前要求，简洁作答。",
        group_reply_policy="ALWAYS",
        default_model="deepseek:deepseek-v4-flash",
    )
    c.wait_for_agent_listed(aid)
cases = json.loads((Path(__file__).with_name("cases.json")).read_text())["cases"]
cases += json.loads((Path(__file__).with_name("supplementary-cases.json")).read_text())[
    "cases"
]
selected = sys.argv[1:] or ["no-update", "date-correction"]
for case in cases:
    if case["id"] not in selected:
        continue
    cid = c.create_group_conversation([aid, "e2e-peer"], title="feat544 " + case["id"])
    record = {
        "case": case,
        "conversation_id": cid,
        "started_at": time.time(),
        "model": "deepseek:deepseek-v4-flash",
        "messages": [],
        "samples": [],
    }
    input_text = case["input"]
    if case["id"] == "tool-send":
        input_text = (
            "请调用 send_message，将约400字活动通知投递到会话 ID "
            + cid
            + "：9月12日，A会议室。请实际执行工具投递。"
        )
    record["actual_input"] = input_text
    record["input_id"] = c.send_message(cid, input_text)
    injected = 0
    last_inject = 0
    deadline = time.monotonic() + 200
    while time.monotonic() < deadline:
        msgs = c.list_messages(cid)
        agentmsgs = [
            m
            for m in msgs
            if m.get("sender_type") == "agent"
            or m.get("sender", {}).get("type") == "agent"
        ]
        running = [m for m in agentmsgs if m.get("delivery_status") == "running"]
        if (
            running
            and injected < len(case["updates"])
            and (
                injected == 0
                or any(
                    x.get("kind") == "revalidation"
                    for m in running
                    for x in m["reply_process"]
                )
            )
            and time.monotonic() - last_inject > 1
        ):
            record.setdefault("update_ids", []).append(
                c.send_message(cid, case["updates"][injected])
            )
            injected += 1
            last_inject = time.monotonic()
        record["messages"] = msgs
        (out / f"{case['id']}-{int(record['started_at'])}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2)
        )
        if agentmsgs and not running and (injected == len(case["updates"])):
            break
        time.sleep(0.3)
    print(
        json.dumps(
            {
                "case": case["id"],
                "conversation_id": cid,
                "injected": injected,
                "messages": record["messages"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
