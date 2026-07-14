"""Integration coverage for e2e generation locking and IM preflight."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from .test_e2e_down_script import _GATEWAY_PID, _run_down, _write_stack_files
from .test_e2e_up_script import _cleanup_owned, _prepare_harness


def _lock_holder(path: Path) -> subprocess.Popen[str]:
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl,sys; "
            "f=open(sys.argv[1], 'a+'); "
            "fcntl.flock(f, fcntl.LOCK_EX); "
            "print('ready', flush=True); sys.stdin.read()",
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "ready"
    return holder


def _release_holder(holder: subprocess.Popen[str]) -> None:
    if holder.poll() is not None:
        return
    assert holder.stdin is not None
    holder.stdin.close()
    holder.wait(timeout=3)


def test_e2e_up_waits_on_external_generation_lock_before_preflight(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    lock_path = tmp_path.parent / f".{tmp_path.name}-lifecycle.lock"
    env["NANO_MULTIAGENT_E2E_LIFECYCLE_LOCK_PATH"] = str(lock_path)
    holder = _lock_holder(lock_path)
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-up.sh"
    process = subprocess.Popen(
        [
            "bash",
            str(script),
            "--wt",
            str(tmp_path),
            "--main-config",
            env["MAIN_CONFIG"],
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.2)
        crossed_generation = (tmp_path / "spawned-pids.log").exists()
        _release_holder(holder)
        _stdout, stderr = process.communicate(timeout=15)

        assert not crossed_generation
        assert process.returncode == 0, stderr
        assert not (tmp_path / ".e2e-lifecycle.lock").exists()
    finally:
        _release_holder(holder)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        _cleanup_owned(tmp_path)


def test_e2e_down_waits_on_same_external_lock_before_preflight(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path.parent / f".{tmp_path.name}-lifecycle.lock"
    holder = _lock_holder(lock_path)
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-down.sh"
    process = subprocess.Popen(
        ["bash", str(script), "--wt", str(tmp_path)],
        cwd=repo_root,
        env={
            **os.environ,
            "NANO_MULTIAGENT_E2E_LIFECYCLE_LOCK_PATH": str(lock_path),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.2)
        crossed_generation = process.poll() is not None
        _release_holder(holder)
        _stdout, stderr = process.communicate(timeout=5)

        assert not crossed_generation
        assert process.returncode == 0, stderr
    finally:
        _release_holder(holder)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)


@pytest.mark.parametrize("mode", ["dangling", "nonregular", "malformed"])
def test_invalid_im_evidence_fails_before_any_gateway_or_im_signal(
    mode: str,
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    im_pid_path = tmp_path / ".im.pid"
    im_pid_path.unlink()
    if mode == "dangling":
        im_pid_path.symlink_to(tmp_path / "missing-im-pid")
    elif mode == "nonregular":
        im_pid_path.mkdir()
    else:
        im_pid_path.write_text("not-a-pid\n", encoding="utf-8")

    result = _run_down(tmp_path, kill_body="return 0")

    calls_path = tmp_path / "calls.log"
    calls = calls_path.read_text(encoding="utf-8") if calls_path.exists() else ""
    assert result.returncode == 1
    assert "kill " not in calls
    assert "IM PID evidence" in result.stderr
    assert (tmp_path / ".gateway.pid").exists()


def test_im_evidence_revision_drift_after_gateway_exit_sends_no_im_signal(
    tmp_path: Path,
) -> None:
    _write_stack_files(tmp_path)
    kill_body = f"""
if [[ "$*" == "{_GATEWAY_PID}" ]]; then
  cp "$E2E_WT/.im.pid" "$E2E_WT/.im.pid.replacement"
  mv "$E2E_WT/.im.pid.replacement" "$E2E_WT/.im.pid"
  export PROCESS_STAT=""
fi
return 0
"""

    result = _run_down(tmp_path, kill_body=kill_body)

    calls = (tmp_path / "calls.log").read_text(encoding="utf-8").splitlines()
    assert result.returncode == 1
    assert f"kill {_GATEWAY_PID}" in calls
    assert "kill 434343" not in calls
    assert "IM PID evidence changed" in result.stderr
    assert (tmp_path / ".im.pid").exists()
