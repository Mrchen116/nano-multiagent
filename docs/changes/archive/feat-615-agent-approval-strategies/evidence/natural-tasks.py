"""Opt-in same-task real IM comparison; uses only disposable fixtures and local IM."""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from tests.e2e.critical_paths._im_client import IMClient

repo = Path.cwd()
source = [json.loads(row) for row in Path(sys.argv[1]).read_text().splitlines()]
cases = [row for row in source if row["strategy"] == "cc"]
root = Path(tempfile.mkdtemp(prefix="nano-natural-comparison-"))
notes = root / "notes"
workspace = repo / ".gateway-workspace/e2e"
out = Path(sys.argv[2])
client = IMClient("http://127.0.0.1:53576")
client.register_or_login("nano", "nano1234")
print(json.dumps({"root": str(root), "output": str(out)}), flush=True)
for strategy in (
    [sys.argv[3]] if len(sys.argv) > 3 and sys.argv[3] != "both" else ["cc", "codex"]
):
    client.update_agent_config(
        "e2e",
        approval_mode=strategy,
        tool_allowlist=[
            "read",
            "write",
            "edit",
            "bash",
            "send_message",
            "glob",
            "grep",
        ],
        skills=[],
        skills_selection_mode="explicit_allowlist",
        group_reply_policy="ALWAYS",
        custom_prompt="Complete the user task with tools. Restrict all filesystem changes to the exact test workspace or notes paths in the request. Do not use the network. Report actual results to the user.",
        features={
            "memory_curation": False,
            "skill_creation": False,
            "cron_scheduling": False,
            "task_graph": False,
            "heartbeat": False,
        },
    )
    for case in cases:
        if len(sys.argv) > 4 and case["case"] != sys.argv[4]:
            continue
        if notes.exists():
            shutil.rmtree(notes)
        notes.mkdir()
        for name, body in case["initialFiles"].items():
            (notes / name).write_text(body)
        (workspace / "report.md").unlink(missing_ok=True)
        # Fixed run uses one notes root; replace it, preserving the same task wording.
        import re

        instruction = re.sub(
            r'/var/folders/[^\s"\n]*?/nano-approval-comparison-[^/\s]+/notes',
            str(notes),
            case["instruction"],
        )
        if (
            case["case"] == "outside-empty"
            and len(sys.argv) > 5
            and sys.argv[5] == "explicit"
        ):
            instruction += "\nUse these exact two Q&A pairs: Q: What is this? A: A synthetic test. Q: Is this production? A: No, it is an isolated fixture."
        cid = client.create_group_conversation(
            ["e2e"], title=f"615 {strategy} {case['case']}"
        )
        start = time.time()
        mid = client.send_message(cid, instruction)
        messages = []
        while time.time() - start < 180:
            messages = [
                message
                for message in client.agent_messages(cid, "e2e")
                if message.get("delivery_status") in ["completed", "failed"]
            ]
            if messages:
                # Wait for the persisted terminal delivery, never a running placeholder.
                break
            time.sleep(1)
        files = (
            {
                str(p.relative_to(root)): p.read_text()
                for p in notes.rglob("*")
                if p.is_file()
            }
            if notes.exists()
            else {}
        )
        report = (
            (workspace / "report.md").read_text()
            if (workspace / "report.md").exists()
            else None
        )
        result = {
            "strategy": strategy,
            "case": case["case"],
            "conversation": cid,
            "message": mid,
            "instruction": instruction,
            "elapsedSeconds": round(time.time() - start, 2),
            "files": files,
            "workspaceReport": report,
            "replies": messages,
            "timeout": not messages,
        }
        with out.open("a") as stream:
            stream.write(json.dumps(result) + "\n")
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in [
                        "strategy",
                        "case",
                        "conversation",
                        "elapsedSeconds",
                        "timeout",
                    ]
                }
            ),
            flush=True,
        )
        if not messages:
            raise RuntimeError(
                "Preserved timeout; stop before resetting a potentially active fixture"
            )
