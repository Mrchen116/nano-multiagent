import io
import json
import os
import socket
from pathlib import Path

import httpx
import pytest

from nano_multiagent.apps.coding_cli.main import run_cli


def _llm_proxy_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4000/health", timeout=1.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.e2e
def test_cli_managed_mode_can_complete_live_agent_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run live proxy e2e tests")
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_CLI_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 to run live managed-cli e2e tests")
    if not _llm_proxy_available():
        pytest.skip("LLM_PROXY is unavailable on http://127.0.0.1:4000")

    repo_root = Path(__file__).resolve().parents[2]
    existing_pythonpath = os.getenv("PYTHONPATH", "").strip()
    merged_pythonpath = str(repo_root / "src")
    if existing_pythonpath:
        merged_pythonpath = f"{merged_pythonpath}{os.pathsep}{existing_pythonpath}"
    monkeypatch.setenv("PYTHONPATH", merged_pythonpath)
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("NANO_MULTIAGENT_API_TIMEOUT_SECONDS", "120")

    port = _pick_free_port()
    base_args = [
        "--mode",
        "managed",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--token",
        "test-token",
        "--llm-provider",
        "anthropic",
        "--llm-model",
        "codexOAuth:gpt-5.2-codex",
        "--llm-base-url",
        "http://127.0.0.1:4000",
    ]

    create_output = io.StringIO()
    create_exit_code = run_cli(
        [*base_args, "create-session", "--title", "m84-live-managed"],
        stdout=create_output,
    )
    assert create_exit_code == 0
    session_payload = json.loads(create_output.getvalue())
    session_id = str(session_payload["session_id"])

    message_output = io.StringIO()
    message_exit_code = run_cli(
        [*base_args, "send-message", "--session-id", session_id, "--text", "reply one word: pong"],
        stdout=message_output,
    )
    assert message_exit_code == 0
    message_payload = json.loads(message_output.getvalue())

    assert message_payload.get("message", {}).get("role") == "assistant"
    content = str(message_payload.get("message", {}).get("content", "")).lower()
    assert "pong" in content
