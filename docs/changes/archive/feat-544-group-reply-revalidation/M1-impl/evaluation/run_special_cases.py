import json, time, sys
from pathlib import Path
from tests.e2e.critical_paths._im_client import IMClient

root = Path.cwd()
out = root / "output/feat544"
c = IMClient(__import__("os").environ["IM_URL"])
c.register_or_login("nano", "nano1234")
kind = sys.argv[1]
aid = "feat544-eval"
if kind == "background":
    c.update_agent_config(aid, tool_allowlist=["bash", "read", "send_message"])
    prompt = '请调用bash工具，参数run_in_background=true，执行命令：sleep 15; printf "会议日期9月12日，地点A会议室"。启动后先只简短确认，结束当前回复。等后台任务完成通知到达，再根据结果在当前群直接写一份约600字的会议通知。不要主动等待或查询任务。'
    correction = "日期更正为9月28日，地点改为D会议室，请用中文两句话给出最终通知。"
else:
    aid = "feat544-vision"
    if not any(a["agent_id"] == aid for a in c.list_agents()):
        c.create_agent(
            c.wait_for_online_node(),
            aid,
            custom_prompt="你是群聊协作助手。准确按当前要求回复。",
            group_reply_policy="ALWAYS",
            default_model="codexOAuth:gpt-5.6-sol",
        )
        c.wait_for_agent_listed(aid)
    prompt = "请用中文写一份约600字的会议通知，日期9月12日，地点A会议室。不要用工具。"
    correction = "以新上传图片中的日期和地点为准，请中文两句话给出最终通知。"
    import subprocess

    subprocess.run(
        [
            __import__("os").environ.get("FEAT544_IMAGE_PYTHON", sys.executable),
            "-c",
            'from PIL import Image,ImageDraw,ImageFont; im=Image.new("RGB",(800,280),"white"); d=ImageDraw.Draw(im); f=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc",52); d.text((30,40),"Date: September 27",fill="black",font=f); d.text((30,150),"Room: C",fill="black",font=f); im.save("output/feat544/image-correction.png")',
        ],
        check=True,
    )
    resp = c._http.post(
        "/im/v1/uploads",
        params={"file_name": "meeting-correction.png"},
        headers={**c._auth_headers, "Content-Type": "image/png"},
        content=(out / "image-correction.png").read_bytes(),
    )
    resp.raise_for_status()
    attachment = resp.json()
cid = c.create_group_conversation([aid, "e2e-peer"], title="feat544 " + kind)
d = {
    "case": kind,
    "input": prompt,
    "update": correction,
    "conversation_id": cid,
    "started_at": time.time(),
    "model": "codexOAuth:gpt-5.6-sol"
    if kind == "image"
    else "deepseek:deepseek-v4-flash",
}
(out / f"{kind}-fixture.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))
d["input_id"] = c.send_message(cid, prompt)
injected = False
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    msgs = c.list_messages(cid)
    agentmsgs = [m for m in msgs if m["sender_type"] == "agent"]
    running = [m for m in agentmsgs if m["delivery_status"] == "running"]
    eligible = (
        running
        if kind != "background"
        else [
            m
            for m in running
            if m["tool_calls"]
            and all(t["status"] == "completed" for t in m["tool_calls"])
            and any(
                a["delivery_status"] == "completed" and a["content"] for a in agentmsgs
            )
        ]
    )
    if eligible and not injected:
        if kind == "image":
            resp = c._http.post(
                f"/im/v1/conversations/{cid}/messages",
                headers=c._auth_headers,
                json={
                    "sender": {"type": "user", "id": c.user_id},
                    "content": correction,
                    "attachments": [attachment],
                },
            )
            resp.raise_for_status()
            mid = resp.json()["id"]
        else:
            mid = c.send_message(cid, correction)
        d["update_id"] = mid
        injected = True
    d["messages"] = msgs
    (out / f"{kind}-{int(d['started_at'])}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2)
    )
    if injected and agentmsgs and not running:
        break
    time.sleep(0.25)
print(
    json.dumps(
        {
            "case": kind,
            "conversation_id": cid,
            "injected": injected,
            "messages": [
                (m["delivery_status"], m["content"], m["reply_process"])
                for m in d["messages"]
                if m["sender_type"] == "agent"
            ],
        },
        ensure_ascii=False,
    ),
    flush=True,
)
