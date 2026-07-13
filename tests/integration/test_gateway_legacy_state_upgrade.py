"""Real-process coverage for forward-reading legacy Gateway state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from personal_assistant.main import launch_gateway_in_background, stop_gateway


def _wait_for_path(path: Path, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            raise AssertionError(f"Gateway exited early with rc={process.returncode}")
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def _write_minimal_config(root: Path) -> Path:
    """Write one isolated foreground-capable Gateway config."""
    config_path = root / "node config 'quoted'.yaml"
    workspace = root / "workspace"
    workspace.mkdir()
    config_path.write_text(
        f"""\
node:
  node_id: legacy-upgrade-test
agents:
  - agent_id: legacy-agent
    workspace_root: {workspace}
channels: []
gateway:
  startup_timeout_seconds: 5
  shutdown_grace_seconds: 5
  poll_interval_seconds: 0.05
llm:
  default_model: anthropic:test-model
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: anthropic:test-model
""",
        encoding="utf-8",
    )
    return config_path


def test_background_start_and_stop_support_quoted_config_path(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime dir 'quoted'"
    runtime_root.mkdir()
    config_path = _write_minimal_config(runtime_root)

    result = launch_gateway_in_background(config_path=config_path)
    try:
        stopped = stop_gateway(config_path=config_path)

        assert stopped.startswith(f"STOPPED pid={result.pid}")
        assert not (runtime_root / "gateway.pid").exists()
        assert not (runtime_root / "gateway.identity.json").exists()
        assert not (runtime_root / ".gateway-state.json").exists()
    finally:
        try:
            os.killpg(result.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_public_stop_upgrades_legacy_state_across_timezone_and_quoted_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_root = tmp_path / "legacy runtime 'quoted'"
    runtime_root.mkdir()
    config_path = _write_minimal_config(runtime_root)
    log_path = runtime_root / "gateway.log"
    child_env = {
        **os.environ,
        "PYTHONPATH": str(repo_root / "src"),
        "LC_ALL": "C",
        "LANG": "C",
        "TZ": "Pacific/Honolulu",
    }
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "personal_assistant.main",
                "--config",
                str(config_path.resolve()),
                "--foreground",
            ],
            cwd=repo_root,
            env=child_env,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    try:
        pid_path = runtime_root / "gateway.pid"
        identity_path = runtime_root / "gateway.identity.json"
        _wait_for_path(pid_path, process)
        _wait_for_path(identity_path, process)
        identity_path.unlink()
        state_path = runtime_root / ".gateway-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "config_path": str(config_path.resolve()),
                    "log_path": str(log_path),
                    "health_url": "http://127.0.0.1:8011/openapi.json",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("LC_ALL", "C")
        monkeypatch.setenv("LANG", "C")
        monkeypatch.setenv("TZ", "UTC")

        result = stop_gateway(config_path=config_path)

        assert result == f"STOPPED pid={process.pid} state={state_path}"
        assert process.wait(timeout=3) == 0
        assert not pid_path.exists()
        assert not identity_path.exists()
        assert not state_path.exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def test_public_stop_upgrades_live_legacy_state_with_health_url(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = tmp_path / "node-config.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path.write_text(
        f"""\
node:
  node_id: legacy-upgrade-test
agents:
  - agent_id: legacy-agent
    workspace_root: {workspace}
channels: []
gateway:
  startup_timeout_seconds: 5
  shutdown_grace_seconds: 5
  poll_interval_seconds: 0.05
llm:
  default_model: anthropic:test-model
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: anthropic:test-model
""",
        encoding="utf-8",
    )
    log_path = tmp_path / "gateway.log"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "personal_assistant.main",
                "--config",
                str(config_path.resolve()),
                "--foreground",
            ],
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    try:
        pid_path = tmp_path / "gateway.pid"
        identity_path = tmp_path / "gateway.identity.json"
        _wait_for_path(pid_path, process)
        _wait_for_path(identity_path, process)
        identity_path.unlink()
        state_path = tmp_path / ".gateway-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "config_path": str(config_path.resolve()),
                    "log_path": str(log_path),
                    "health_url": "http://127.0.0.1:8011/openapi.json",
                }
            ),
            encoding="utf-8",
        )

        result = stop_gateway(config_path=config_path)

        assert result == f"STOPPED pid={process.pid} state={state_path}"
        assert process.wait(timeout=3) == 0
        assert not pid_path.exists()
        assert not identity_path.exists()
        assert not state_path.exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
