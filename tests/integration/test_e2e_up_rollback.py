"""Regression coverage for fail-atomic e2e-up rollback."""

from __future__ import annotations

from pathlib import Path

from .test_e2e_up_script import (
    _cleanup_owned,
    _pid_alive,
    _prepare_harness,
    _run_up,
    _spawned_pids,
)


def test_identity_timeout_rolls_back_exact_spawned_stack_and_preserves_logs(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path, startup_timeout=0.5)
    env["GATEWAY_IDENTITY_MODE"] = "timeout"
    env["CREATE_GATEWAY_LOCK"] = "1"

    try:
        result = _run_up(tmp_path, env)
        spawned_pids = _spawned_pids(tmp_path)

        assert result.returncode == 1
        assert spawned_pids
        assert all(not _pid_alive(pid) for pid in spawned_pids), result.stderr
        assert not (tmp_path / ".gateway.pid").exists()
        assert not (tmp_path / ".im.pid").exists()
        assert not (tmp_path / "gateway.pid").exists()
        assert not (tmp_path / "gateway.identity.json").exists()
        assert not (tmp_path / ".gateway-config.yaml.lock").exists()
        assert (tmp_path / ".gateway.log").exists()
        assert (tmp_path / ".im.log").exists()
    finally:
        _cleanup_owned(tmp_path)


def test_identity_timeout_reaps_sigkill_only_im_before_clearing_evidence(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path, startup_timeout=0.5)
    env["GATEWAY_IDENTITY_MODE"] = "timeout"
    env["IM_IGNORES_TERM"] = "1"

    try:
        result = _run_up(tmp_path, env)
        spawned_pids = _spawned_pids(tmp_path)

        assert result.returncode == 1
        assert "rollback could not stop IM" not in result.stderr
        assert spawned_pids
        assert all(not _pid_alive(pid) for pid in spawned_pids), result.stderr
        assert not (tmp_path / ".gateway.pid").exists()
        assert not (tmp_path / ".im.pid").exists()
        assert not (tmp_path / "gateway.pid").exists()
        assert not (tmp_path / "gateway.identity.json").exists()
    finally:
        _cleanup_owned(tmp_path)


def test_identity_timeout_gateway_survivor_retains_whole_stack(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path, startup_timeout=0.1)
    env["GATEWAY_IDENTITY_MODE"] = "timeout"

    try:
        result = _run_up(tmp_path, env, preserve_gateway_signals=True)
        gateway_pid, im_pid = _spawned_pids(tmp_path)[1], _spawned_pids(tmp_path)[0]
        calls = (tmp_path / "signal-calls.log").read_text(encoding="utf-8").splitlines()

        assert result.returncode == 1
        assert "rollback could not stop Gateway" in result.stderr
        assert _pid_alive(gateway_pid)
        assert _pid_alive(im_pid)
        assert not any(line.endswith(f" {im_pid}") for line in calls)
        for evidence in (".gateway.pid", ".im.pid", ".gateway-config.yaml"):
            assert (tmp_path / evidence).exists(), evidence
        assert "stack rollback complete" not in result.stderr
    finally:
        _cleanup_owned(tmp_path)


def test_readiness_failure_after_identity_rolls_back_spawned_stack(
    tmp_path: Path,
) -> None:
    env = _prepare_harness(tmp_path)
    env["NODES_STATUS"] = "offline"

    try:
        result = _run_up(tmp_path, env)
        spawned_pids = _spawned_pids(tmp_path)

        assert result.returncode == 1
        assert "did not become online" in result.stderr
        assert spawned_pids
        assert all(not _pid_alive(pid) for pid in spawned_pids), result.stderr
        assert not (tmp_path / ".gateway.pid").exists()
        assert not (tmp_path / ".im.pid").exists()
        assert not (tmp_path / "gateway.pid").exists()
        assert not (tmp_path / "gateway.identity.json").exists()
        assert (tmp_path / ".gateway.log").exists()
        assert (tmp_path / ".im.log").exists()
    finally:
        _cleanup_owned(tmp_path)
