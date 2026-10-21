"""Real host Inbox fragments → sent proposal → same-epoch child → HTTP recovery.

No inbox bodies, observation labels, host_context, approval rows, source kinds or
native events are manufactured. Controlled model choices call public host tools.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from ._im_polling import poll_until
from ._im_gateway import restart_gateway
from .conftest import _parse_ports_env


def projected_rows(record: dict) -> list[dict]:
    """Decode actual JSONL evidence rows, without reconstructing host facts."""
    rows = []
    for message in record["messages"]:
        content = message["content"]
        texts = (
            [content]
            if isinstance(content, str)
            else [b.get("text", "") for b in content]
        )
        for text in texts:
            for line in text.splitlines():
                if line.startswith("{"):
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if (
                        "inbox_result" in row
                        or "send_message_result" in row
                        or "tool_result" in row
                    ):
                        rows.append(row)
    return rows


from .test_auto_review_retry_critical_path import approvals, running

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("policy", ["nano", "codex"])
@pytest.mark.parametrize("epoch", ["same", "restart", "compact"])
@pytest.mark.parametrize("flow", ["direct", "ptc"])
@pytest.mark.timeout(180)
def test_real_inbox_pages_sent_proposal_and_child_service_recovery(
    tmp_path: Path, policy: str, epoch: str, flow: str
):
    """Preserve each real partial page and source status through an actual child."""
    case_id = f"{policy}_source"
    with running(
        tmp_path,
        policy,
        work_mode="global",
        agent_ids=["e2e"],
        tools=["inbox", "send_message", "subagent", "bash"],
    ) as (client, root, url):
        outside = client.create_group_conversation(
            [], title="Unobserved library history"
        )
        client.send_message(
            outside,
            "LIBRARY_OUTSIDE_EFFECTIVE_CONTEXT " + "large unrelated history " * 1000,
        )
        response = client._http.post(
            "/im/v1/personal-agent",
            headers=client._auth_headers,
            json={
                "request_key": case_id,
                "node_id": client.wait_for_online_node(),
                "display_name": "Source regression PA",
            },
        )
        response.raise_for_status()
        binding = response.json()["binding"]
        agent_id, conversation = binding["agent_id"], binding["conversation_id"]
        client.wait_for_agent_listed(agent_id)
        client.update_agent_config(
            agent_id,
            default_model="main",
            tool_allowlist=[
                "inbox",
                "send_message",
                "subagent",
                "bash",
                "plugin_manager",
            ],
        )
        workspace = Path(client.get_agent_config(agent_id)["workspace_root"])
        assert workspace.resolve().is_relative_to(
            (root / ".gateway-workspace").resolve()
        )
        bundle = workspace / "source-ptc-fixture"
        bundle.mkdir()
        (bundle / "package.json").write_text(
            json.dumps(
                {
                    "name": "source-ptc-fixture",
                    "version": "1.0.0",
                    "type": "module",
                    "peerDependencies": {"@deepseek-ai/dsh-tools": "*"},
                    "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
                }
            )
        )
        (bundle / "cordis.patch.yml").write_text(
            json.dumps(
                [{"insert": [{"id": "source-ptc-fixture", "name": "./ptc.mjs"}]}]
            )
        )
        (bundle / "ptc.mjs").write_text(
            "export const name='source-ptc-fixture';export const inject=['tools'];"
            "export function apply(ctx){ctx.tools.presentAs('both');}"
        )
        control = {
            "id": case_id,
            "policy": policy,
            "source_mode": True,
            "target": conversation,
            "plan": ["503", "allow"],
            "delegate": epoch == "same",
            "ptc": flow == "ptc",
            "held": flow == "ptc" and epoch == "same",
            "bundle": str(bundle),
        }
        httpx.post(url + "/control", json=control).raise_for_status()
        message = client.send_message(
            conversation,
            f"RETRY_CASE_{case_id} SOURCE_USER_START "
            + "source evidence " * 500
            + " SOURCE_USER_END",
        )
        if control["held"]:
            poll_until(
                lambda: client.list_messages(conversation),
                lambda rows: any(
                    f"SOURCE_PROPOSAL_{case_id}" in str(r.get("content", ""))
                    for r in rows
                ),
                timeout=60,
                desc="first proposal actually sent",
            )
            newer = client.send_message(
                conversation, f"Reconsider the proposed draft RETRY_CASE_{case_id}."
            )
            database = next((root / ".dsh-runtime").glob("*/global.sqlite3"))

            def admitted():
                # Observe real relay ingestion read-only, never create a source
                # row or bypass unread revalidation with a fabricated result.
                with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                    return any(
                        json.loads(row[0])["message"]["id"] == newer
                        for row in db.execute(
                            "SELECT payload FROM inbox WHERE agent_id=? AND consumed=0",
                            (agent_id,),
                        )
                    )

            poll_until(
                admitted, bool, timeout=10, desc="new human message in host Inbox"
            )
            httpx.post(url + "/release", json={"id": case_id}).raise_for_status()
        if epoch in ("restart", "compact"):
            poll_until(
                lambda: client.list_messages(conversation),
                lambda rows: any(
                    f"SOURCE_PROPOSAL_{case_id}" in str(r.get("content", ""))
                    for r in rows
                ),
                timeout=60,
                desc="real proposal sent before process epoch change",
            )
            poll_until(
                lambda: client._http.get(
                    f"/im/v1/agents/{agent_id}/work", headers=client._auth_headers
                ).json(),
                lambda view: (
                    view.get("main_execution") == "idle" and bool(view.get("turns"))
                ),
                timeout=30,
                desc="public main terminal before orderly restart",
            )
            if epoch == "restart":
                node = client.wait_for_online_node()
                ports = _parse_ports_env(root / ".e2e-ports.env")
                generation = restart_gateway(str(root), str(ports["IM_PORT"]))
                client.wait_for_node_reconnect(
                    node_id=node, replacement_started_after=generation
                )
            else:
                client.send_message(
                    conversation,
                    "/compact Keep only the task objective, not raw source bodies.",
                )
                client.wait_for_agent_reply_with(conversation, "已压缩", timeout=60)
            httpx.post(
                url + "/control",
                json={
                    **control,
                    "delegate": True,
                    "resumed": True,
                    "compacted": epoch == "compact",
                },
            ).raise_for_status()
            client.send_message(
                conversation,
                f"Continue the earlier observed task RETRY_CASE_{case_id}.",
            )
        poll_until(
            lambda: client.list_messages(conversation),
            lambda rows: any(
                f"SOURCE_DONE_{case_id}" in str(r.get("content", "")) for r in rows
            ),
            timeout=120,
            desc="real global source journey and child completion",
        )
        records = [
            r
            for r in httpx.get(url + "/records").json()
            if r["review"] and r["action_effect"]
        ]
        rows = approvals(root, f"effect-{case_id}")
        export = {
            "input_message": message,
            "conversation": conversation,
            "records": records,
            "approvals": rows,
        }
        (tmp_path / "source-recovery-export.json").write_text(
            json.dumps(export, ensure_ascii=False, indent=2)
        )
        assert any(r["decision"] == "allow" for r in rows), export
        effects = workspace / "retry-effects.txt"
        assert effects.read_text().splitlines().count(case_id) == 1
        assert records[0]["selected"] == "503"
        assert records[1]["selected"] == "allow"
        # Per-source assertions deliberately inspect the real reviewer request,
        # not a reconstructed source fixture or an authorization database query.
        text = json.dumps(records, ensure_ascii=False)
        assert "LIBRARY_OUTSIDE_EFFECTIVE_CONTEXT" not in text
        if epoch == "compact":
            first, recovered = [projected_rows(r) for r in records]
            assert first == recovered
            observed = [r for r in first if r.get("inbox_result", {}).get("messages")]
            assert len(observed) == 1 and observed[0]["observation"] == "live"
            assert observed[0]["inbox_result"]["messages"][0]["id"] != message
            assert message not in text
            assert "SOURCE_USER_START" not in text and "SOURCE_USER_END" not in text
            assert f"SOURCE_PROPOSAL_{case_id}" not in text
            assert f"SUMMARY_RETRY_CASE_{case_id}" in text
            assert (
                next(r["recovery"] for r in rows if r.get("recovery"))["retriesUsed"]
                == 1
            )
            return
        assert message in text
        assert "SOURCE_USER_START" in text and "SOURCE_USER_END" in text
        expected_observation = "live" if epoch == "same" else "restored"
        first, recovered = [projected_rows(r) for r in records]
        first_inbox = [r for r in first if r.get("inbox_result", {}).get("messages")]
        recovered_inbox = [
            r for r in recovered if r.get("inbox_result", {}).get("messages")
        ]
        assert first_inbox == recovered_inbox
        if epoch == "restart" or control["held"]:
            assert len(first_inbox) == (4 if flow == "ptc" else 3)
            resumed = [
                r
                for r in first_inbox
                if r["inbox_result"]["messages"][0]["id"] != message
            ]
            assert len(resumed) == 1 and resumed[0]["observation"] == "live"
            first_inbox = [
                r
                for r in first_inbox
                if r["inbox_result"]["messages"][0]["id"] == message
            ]
        assert len(first_inbox) == (3 if flow == "ptc" else 2)
        assert all(r["observation"] == expected_observation for r in first_inbox)
        assert sorted(
            r["inbox_result"]["messages"][0]["part"] for r in first_inbox
        ) == ([1, 1, 2] if flow == "ptc" else [1, 2])
        assert len({r["id"] for r in first_inbox}) == len(first_inbox)
        assert all(
            r["inbox_result"]["messages"][0]["id"] == message for r in first_inbox
        )
        assert all(
            r["inbox_result"]["messages"][0]["sender"]["type"] == "user"
            for r in first_inbox
        )
        assert all(
            r["inbox_result"]["messages"][0]["sender"]["is_owner"] for r in first_inbox
        )
        assert all(r["inbox_result"]["delivery"] == "participant" for r in first_inbox)
        if policy == "codex":
            source_ids = {r["id"] for r in first_inbox}
            assert not any(
                r.get("id") in source_ids and "tool_result" in r for r in first
            )
        assert any(
            r.get("send_message_result", {}).get("status") == "sent" for r in first
        )
        if control["held"]:
            assert any(
                r.get("send_message_result", {}).get("status")
                == "held_for_revalidation"
                for r in first
            )
            assert not any(
                f"SOURCE_HELD_PROPOSAL_{case_id}" in str(r.get("content", ""))
                for r in client.list_messages(conversation)
            )
        if flow == "ptc":
            assert any(":ptc:" in str(r.get("id")) for r in first_inbox)
        assert (
            next(r["recovery"] for r in rows if r.get("recovery"))["retriesUsed"] == 1
        )
        assert "partial" in text and "next_cursor" in text
        assert f"SOURCE_PROPOSAL_{case_id}" in text
        assert "sent" in text
