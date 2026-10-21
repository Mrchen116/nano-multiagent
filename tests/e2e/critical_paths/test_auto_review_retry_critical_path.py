"""Controlled real-IM HTTP approval, effects and audit; not vendor acceptance."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest
import yaml

from ._im_client import IMClient
from ._im_polling import poll_until
from .conftest import _parse_ports_env

REPO = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.e2e


@contextmanager
def running(
    tmp_path: Path,
    policy: str,
    *,
    work_mode="single_thread",
    tools=None,
    review_window=258400,
    agent_ids=None,
):
    """Own a fixture and a complete isolated stack, including startup-failure cleanup."""
    if os.environ.get("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 for isolated process E2E")
    ready = tmp_path / "fixture-ready.json"
    record = tmp_path / "fixture.jsonl"
    proc = subprocess.Popen(
        [
            sys.executable,
            str(REPO / "scripts/fixtures/anthropic_sse_auto_review_retry.py"),
            "--ready-file",
            str(ready),
            "--record",
            str(record),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    root = tmp_path / "stack"
    root.mkdir()
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
    }
    client = None
    try:
        poll_until(
            lambda: ready.exists() or proc.poll() is not None,
            bool,
            timeout=10,
            desc="HTTP fixture readiness",
        )
        assert proc.poll() is None
        port = json.loads(ready.read_text())["port"]
        fixture_url = f"http://127.0.0.1:{port}"
        config = yaml.safe_load((REPO / "config/e2e/gateway.yaml").read_text())
        if agent_ids is not None:
            config["agents"] = [
                agent for agent in config["agents"] if agent["agent_id"] in agent_ids
            ]
        for agent in config["agents"]:
            agent.update(
                default_model="main",
                tool_allowlist=tools or ["bash"],
                work_mode=work_mode,
            )
        config["llm"] = {
            "default_model": "main",
            "tool_approval_model": "review",
            "providers": [
                {
                    "name": "anthropic",
                    "base_url": fixture_url,
                    "models": [
                        {
                            "name": model,
                            "context_window": review_window
                            if model == "review"
                            else 258400,
                            "reasoning": {"default": "low", "levels": ["low"]},
                        }
                        for model in ("main", "review")
                    ],
                }
            ],
        }
        source = tmp_path / "source.yaml"
        source.write_text(yaml.safe_dump(config, sort_keys=False))
        owner = root / ".gateway-owner"
        owner.mkdir()
        (owner / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "auto_mode": {
                        "enabled": True,
                        "rules": policy,
                        "dangerously_skip_permissions": False,
                        "unattended_fallback": "deny",
                    }
                }
            )
        )
        up = subprocess.run(
            [
                "bash",
                str(REPO / "scripts/e2e-up.sh"),
                "--wt",
                str(root),
                "--main-config",
                str(source),
            ],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        assert up.returncode == 0, up.stdout + up.stderr
        ports = _parse_ports_env(root / ".e2e-ports.env")
        client = IMClient(ports["IM_URL"])
        client.register_or_login("nano", "nano1234")
        client.wait_for_online_node()
        yield client, root, fixture_url
    finally:
        if client:
            client.close()
        down = subprocess.run(
            ["bash", str(REPO / "scripts/e2e-down.sh"), "--wt", str(root)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        assert down.returncode == 0, down.stdout + down.stderr
        if (root / ".e2e-ports.env").exists():
            url = _parse_ports_env(root / ".e2e-ports.env")["IM_URL"]
            with pytest.raises(httpx.ConnectError):
                httpx.get(url + "/health", timeout=2, trust_env=False)


def approvals(root: Path, call_id: str) -> list[dict]:
    """Read only this test's durable approval domain, filtering by original tool call."""
    rows = []
    for path in (root / ".dsh-runtime").glob(
        "**/storages/nano_approval/sessions/*.json"
    ):
        rows.extend(
            row
            for row in json.loads(path.read_text())["record"]
            if row["callId"] == call_id
        )
    return rows


