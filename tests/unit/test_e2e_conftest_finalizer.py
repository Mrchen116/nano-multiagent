"""Black-box regression for the E2E pytest session process finalizer."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _spawn_gateway_marker(config_path: Path) -> subprocess.Popen[bytes]:
    marker = f"personal_assistant.main --config {config_path}"
    return subprocess.Popen(
        [sys.executable, "-c", f"# {marker}\nimport time; time.sleep(60)"],
        start_new_session=True,
    )


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
        process.wait(timeout=5)


def _wait_until_stopped(pid: int, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} remained alive after pytest session teardown")


def test_e2e_session_finalizer_kills_only_its_own_gateway_leak(
    tmp_path: Path,
) -> None:
    """A nested E2E session reaps its leak without touching another pytest session."""
    repo_root = Path(__file__).resolve().parents[2]
    unrelated = _spawn_gateway_marker(tmp_path / "other-session" / "config.yaml")
    nested_test = tmp_path / "test_nested_e2e_leak.py"
    leak_pid_path = tmp_path / "current-leak.pid"
    nested_test.write_text(
        """
import os
import subprocess
import sys
from pathlib import Path


def test_leave_gateway_for_session_finalizer(tmp_path):
    marker = f"personal_assistant.main --config {tmp_path / 'config.yaml'}"
    process = subprocess.Popen(
        [sys.executable, "-c", f"# {marker}\\nimport time; time.sleep(60)"],
        start_new_session=True,
    )
    Path(os.environ["E2E_CURRENT_LEAK_PID"]).write_text(str(process.pid))
""".lstrip(),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "E2E_CURRENT_LEAK_PID": str(leak_pid_path),
        "PYTHONPATH": str(repo_root),
    }

    try:
        nested = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "tests.e2e.conftest",
                str(nested_test),
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        assert nested.returncode == 0, nested.stdout + nested.stderr
        leaked_pid = int(leak_pid_path.read_text(encoding="utf-8"))
        _wait_until_stopped(leaked_pid)
        assert unrelated.poll() is None, (
            "one E2E pytest session killed another session's Gateway process"
        )
    finally:
        _terminate(unrelated)


def test_e2e_session_finalizer_does_not_kill_its_own_process_group(
    tmp_path: Path,
) -> None:
    """A leaked Gateway inheriting pytest's group must not abort pytest itself."""
    repo_root = Path(__file__).resolve().parents[2]
    nested_test = tmp_path / "test_nested_e2e_inherited_group.py"
    leak_pid_path = tmp_path / "inherited-group-leak.pid"
    nested_test.write_text(
        """
import os
import subprocess
import sys
from pathlib import Path


def test_leave_gateway_in_pytest_process_group(tmp_path):
    marker = f"personal_assistant.main --config {tmp_path / 'config.yaml'}"
    process = subprocess.Popen(
        [sys.executable, "-c", f"# {marker}\\nimport time; time.sleep(60)"],
    )
    Path(os.environ["E2E_CURRENT_LEAK_PID"]).write_text(str(process.pid))
""".lstrip(),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "E2E_CURRENT_LEAK_PID": str(leak_pid_path),
        "PYTHONPATH": str(repo_root),
    }

    nested = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tests.e2e.conftest",
            str(nested_test),
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        # Isolate this regression subprocess: before the fix its finalizer
        # kills this group's pytest runner along with its leaked child.
        start_new_session=True,
    )

    assert nested.returncode == 0, nested.stdout + nested.stderr
    leaked_pid = int(leak_pid_path.read_text(encoding="utf-8"))
    _wait_until_stopped(leaked_pid)
