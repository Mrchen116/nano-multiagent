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


@pytest.mark.e2e
def test_worktree_stack_isolates_runtime_and_releases_owned_resources(
    tmp_path: Path,
) -> None:
    """Start the public E2E stack, create an Agent, then prove complete teardown."""
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
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