@pytest.mark.parametrize("policy", ["nano", "codex"])
@pytest.mark.timeout(180)
def test_auto_review_http_recovery_reaches_im_and_executes_once(
    tmp_path: Path, policy: str
):
    """Observe recovery, shared format allowance and final deny at the actual user entry."""
    cases = [
        ("success", ["503", "allow"], 2, 1, 0, True),
        ("mixed", ["503", "malformed", "allow"], 3, 2, 1, True),
        ("twiceformat", ["malformed", "malformed", "allow"], 2, 1, 1, False),
        ("deny", ["deny", "deny", "allow"], 2 if policy == "nano" else 1, 0, 0, False),
        ("limited", ["429", "allow"], 2, 1, 0, True),
        ("permanent", ["401", "allow"], 1, 0, 0, False),
        ("longdelay", ["429long", "allow"], 1, 0, 0, False),
        ("exhausted", ["503", "503", "503", "allow"], 3, 2, 0, False),
        ("empty", ["empty", "allow"], 2, 1, 1, True),
    ]
    if policy == "nano":
        cases.append(("secondstage", ["deny", "503", "allow"], 3, 1, 0, True))
    else:
        cases.append(("inspection", ["inspect", "503", "allow"], 3, 1, 0, True))
    with running(tmp_path, policy) as (client, root, fixture_url):
        evidence = []
        workspace = root / ".gateway-workspace/e2e"
        workspace.mkdir(exist_ok=True, parents=True)
        (workspace / "inspection.txt").write_text("FAILED_REVIEW_BRANCH")
        for name, plan, count, retries, formats, allowed in cases:
            case_id = f"{policy}_{name}"
            httpx.post(
                fixture_url + "/control",
                json={"id": case_id, "policy": policy, "plan": plan},
            ).raise_for_status()
            conversation = client.create_direct_conversation("e2e")
            ws = client.connect_ws()
            try:
                input_id = client.send_message(
                    conversation,
                    f"Run exactly one isolated bash fixture action RETRY_CASE_{case_id}; if denied do not reissue it.",
                )
                if name in ("twiceformat", "permanent", "longdelay", "exhausted"):
                    frame = ws.wait_for_event(
                        "permission.request",
                        lambda event: (
                            event.conversation_id == conversation
                            and case_id in json.dumps(event.data)
                        ),
                        timeout=90,
                    )
                    client.resolve_permission(
                        conversation,
                        frame.data["permission_request"]["request_id"],
                        frame.data["message_id"],
                        "deny",
                    )
                poll_until(
                    lambda: client.list_messages(conversation),
                    lambda messages: any(
                        f"FINISHED_RETRY_CASE_{case_id}"
                        in str(message.get("content", ""))
                        for message in messages
                    ),
                    timeout=90,
                    desc=f"completed fixture response {case_id}",
                )
            finally:
                ws.close()
            rows = poll_until(
                lambda: approvals(root, f"effect-{case_id}"),
                lambda rows: any(row.get("recovery") for row in rows),
                timeout=10,
                desc="durable recovery summary",
            )
            trace = next(row["recovery"] for row in rows if row.get("recovery"))
            records = [
                row
                for row in httpx.get(fixture_url + "/records").json()
                if row["review"] and row["case"] == case_id
            ]
            assert len(records) == count
            assert trace["retriesUsed"] == retries
            assert trace["formatRetriesUsed"] == formats
            effects = root / ".gateway-workspace/e2e/retry-effects.txt"
            lines = effects.read_text().splitlines() if effects.exists() else []
            assert lines.count(case_id) == int(allowed)
            if name in ("success", "limited"):
                assert records[1]["time"] - records[0]["time"] >= 0.95
            if policy == "codex" and retries:
                assert len({row["session"] for row in records}) >= 2
            if name == "inspection":
                assert [row["failed_history"] for row in records] == [
                    False,
                    True,
                    False,
                ]
                assert (
                    records[0]["session"]
                    == records[1]["session"]
                    != records[2]["session"]
                )
            assert all(row["effort"] == "low" for row in records)
            evidence.append(
                {
                    "case": case_id,
                    "conversation": conversation,
                    "message": input_id,
                    "trace": trace,
                    "records": records,
                    "effects": int(allowed),
                }
            )
        (tmp_path / "approval-export.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2)
        )


