"""Cross-process recovery for Gateway-owned session continuity state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest


_HELPER = "tests.e2e.critical_paths._session_continuity_partial_recovery"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until(predicate, *, timeout: float = 15.0) -> object:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out waiting for continuity recovery condition")


def _helper_command(mode: str, runtime: Path, *args: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        _HELPER,
        mode,
        "--runtime",
        str(runtime),
        *args,
    ]


@pytest.mark.e2e
def test_pending_shadow_and_control_recover_once_after_gateway_process_loss(
    tmp_path: Path,
) -> None:
    """Kill A after durable commit; B resumes both visible journeys exactly once."""

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    port = _free_port()
    im_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            (
                str(Path(__file__).resolve().parents[3]),
                str(Path(__file__).resolve().parents[3] / "src"),
            )
        ),
        "IM_JWT_SECRET": "continuity-e2e-secret-at-least-32-bytes",
    }
    initialized = subprocess.run(
        _helper_command("initialize-im", runtime),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    identity = json.loads(initialized.stdout)
    im_log = (runtime / "im.log").open("w", encoding="utf-8")
    im_process = subprocess.Popen(
        _helper_command("serve-im", runtime, "--port", str(port)),
        env=env,
        stdout=im_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    headers = {"Authorization": f"Bearer {identity['token']}"}
    try:
        _wait_until(
            lambda: _im_ready(im_url, headers),
            timeout=30,
        )
        common = (
            "--im-url",
            im_url,
            "--token",
            identity["token"],
            "--owner-id",
            identity["owner_id"],
        )
        gateway_a = subprocess.Popen(
            _helper_command("stage-a", runtime, *common),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        barrier_path = runtime / "barrier-state.json"
        committed = _wait_until(
            lambda: (
                state
                if (state := _read_json(barrier_path)).get("durable_commit_reached")
                and state.get("external_send_blocked")
                else None
            ),
            timeout=15,
        )
        gateway_a.terminate()
        gateway_a.wait(timeout=10)
        assert gateway_a.returncode is not None

        barrier_path.write_text(
            json.dumps({**committed, "allow_remote_delivery": True}),
            encoding="utf-8",
        )
        recovered = subprocess.run(
            _helper_command("recover-b", runtime, *common),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        recovery = json.loads(recovered.stdout)

        ledger = [
            json.loads(line)
            for line in (runtime / "fake-external-chat.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        assert [item["type"] for item in ledger].count("control_confirmation") == 1
        assert [item["type"] for item in ledger].count("boundary_applied") == 1
        assert (
            recovery["current_control_session_id"]
            != committed["old_control_session_id"]
        )
        assert (
            recovery["next_message_session_id"] == committed["new_control_session_id"]
        )

        conversations = (
            httpx.get(f"{im_url}/im/v1/conversations", headers=headers, timeout=5)
            .raise_for_status()
            .json()["items"]
        )
        by_external_chat = {
            item.get("external_chat_id"): item for item in conversations
        }
        assert {"shadow-boundary-chat", "control-chat"} <= set(by_external_chat)
        boundary_messages = _messages(
            im_url, headers, by_external_chat["shadow-boundary-chat"]["id"]
        )
        control_messages = _messages(
            im_url, headers, by_external_chat["control-chat"]["id"]
        )
        assert [item["content"] for item in boundary_messages].count(
            "boundary user message"
        ) == 1
        assert [item["content"] for item in control_messages].count("/new") == 1
        assert [item["content"] for item in control_messages].count(
            "已开始新会话。"
        ) == 1
        assert (runtime / "session_bindings.sqlite3").is_file()
        assert (runtime / "external_shadow_sagas.sqlite3").is_file()
    finally:
        im_process.terminate()
        try:
            im_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            im_process.kill()
            im_process.wait(timeout=5)
        im_log.close()


def _im_ready(im_url: str, headers: dict[str, str]) -> bool:
    try:
        response = httpx.get(f"{im_url}/im/v1/nodes", headers=headers, timeout=0.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _messages(
    im_url: str, headers: dict[str, str], conversation_id: str
) -> list[dict[str, object]]:
    response = httpx.get(
        f"{im_url}/im/v1/conversations/{conversation_id}/messages",
        headers=headers,
        timeout=5,
    )
    response.raise_for_status()
    return [
        item["message"]
        for item in response.json()["items"]
        if item["type"] == "message"
    ]
