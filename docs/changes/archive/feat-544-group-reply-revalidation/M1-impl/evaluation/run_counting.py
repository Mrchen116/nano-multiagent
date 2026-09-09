import json, time, re, sys, os
from pathlib import Path
from tests.e2e.critical_paths._im_client import IMClient

root = Path.cwd()
out = root / "output/feat544"
recipe = json.loads(Path(__file__).with_name("raft-counting.json").read_text())
c = IMClient(os.environ["IM_URL"])
c.register_or_login("nano", "nano1234")
node = c.wait_for_online_node()
ids = ["feat544-counter-a", "feat544-counter-b", "feat544-counter-c"]
existing = {a["agent_id"] for a in c.list_agents()}
for aid in ids:
    if aid not in existing:
        c.create_agent(
            node,
            aid,
            custom_prompt="你是协作群聊中的一个参与者。遵循群内任务规则，结合最新消息行动。",
            group_reply_policy="ALWAYS",
            default_model=recipe["model"],
            tool_allowlist=[],
        )
        c.wait_for_agent_listed(aid)
    else:
        c.update_agent_config(aid, group_reply_policy="ALWAYS", tool_allowlist=[])
for trial in map(int, sys.argv[1:] or ["1"]):
    for aid in ids:
        c.update_agent_config(aid, group_reply_policy="ALWAYS", tool_allowlist=[])
    cid = c.create_group_conversation(ids, title=f"feat544 Raft counting {trial}")
    d = {
        "case": "raft-counting",
        "trial": trial,
        "recipe": recipe,
        "conversation_id": cid,
        "started_at": time.time(),
        "model": recipe["model"],
    }
    d["input_id"] = c.send_message(cid, recipe["input"])
    deadline = time.monotonic() + recipe["timeout_seconds"]
    quiet_since = None
    last_numbers = []
    while time.monotonic() < deadline:
        msgs = c.list_messages(cid, limit=200)
        d["messages"] = msgs
        agents = [m for m in msgs if m["sender_type"] == "agent"]
        visible = [m for m in agents if m["content"].strip()]
        numbers = [
            int(m["content"].strip())
            for m in visible
            if re.fullmatch(r"[0-9]+", m["content"].strip())
        ]
        running = any(m["delivery_status"] == "running" for m in agents)
        d["numbers"] = numbers
        d["duplicates"] = len(numbers) - len(set(numbers))
        d["extra_text"] = [
            m["content"]
            for m in visible
            if not re.fullmatch(r"[0-9]+", m["content"].strip())
        ]
        if numbers != last_numbers:
            print(
                json.dumps(
                    {"trial": trial, "numbers": numbers, "running": running},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            last_numbers = numbers
        (out / f"raft-counting-{trial}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2)
        )
        if numbers and max(numbers) >= 20 and not running:
            if quiet_since is None:
                quiet_since = time.monotonic()
            if time.monotonic() - quiet_since >= 3:
                break
        else:
            quiet_since = None
        if len(visible) > 35:
            break
        time.sleep(0.3)
    d["outcome"] = (
        "passed"
        if numbers == list(range(1, 21))
        and not d["extra_text"]
        and quiet_since is not None
        and time.monotonic() - quiet_since >= 3
        else "failed"
    )
    d["elapsed_seconds"] = time.time() - d["started_at"]
    d["draft_count"] = sum(
        x["kind"] == "draft" for m in agents for x in m["reply_process"]
    )
    d["revalidation_count"] = sum(
        x["kind"] == "revalidation" for m in agents for x in m["reply_process"]
    )
    if d["outcome"] != "passed":
        for aid in ids:
            try:
                c.update_agent_config(aid, group_reply_policy="MENTION")
            except Exception as exc:
                d.setdefault("cleanup_errors", []).append(str(exc))
        d["cleanup_message_id"] = c.send_message(cid, "/stop", mentions=ids)
    (out / f"raft-counting-{trial}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                k: d[k]
                for k in [
                    "trial",
                    "outcome",
                    "numbers",
                    "duplicates",
                    "extra_text",
                    "draft_count",
                    "revalidation_count",
                    "elapsed_seconds",
                ]
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
