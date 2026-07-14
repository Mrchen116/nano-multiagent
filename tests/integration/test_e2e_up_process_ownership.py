"""Integration coverage for e2e-up process evidence ownership."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time

from .test_e2e_up_script import (
    _cleanup_owned,
    _pid_alive,
    _prepare_harness,
    _run_up,
    _spawned_pids,
)


def test_preflight_rejects_invalid_internal_evidence_without_signalling_its_pid(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    sentinel = subprocess.Popen(["/bin/sleep", "30"])
    (tmp_path / "gateway.pid").write_text(str(sentinel.pid), encoding="utf-8")
    (tmp_path / "gateway.identity.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gateway-state.json").write_text("{}", encoding="utf-8")
    try:
        result = _run_up(tmp_path, env)

        assert result.returncode == 1
        assert sentinel.poll() is None
        assert "Gateway lifecycle evidence is invalid" in result.stderr
        assert not (tmp_path / "spawned-pids.log").exists()
        assert (tmp_path / "gateway.pid").exists()
        assert (tmp_path / "gateway.identity.json").exists()
        assert (tmp_path / ".gateway-state.json").exists()
    finally:
        _cleanup_owned(tmp_path)
        sentinel.terminate()
        sentinel.wait(timeout=3)


def test_preflight_rejects_live_internal_gateway_before_spawning_second_stack(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    config_path = tmp_path / ".gateway-config.yaml"
    config_path.write_text(
        Path(env["MAIN_CONFIG"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    owner = subprocess.Popen(
        [
            "python",
            "-m",
            "personal_assistant.main",
            "--config",
            str(config_path),
            "--foreground",
            "--auto-bind",
        ],
        cwd=tmp_path,
        env=env,
    )
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if (tmp_path / "gateway.identity.json").exists():
                break
            time.sleep(0.02)
        assert (tmp_path / "gateway.identity.json").exists()

        result = _run_up(tmp_path, env)

        assert result.returncode == 1
        assert "service still running" in result.stderr
        assert owner.poll() is None
        spawned = _spawned_pids(tmp_path)
        assert spawned == [owner.pid]
        assert (tmp_path / "gateway.pid").read_text(encoding="utf-8").strip() == str(
            owner.pid
        )
    finally:
        _cleanup_owned(tmp_path)
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=3)


def test_rollback_reused_gateway_pid_retains_complete_stack(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    env["NODES_STATUS"] = "offline"
    env["SIMULATE_ROLLBACK_PID_REUSE"] = "1"

    try:
        result = _run_up(tmp_path, env, preserve_gateway_signals=True)
        gateway_pid, im_pid = _spawned_pids(tmp_path)[1], _spawned_pids(tmp_path)[0]
        calls = (tmp_path / "signal-calls.log").read_text(encoding="utf-8").splitlines()

        assert result.returncode == 1
        assert "rollback could not stop Gateway" in result.stderr
        assert _pid_alive(gateway_pid)
        assert _pid_alive(im_pid)
        assert f"kill -- -{gateway_pid}" not in calls
        assert f"kill -9 -- -{gateway_pid}" not in calls
        for evidence in (".gateway.pid", "gateway.identity.json", ".im.pid"):
            assert (tmp_path / evidence).exists(), evidence
    finally:
        _cleanup_owned(tmp_path)
