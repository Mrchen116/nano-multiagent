"""Neutral true-IM context-rebuild/recovery observation driver for feat-625.

The provider is controlled HTTP, not a real vendor. Nothing injects an approval,
source label or cursor. Raw request bodies and durable approval exports remain in
pytest's isolated temporary root for an independent reviewer to inspect.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ._im_polling import poll_until
from .test_auto_review_retry_critical_path import approvals, running

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("recovered", ["allow", "context"])
@pytest.mark.timeout(180)
def test_guardian_context_rebuild_service_recovery_and_next_delta(
    tmp_path: Path, recovered: str
):
    """Warm a real cache, overflow its delta, fail rebuild HTTP, then replay full."""
    case_id = f"codex_context_chain_{recovered}"
    with running(tmp_path, "codex") as (client, root, fixture_url):
        httpx.post(
            fixture_url + "/control",
            json={
                "id": case_id,
                "policy": "codex",
                "steps": True,
                "plan": ["allow", "context", "503", recovered, "allow"],
            },
        ).raise_for_status()
        conversation = client.create_direct_conversation("e2e")
        exported = []
        for step in range(3):
            ws = client.connect_ws()
            try:
                message = client.send_message(
                    conversation,
                    f"Perform exactly one bash action RETRY_CASE_{case_id} EFFECT_STEP_{step}. "
                    "Do not reissue after denial.",
                )
                if step == 1 and recovered == "context":
                    frame = ws.wait_for_event(
                        "permission.request",
                        lambda e: e.conversation_id == conversation,
                        timeout=60,
                    )
                    client.resolve_permission(
                        conversation,
                        frame.data["permission_request"]["request_id"],
                        frame.data["message_id"],
                        "deny",
                    )
            finally:
                ws.close()
            marker = f"FINISHED_RETRY_CASE_{case_id}_STEP_{step}"
            poll_until(
                lambda: client.list_messages(conversation),
                lambda messages: any(
                    marker in str(m.get("content", "")) for m in messages
                ),
                timeout=60,
                desc=f"context combination step {step}",
            )
            rows = approvals(root, f"effect-{case_id}-{step}")
            if step == 1 and recovered == "context":
                assert any(row["decision"] == "no_verdict" for row in rows), rows
                assert all(row["decision"] != "allow" for row in rows), rows
            else:
                assert any(row["decision"] == "allow" for row in rows), rows
            exported.append({"step": step, "message": message, "approvals": rows})
        records = [
            r
            for r in httpx.get(fixture_url + "/records").json()
            if r["review"] and r["case"] == case_id
        ]
        (tmp_path / "context-combination-export.json").write_text(
            json.dumps(
                {
                    "conversation": conversation,
                    "steps": exported,
                    "requests": records,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        assert [r["selected"] for r in records] == [
            "allow",
            "context",
            "503",
            recovered,
            "allow",
        ]
        trace = next(
            r["recovery"] for r in exported[1]["approvals"] if r.get("recovery")
        )
        assert trace["contextRebuilds"] == 1
        assert trace["retriesUsed"] == 1
        assert trace["formatRetriesUsed"] == 0
        # Context rebuild and technical recovery must each have fresh native identity.
        assert records[0]["session"] == records[1]["session"]
        assert len({r["session"] for r in records[1:4]}) == 3
        if recovered == "allow":
            assert records[3]["session"] == records[4]["session"]
        else:
            assert records[3]["session"] != records[4]["session"]
            assert trace["terminalReason"] == "context"
        # A full replay contains the earlier human evidence; the next successful
        # cache reuse is a real delta, not a replay of all prior rows.
        assert "EFFECT_STEP_0" in json.dumps(records[3]["messages"])
        latest = records[4]["messages"][-1]
        assert "EFFECT_STEP_2" in json.dumps(records[4]["messages"])
        if recovered == "allow":
            assert "EFFECT_STEP_2" in json.dumps(latest)
            assert "EFFECT_STEP_0" not in json.dumps(latest)
        effects = root / ".gateway-workspace/e2e/retry-effects.txt"
        assert effects.read_text().splitlines().count(case_id) == (
            3 if recovered == "allow" else 2
        )


@pytest.mark.timeout(120)
def test_guardian_required_action_admission_never_retries_or_truncates(tmp_path: Path):
    """A complete action cannot fit: unavailable, no provider HTTP and no effect."""
    case_id = "codex_required_action"
    with running(tmp_path, "codex", review_window=20000, agent_ids=["e2e"]) as (
        client,
        root,
        url,
    ):
        httpx.post(
            url + "/control",
            json={
                "id": case_id,
                "policy": "codex",
                "plan": ["allow"],
                "action_size": 5000,
            },
        ).raise_for_status()
        conversation = client.create_direct_conversation("e2e")
        ws = client.connect_ws()
        try:
            message = client.send_message(
                conversation, f"One controlled fixture action RETRY_CASE_{case_id}."
            )
            frame = ws.wait_for_event(
                "permission.request",
                lambda e: e.conversation_id == conversation,
                timeout=60,
            )
            client.resolve_permission(
                conversation,
                frame.data["permission_request"]["request_id"],
                frame.data["message_id"],
                "deny",
            )
            poll_until(
                lambda: client.list_messages(conversation),
                lambda rows: any(
                    f"FINISHED_RETRY_CASE_{case_id}" in str(r.get("content", ""))
                    for r in rows
                ),
                timeout=30,
                desc="admission failure returns through ordinary fallback",
            )
        finally:
            ws.close()
        rows = approvals(root, f"effect-{case_id}")
        trace = next(r["recovery"] for r in rows if r.get("recovery"))
        requests = [r for r in httpx.get(url + "/records").json() if r["review"]]
        (tmp_path / "required-admission-export.json").write_text(
            json.dumps(
                {
                    "message": message,
                    "conversation": conversation,
                    "approvals": rows,
                    "requests": requests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        assert trace["terminalReason"] == "context_required"
        assert trace["retriesUsed"] == 0 and trace["formatRetriesUsed"] == 0
        assert requests == []
        assert any(r["decision"] == "no_verdict" for r in rows)
        assert all(r["decision"] != "allow" for r in rows)
        effects = root / ".gateway-workspace/e2e/retry-effects.txt"
        assert not effects.exists() or case_id not in effects.read_text()
