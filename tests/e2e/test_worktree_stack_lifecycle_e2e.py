"""Real-process acceptance for the worktree E2E stack lifecycle."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

from .critical_paths._im_client import IMClient
from .critical_paths.conftest import _parse_ports_env


_REPO_ROOT = Path(__file__).resolve().parents[2]
_E2E_UP = _REPO_ROOT / "scripts" / "e2e-up.sh"
_E2E_DOWN = _REPO_ROOT / "scripts" / "e2e-down.sh"


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _e2e_python_wrapper(
    tmp_path: Path, *, im_launch_mode: str, readiness_timeout_seconds: int | None
) -> dict[str, str]:
    """Delay or stop only the IM uvicorn child while preserving Gateway startup."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "python"
    wrapper.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"uvicorn\" ]]; then
  case \"${NANO_MULTIAGENT_E2E_TEST_IM_LAUNCH_MODE:-normal}\" in
    delayed) sleep \"${NANO_MULTIAGENT_E2E_TEST_IM_DELAY_SECONDS:-0}\" ;;
    exited) exit 23 ;;
  esac
fi
exec \"$NANO_MULTIAGENT_E2E_REAL_PYTHON\" \"$@\"
""",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
        "NANO_MULTIAGENT_E2E_REAL_PYTHON": sys.executable,
        "NANO_MULTIAGENT_E2E_TEST_IM_LAUNCH_MODE": im_launch_mode,
    }
    if readiness_timeout_seconds is None:
        env.pop("NANO_MULTIAGENT_E2E_IM_READINESS_TIMEOUT_SECONDS", None)
    else:
        env["NANO_MULTIAGENT_E2E_IM_READINESS_TIMEOUT_SECONDS"] = str(
            readiness_timeout_seconds
        )
    return env


def _run_e2e_down(stack_dir: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        ["bash", str(_E2E_DOWN), "--wt", str(stack_dir)],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _assert_im_reclaimed(stack_dir: Path, im_pid: int | None) -> None:
    assert not (stack_dir / ".im.pid").exists()
    if im_pid is None:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _pid_is_alive(im_pid):
        time.sleep(0.05)
    assert not _pid_is_alive(im_pid)


@pytest.mark.e2e
def test_worktree_stack_isolates_runtime_and_releases_owned_resources(
    tmp_path: Path,
) -> None:
    """Start the public E2E stack, create an Agent, then prove complete teardown."""
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    stale_shadow_files = [
        stack_dir / "external_shadow_sagas.sqlite3",
        stack_dir / "external_shadow_sagas.sqlite3-wal",
        stack_dir / "external_shadow_sagas.sqlite3-shm",
    ]
    for path in stale_shadow_files:
        path.write_text("stale-external-shadow-state", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
    }
    down_result: subprocess.CompletedProcess[str] | None = None
    try:
        up_result = subprocess.run(
            [
                "bash",
                str(_E2E_UP),
                "--wt",
                str(stack_dir),
            ],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert up_result.returncode == 0, (
            f"e2e-up failed:\n{up_result.stdout}\n{up_result.stderr}"
        )

        ports = _parse_ports_env(stack_dir / ".e2e-ports.env")
        assert ports["E2E_PROFILE"] == "default"
        assert all(
            not path.exists() or path.read_bytes() != b"stale-external-shadow-state"
            for path in stale_shadow_files
        )
        im_port = int(ports["IM_PORT"])
        im_pid = int((stack_dir / ".im.pid").read_text().strip())
        gateway_pid = int((stack_dir / ".gateway.pid").read_text().strip())
        assert _pid_is_alive(im_pid)
        assert _pid_is_alive(gateway_pid)
        assert _port_is_open(im_port)
        assert (
            httpx.get(f"{ports['IM_URL']}/openapi.json", timeout=2).status_code == 200
        )

        config = yaml.safe_load((stack_dir / ".gateway-config.yaml").read_text())
        workspace_root = (stack_dir / ".gateway-workspace").resolve()
        assert Path(config["node"]["workspace_base"]).resolve() == workspace_root
        assert config["node"]["node_id"] == ports["NODE_ID"]
        assert {agent["agent_id"] for agent in config["agents"]} == {
            "e2e",
            "e2e-peer",
        }
        assert all(
            Path(agent["workspace_root"]).resolve().is_relative_to(workspace_root)
            for agent in config.get("agents", [])
        )
        assert (stack_dir / "data" / "im_service.sqlite3").is_file()

        client = IMClient(ports["IM_URL"])
        try:
            client.register_or_login("nano", "nano1234", display_name="Test User")
            node_id = client.wait_for_online_node(timeout=30)
            agent_id = "isolation" + secrets.token_hex(3)
            created = client.create_agent(node_id, agent_id)
            dynamic_workspace = Path(created["workspace_root"]).resolve()
            assert dynamic_workspace.is_relative_to(workspace_root)
            assert dynamic_workspace.is_dir()
        finally:
            client.close()

        for path in (
            stack_dir / "channel-credentials-v1.pem",
            stack_dir / "channel-manifest-v1.json",
        ):
            assert path.is_file()
    finally:
        down_result = subprocess.run(
            ["bash", str(_E2E_DOWN), "--wt", str(stack_dir)],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    assert down_result.returncode == 0, down_result.stderr
    for path in (
        stack_dir / ".im.pid",
        stack_dir / ".gateway.pid",
        stack_dir / ".e2e-ports.env",
        stack_dir / ".e2e-jwt-secret",
        stack_dir / ".gateway-config.yaml",
        stack_dir / "channel-credentials-v1.pem",
        stack_dir / "channel-manifest-v1.json",
    ):
        assert not path.exists()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _port_is_open(im_port):
        time.sleep(0.05)
    assert not _port_is_open(im_port)
    assert not _pid_is_alive(im_pid)
    assert not _pid_is_alive(gateway_pid)


@pytest.mark.e2e
def test_e2e_up_accepts_slow_but_alive_im_within_readiness_budget(
    tmp_path: Path,
) -> None:
    """IM cold startup is condition-polled rather than rejected at the old six seconds."""

    stack_dir = tmp_path / "slow-im"
    stack_dir.mkdir()
    env = _e2e_python_wrapper(
        tmp_path,
        im_launch_mode="delayed",
        readiness_timeout_seconds=None,
    )
    env["NANO_MULTIAGENT_E2E_TEST_IM_DELAY_SECONDS"] = "7"
    im_pid: int | None = None
    try:
        up = subprocess.run(
            ["bash", str(_E2E_UP), "--wt", str(stack_dir)],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert up.returncode == 0, f"stdout:\n{up.stdout}\nstderr:\n{up.stderr}"
        im_pid = int((stack_dir / ".im.pid").read_text().strip())
        assert _pid_is_alive(im_pid)
        ports = _parse_ports_env(stack_dir / ".e2e-ports.env")
        assert (
            httpx.get(f"{ports['IM_URL']}/openapi.json", timeout=2).status_code == 200
        )
    finally:
        _run_e2e_down(stack_dir, env)
    _assert_im_reclaimed(stack_dir, im_pid)


@pytest.mark.e2e
def test_e2e_up_reports_im_child_exit_before_readiness_deadline(tmp_path: Path) -> None:
    """A dead IM process is not misreported as a readiness timeout or Bot conflict."""

    stack_dir = tmp_path / "dead-im"
    stack_dir.mkdir()
    env = _e2e_python_wrapper(
        tmp_path,
        im_launch_mode="exited",
        readiness_timeout_seconds=5,
    )
    im_pid: int | None = None
    try:
        up = subprocess.run(
            ["bash", str(_E2E_UP), "--wt", str(stack_dir)],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert up.returncode != 0
        assert "IM process exited during startup" in up.stderr
        assert "readiness timed out" not in up.stderr
        assert "dedicated Feishu E2E listener" not in up.stderr
        assert (stack_dir / ".im.log").exists()
        im_pid_file = stack_dir / ".im.pid"
        im_pid = int(im_pid_file.read_text().strip()) if im_pid_file.exists() else None
    finally:
        _run_e2e_down(stack_dir, env)
    _assert_im_reclaimed(stack_dir, im_pid)


@pytest.mark.e2e
def test_e2e_up_reports_alive_im_readiness_deadline_and_cleanup(tmp_path: Path) -> None:
    """An alive but not-yet-ready IM preserves logs and names the actual timeout."""

    stack_dir = tmp_path / "timed-out-im"
    stack_dir.mkdir()
    env = _e2e_python_wrapper(
        tmp_path,
        im_launch_mode="delayed",
        readiness_timeout_seconds=1,
    )
    env["NANO_MULTIAGENT_E2E_TEST_IM_DELAY_SECONDS"] = "5"
    im_pid: int | None = None
    try:
        up = subprocess.run(
            ["bash", str(_E2E_UP), "--wt", str(stack_dir)],
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert up.returncode != 0
        assert "IM readiness timed out after 1s" in up.stderr
        assert "process exited" not in up.stderr
        assert "dedicated Feishu E2E listener" not in up.stderr
        assert (stack_dir / ".im.log").exists()
        im_pid = int((stack_dir / ".im.pid").read_text().strip())
        assert _pid_is_alive(im_pid)
    finally:
        _run_e2e_down(stack_dir, env)
    _assert_im_reclaimed(stack_dir, im_pid)