@pytest.mark.parametrize("policy", ["nano", "codex"])
@pytest.mark.parametrize("phase", ["request", "backoff"])
@pytest.mark.timeout(120)
def test_auto_review_public_stop_never_allows_or_retries(
    tmp_path: Path, policy: str, phase: str
):
    """Send the real user's /stop while reviewer HTTP or Retry-After is in progress."""
    with running(tmp_path, policy) as (client, root, fixture_url):
        case_id = f"{policy}_stop_{phase}"
        plan = ["timeout", "allow"] if phase == "request" else ["429stop", "allow"]
        httpx.post(
            fixture_url + "/control",
            json={"id": case_id, "policy": policy, "plan": plan},
        ).raise_for_status()
        conversation = client.create_direct_conversation("e2e")
        client.send_message(
            conversation, f"Run one isolated bash action RETRY_CASE_{case_id}."
        )
        records_for_case = lambda: [
            row
            for row in httpx.get(fixture_url + "/records").json()
            if row["review"] and row["case"] == case_id
        ]
        poll_until(
            records_for_case,
            bool,
            timeout=30,
            interval=0.02,
            desc="in-flight real reviewer HTTP",
        )
        stop_message = client.send_message(conversation, "/stop")
        rows = poll_until(
            lambda: approvals(root, f"effect-{case_id}"),
            lambda rows: any(row.get("decision") == "cancelled" for row in rows),
            timeout=15,
            interval=0.1,
            desc="cancelled review audit",
        )
        trace = next(row["recovery"] for row in rows if row.get("recovery"))
        assert trace["finalRoute"] == "cancel" and trace["complete"] is True
        assert trace["terminalReason"] == "cancelled"
        assert all(row["decision"] != "allow" for row in rows)
        assert all(row["total"] == 0 and row["consecutive"] == 0 for row in rows)
        # Pass the original server backoff boundary; no later HTTP may be issued.
        time.sleep(8.5 if phase == "backoff" else 0.5)
        assert len(records_for_case()) == 1
        effects = root / ".gateway-workspace/e2e/retry-effects.txt"
        assert not effects.exists() or case_id not in effects.read_text()
        (tmp_path / "stop-export.json").write_text(
            json.dumps(
                {
                    "trace": trace,
                    "approvals": rows,
                    "requests": records_for_case(),
                    "stop": stop_message,
                    "conversation": conversation,
                },
                indent=2,
            )
        )


@pytest.mark.parametrize("policy", ["nano", "codex"])
@pytest.mark.slow
@pytest.mark.timeout(240)
def test_auto_review_real_default_deadline_recovers_once(tmp_path: Path, policy: str):
    """Keep production 30/90-second judgment budgets on the genuine user-facing path."""
    with running(tmp_path, policy) as (client, root, fixture_url):
        case_id = f"{policy}_deadline"
        httpx.post(
            fixture_url + "/control",
            json={"id": case_id, "policy": policy, "plan": ["timeout", "allow"]},
        ).raise_for_status()
        conversation = client.create_direct_conversation("e2e")
        client.send_message(
            conversation,
            f"Run one isolated bash action RETRY_CASE_{case_id}. Do not issue it again after denial.",
        )
        poll_until(
            lambda: client.list_messages(conversation),
            lambda messages: any(
                f"FINISHED_RETRY_CASE_{case_id}" in str(message.get("content", ""))
                for message in messages
            ),
            timeout=420,
            desc="real default reviewer deadline recovery",
        )
        rows = approvals(root, f"effect-{case_id}")
        trace = next(row["recovery"] for row in rows if row.get("recovery"))
        records = [
            row
            for row in httpx.get(fixture_url + "/records").json()
            if row["review"] and row["case"] == case_id
        ]
        assert len(records) == 2
        budget = 30 if policy == "nano" else 90
        assert records[1]["time"] - records[0]["time"] >= budget
        assert trace["retriesUsed"] == 1
        assert trace["attempts"][0]["category"] == "review_timeout"
        assert trace["attempts"][0]["budgetMs"] == budget * 1000
        assert trace["attempts"][1]["budgetMs"] == budget * 1000
        lines = (
            (root / ".gateway-workspace/e2e/retry-effects.txt").read_text().splitlines()
        )
        assert lines.count(case_id) == 1
        (tmp_path / "deadline-export.json").write_text(
            json.dumps(
                {"trace": trace, "records": records, "conversation": conversation},
                indent=2,
            )
        )
