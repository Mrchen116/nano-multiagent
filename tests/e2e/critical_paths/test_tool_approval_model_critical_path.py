"""Real PA/IM/Gateway path for build-scoped automatic tool approval models."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import yaml

from ._im_client import IMClient, restart_gateway
from .conftest import E2EStack, _dump_logs, _parse_ports_env, _selected_llm_model


_REPO_ROOT = Path(__file__).resolve().parents[3]
_E2E_UP = _REPO_ROOT / "scripts/e2e-up.sh"
_E2E_DOWN = _REPO_ROOT / "scripts/e2e-down.sh"
_FREE_PORTS = _REPO_ROOT / "scripts/free-ports.sh"
_STUB = _REPO_ROOT / "scripts/fixtures/anthropic_sse_tool_approval_recording.py"
_E2E_CONFIG = _REPO_ROOT / "config/e2e/gateway.yaml"
_MODELS = ("model-a", "model-b", "model-c", "model-d", "approval-fail")


@dataclass
class ApprovalStack(E2EStack):
    """One isolated true-process stack backed by the approval recording stub."""

    record_path: str
    stub_port: int


def _write_config(
    destination: Path,
    stub_url: str,
    *,
    tool_approval_model: str | None,
) -> None:
    config = yaml.safe_load(_E2E_CONFIG.read_text(encoding="utf-8"))
    config["agents"][0]["default_model"] = "model-a"
    config["agents"][1]["default_model"] = "model-b"
    for agent in config["agents"]:
        agent["tool_allowlist"] = ["write"]
    config["llm"] = {
        "default_model": "model-a",
        "providers": [
            {
                "name": "anthropic",
                "base_url": stub_url,
                "models": [{"name": model} for model in _MODELS],
            }
        ],
    }
    if tool_approval_model is not None:
        config["llm"]["tool_approval_model"] = tool_approval_model
    destination.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _wait_stub(stub_proc: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if stub_proc.poll() is not None:
            error = stub_proc.stderr.read() if stub_proc.stderr else ""
            pytest.fail(f"tool approval stub exited early: {error}")
        try:
            httpx.get(f"http://127.0.0.1:{port}/", timeout=0.3)
            return
        except httpx.HTTPError:
            time.sleep(0.05)
    pytest.fail("tool approval stub did not listen in time")


@contextmanager
def _running_stack(
    tmp_path: Path, *, tool_approval_model: str | None
) -> Iterator[ApprovalStack]:
    stub_port = int(
        subprocess.check_output([str(_FREE_PORTS), "1"], text=True).split()[0]
    )
    record_path = tmp_path / "approval-requests.jsonl"
    stub_proc = subprocess.Popen(
        [sys.executable, str(_STUB), str(stub_port)],
        env={**os.environ, "NANO_FIXTURE_RECORD_PATH": str(record_path)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_stub(stub_proc, stub_port)

    main_config = tmp_path / "gateway.yaml"
    _write_config(
        main_config,
        f"http://127.0.0.1:{stub_port}",
        tool_approval_model=tool_approval_model,
    )
    wt_dir = tmp_path / "stack"
    wt_dir.mkdir()
    up = subprocess.run(
        [
            "bash",
            str(_E2E_UP),
            "--wt",
            str(wt_dir),
            "--main-config",
            str(main_config),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
        },
    )
    if up.returncode != 0:
        stub_proc.kill()
        _dump_logs(wt_dir)
        pytest.fail(f"e2e-up.sh failed (rc={up.returncode}):\n{up.stdout}\n{up.stderr}")

    values = _parse_ports_env(wt_dir / ".e2e-ports.env")
    stack = ApprovalStack(
        im_url=values["IM_URL"],
        im_port=values["IM_PORT"],
        node_id=values.get("NODE_ID", ""),
        wt_dir=str(wt_dir),
        llm_model=_selected_llm_model(wt_dir / ".gateway-config.yaml"),
        record_path=str(record_path),
        stub_port=stub_port,
    )
    try:
        yield stack
    finally:
        subprocess.run(
            ["bash", str(_E2E_DOWN), "--wt", str(wt_dir)],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        stub_proc.terminate()
        try:
            stub_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stub_proc.kill()


def _load_records(stack: ApprovalStack) -> list[dict]:
    path = Path(stack.record_path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wait_records(stack: ApprovalStack, minimum: int) -> list[dict]:
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        records = _load_records(stack)
        if len(records) >= minimum:
            return records
        time.sleep(0.2)
    raise AssertionError(
        f"expected at least {minimum} requests, got {len(_load_records(stack))}"
    )


def _login(stack: ApprovalStack) -> IMClient:
    client = IMClient(stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    return client


def _agent_ids(client: IMClient) -> tuple[str, str]:
    ids = {agent["agent_id"] for agent in client.list_agents()}
    assert {"e2e", "e2e-peer"} <= ids
    client.update_agent_config("e2e", default_model="model-a", tool_allowlist=["write"])
    client.update_agent_config(
        "e2e-peer", default_model="model-b", tool_allowlist=["write"]
    )
    return "e2e", "e2e-peer"


def _run_tool_turn(client: IMClient, stack: ApprovalStack, agent_id: str) -> list[dict]:
    before = len(_load_records(stack))
    conversation = client.create_direct_conversation(agent_id)
    ws = client.connect_ws()
    try:
        client.send_message(conversation, "请完成这次确定性工具操作。")
        ws.wait_for_event("message.completed", timeout=90.0)
    finally:
        ws.close()
    records = _wait_records(stack, before + 3)[before:]
    assert len(records) == 3, f"unexpected request count: {records!r}"
    assert [record["kind"] for record in records] == [
        "normal",
        "classifier",
        "normal",
    ]
    filename = f"approval-route-{before + 1}.txt"
    assert list((Path(stack.wt_dir) / ".gateway-workspace").rglob(filename)), (
        f"approved write did not create {filename}"
    )
    return records


def _models(records: list[dict]) -> list[str]:
    return [record["request"]["model"] for record in records]


@pytest.mark.e2e
def test_configured_model_is_unified_and_changes_only_after_restart(
    tmp_path: Path,
) -> None:
    with _running_stack(tmp_path, tool_approval_model="model-c") as stack:
        client = _login(stack)
        try:
            agent_a, agent_b = _agent_ids(client)
            assert _models(_run_tool_turn(client, stack, agent_a)) == [
                "model-a",
                "model-c",
                "model-a",
            ]
            assert _models(_run_tool_turn(client, stack, agent_b)) == [
                "model-b",
                "model-c",
                "model-b",
            ]

            generated = Path(stack.wt_dir) / ".gateway-config.yaml"
            config = yaml.safe_load(generated.read_text(encoding="utf-8"))
            config["llm"]["tool_approval_model"] = "model-d"
            generated.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            assert _models(_run_tool_turn(client, stack, agent_a)) == [
                "model-a",
                "model-c",
                "model-a",
            ]

            floor = restart_gateway(stack.wt_dir, stack.im_port)
            client.wait_for_node_reconnect(
                node_id=stack.node_id, replacement_started_after=floor
            )
            assert _models(_run_tool_turn(client, stack, agent_a)) == [
                "model-a",
                "model-d",
                "model-a",
            ]
        finally:
            client.close()


@pytest.mark.e2e
def test_omitted_model_reuses_each_agent_model(tmp_path: Path) -> None:
    with _running_stack(tmp_path, tool_approval_model=None) as stack:
        client = _login(stack)
        try:
            agent_a, agent_b = _agent_ids(client)
            assert _models(_run_tool_turn(client, stack, agent_a)) == [
                "model-a",
                "model-a",
                "model-a",
            ]
            assert _models(_run_tool_turn(client, stack, agent_b)) == [
                "model-b",
                "model-b",
                "model-b",
            ]
        finally:
            client.close()


@pytest.mark.e2e
def test_classifier_failure_escalates_without_model_fallback(tmp_path: Path) -> None:
    with _running_stack(tmp_path, tool_approval_model="approval-fail") as stack:
        client = _login(stack)
        try:
            agent_a, _ = _agent_ids(client)
            conversation = client.create_direct_conversation(agent_a)
            ws = client.connect_ws()
            try:
                client.send_message(conversation, "请完成这次确定性工具操作。")
                frame = ws.wait_for_event("permission.request", timeout=90.0)
                request = frame.data["permission_request"]
                observed = _wait_records(stack, 2)
                classifier_models = [
                    item["request"]["model"]
                    for item in observed
                    if item["kind"] == "classifier"
                ]
                assert classifier_models == ["approval-fail"]
                client.resolve_permission(
                    frame.conversation_id or conversation,
                    request["request_id"],
                    frame.data["message_id"],
                    "deny",
                )
                ws.wait_for_event("permission.resolved", timeout=60.0)
                ws.wait_for_event("message.completed", timeout=90.0)
            finally:
                ws.close()
        finally:
            client.close()


@pytest.mark.e2e
def test_unregistered_model_rejects_gateway_startup(tmp_path: Path) -> None:
    config = tmp_path / "invalid-gateway.yaml"
    _write_config(
        config,
        "http://127.0.0.1:1",
        tool_approval_model="missing-model",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "personal_assistant.main",
            "--config",
            str(config),
            "--foreground",
        ],
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "llm.tool_approval_model" in result.stdout + result.stderr
    assert "missing-model" in result.stdout + result.stderr
