"""Owned real IM/Node/HTTP harness shared by automatic-review journeys."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

from ._im_client import IMClient
from .conftest import E2EStack, _dump_logs, _parse_ports_env
from .test_tool_approval_model_critical_path import _wait_stub

_ROOT = Path(__file__).resolve().parents[3]
_STUB = _ROOT / "scripts/fixtures/anthropic_sse_auto_review_retry.py"
_EXPORT = _ROOT / "scripts/fixtures/export_review_trace.py"


@contextmanager
def _stack(
    tmp_path: Path, *, profile: str = "basic", fallback: str = "deny"
) -> Iterator[tuple[E2EStack, Path]]:
    port = subprocess.check_output(
        [str(_ROOT / "scripts/free-ports.sh"), "1"], text=True
    ).strip()
    records = tmp_path / "requests.jsonl"
    proc = subprocess.Popen(
        [sys.executable, str(_STUB), port],
        env={**os.environ, "NANO_FIXTURE_RECORD_PATH": str(records)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    runtime = tmp_path / "stack"
    runtime.mkdir()
    try:
        _wait_stub(proc, int(port))
        config = yaml.safe_load((_ROOT / "config/e2e/gateway.yaml").read_text())
        config["agents"] = config["agents"][:2]
        for agent, policy in zip(config["agents"], ("cc", "codex"), strict=True):
            agent.update(
                default_model="main", approval_mode=policy, tool_allowlist=["bash"]
            )
            if profile != "basic":
                agent["work_mode"] = (
                    "global" if profile == "global" else "single_thread"
                )
                agent["tool_allowlist"] += [
                    "send_message",
                    "subagent",
                    "schedule_create",
                ]
                if profile == "heartbeat":
                    agent["tool_allowlist"].append("read")
                if profile == "schedule":
                    agent["tool_allowlist"] += [
                        "schedule_list",
                        "schedule_update",
                        "schedule_delete",
                        "schedule_run",
                        "schedule_history",
                    ]
                workspace = (
                    runtime
                    / ".gateway-workspace"
                    / agent["agent_id"]
                    / ".nanoassistant"
                )
                workspace.mkdir(parents=True)
                (workspace / "config.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "auto_mode": {
                                "enabled": True,
                                "dangerously_skip_permissions": False,
                                "unattended_fallback": fallback,
                            }
                        }
                    )
                )
            agent["features"] = {
                "intelligent_ui": False,
                "task_graph": False,
                "memory_curation": False,
                "skill_creation": False,
                "heartbeat": False,
                "cron_scheduling": profile == "schedule",
            }
        config["llm"] = {
            "default_model": "main",
            "tool_approval_model": "review",
            "providers": [
                {
                    "name": "anthropic",
                    "base_url": f"http://127.0.0.1:{port}",
                    "models": [
                        {"name": name, "context_window": 200000}
                        for name in ("main", "review")
                    ],
                }
            ],
        }
        source = tmp_path / "fixture-config.yaml"
        source.write_text(yaml.safe_dump(config, sort_keys=False))
        up = subprocess.run(
            [
                "bash",
                str(_ROOT / "scripts/e2e-up.sh"),
                "--wt",
                str(runtime),
                "--main-config",
                str(source),
            ],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
            },
            timeout=180,
        )
        if up.returncode:
            _dump_logs(runtime)
            pytest.fail(f"isolated stack failed: {up.stdout}\n{up.stderr}")
        ports = _parse_ports_env(runtime / ".e2e-ports.env")
        yield (
            E2EStack(
                im_url=ports["IM_URL"],
                im_port=ports["IM_PORT"],
                node_id=ports["NODE_ID"],
                wt_dir=str(runtime),
                llm_model="main",
            ),
            records,
        )
    finally:
        down = subprocess.run(
            ["bash", str(_ROOT / "scripts/e2e-down.sh"), "--wt", str(runtime)],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if down.returncode:
            pytest.fail(f"isolated cleanup failed: {down.stdout}\n{down.stderr}")


def _records(path: Path, case: str) -> list[dict]:
    return (
        [
            row
            for line in path.read_text().splitlines()
            if (row := json.loads(line))["case"] == case
        ]
        if path.exists()
        else []
    )


def _trace(stack: E2EStack, case: str) -> dict:
    result = subprocess.check_output(
        [
            sys.executable,
            str(_EXPORT),
            "--runtime",
            stack.wt_dir,
            "--call-id",
            f"retry-{case}",
            "--sha",
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True
            ).strip(),
        ],
        text=True,
    )
    rows = json.loads(result)["rows"]
    traces = [row for row in rows if "recovery" in row]
    assert len(traces) == 1, rows
    # Export is deliberately independent of model prompts/reason strings.
    assert all("reason" not in row and "entries" not in row for row in rows)
    return traces[0]


def _login(stack: E2EStack) -> IMClient:
    client = IMClient(stack.im_url)
    client.register_or_login("nano", "nano1234")
    client.wait_for_online_node()
    return client
