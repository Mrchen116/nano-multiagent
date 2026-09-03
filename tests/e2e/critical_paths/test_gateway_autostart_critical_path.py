"""Critical path: a macOS Gateway survives crashes and returns next login."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "e2e-gateway-autostart.sh"


def _cleanup_autostart_runtime(tmp_path: Path, env: dict[str, str]) -> None:
    """Remove launchd state even when the shell driver had to be killed."""
    config_path = tmp_path / ".gateway-config.yaml"
    cleanup_env = {**env, "PYTHONPATH": str(_REPO_ROOT / "src")}
    cleanup_code = (
        "from personal_assistant.gateway.macos_launch_agent import "
        "permanently_remove; import sys; permanently_remove(config_path=sys.argv[1])"
    )
    with suppress(subprocess.TimeoutExpired):
        subprocess.run(
            [sys.executable, "-c", cleanup_code, str(config_path)],
            cwd=_REPO_ROOT,
            env=cleanup_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    with suppress(subprocess.TimeoutExpired):
        subprocess.run(
            [
                "bash",
                str(_REPO_ROOT / "scripts" / "e2e-down.sh"),
                "--wt",
                str(tmp_path),
            ],
            cwd=_REPO_ROOT,
            env=cleanup_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )


@pytest.mark.e2e
def test_macos_gateway_autostart_crash_stop_login_and_disable(
    tmp_path: Path,
) -> None:
    """Run the real Gateway CLI, LaunchAgent, and isolated IM journey."""
    if sys.platform != "darwin":
        pytest.skip("macOS LaunchAgent critical path")
    if os.getenv("NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E") != "1":
        pytest.skip("set NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 to run")

    env = {**os.environ, "NANO_MULTIAGENT_E2E_PYTHON": sys.executable}
    process = subprocess.Popen(
        ["bash", str(_SCRIPT), "--wt", str(tmp_path)],
        cwd=_REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=180)
    except subprocess.TimeoutExpired as exc:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        raise AssertionError("Gateway autostart e2e timed out") from exc
    finally:
        _cleanup_autostart_runtime(tmp_path, env)

    output = f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    assert process.returncode == 0, output
    assert "GATEWAY AUTOSTART E2E PASS" in stdout, output
