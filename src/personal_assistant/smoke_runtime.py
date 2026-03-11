"""Operator-facing smoke runner for the assembled personal assistant gateway."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

from personal_assistant.config.local_store import LocalConfig, load_local_config


def main(argv: list[str] | None = None) -> int:
    """Run a local readiness + shutdown smoke check against the gateway entrypoint.

    Args:
        argv: Optional CLI argument vector for tests.

    Returns:
        `0` when the gateway reaches ready state, stays alive for the steady window,
        and then exits cleanly after SIGTERM.
    """

    parser = argparse.ArgumentParser(description="Smoke-check personal assistant gateway readiness and shutdown")
    parser.add_argument("--config", required=True, help="Path to the local gateway config file")
    parser.add_argument("--ready-timeout", type=float, default=15.0, help="Seconds to wait for kernel readiness")
    parser.add_argument("--steady-seconds", type=float, default=0.5, help="Seconds the gateway must stay alive after ready")
    parser.add_argument("--shutdown-timeout", type=float, default=10.0, help="Seconds to wait for graceful gateway exit")
    args = parser.parse_args(argv)

    config = load_local_config(args.config)
    process = subprocess.Popen(
        [sys.executable, "-m", "personal_assistant.main", "--config", str(config.source_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_ready(process=process, config=config, timeout_seconds=args.ready_timeout)
        print(f"READY pid={process.pid} url={config.kernel.base_url}{config.kernel.health_path}")
        time.sleep(args.steady_seconds)
        alive = process.poll() is None
        print(f"RUNNING steady_seconds={args.steady_seconds} alive={str(alive).lower()}")
        if not alive:
            raise RuntimeError(f"gateway exited early with return code {process.returncode}")
        process.terminate()
        exit_code = process.wait(timeout=args.shutdown_timeout)
        print(f"SHUTDOWN exit_code={exit_code}")
        if exit_code != 0:
            raise RuntimeError(f"gateway exited with non-zero code: {exit_code}")
        return 0
    except Exception as exc:  # noqa: BLE001
        _cleanup_process(process)
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


def _wait_for_ready(*, process: subprocess.Popen[bytes], config: LocalConfig, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(f"gateway exited before ready with return code {process.returncode}")
        try:
            response = httpx.get(
                f"{config.kernel.base_url}{config.kernel.health_path}",
                timeout=1.0,
                trust_env=False,
            )
            payload = response.json()
            if isinstance(payload, dict) and bool(payload.get("healthy")):
                return
            last_error = RuntimeError(f"unexpected health payload: {payload}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(config.kernel.health_poll_interval_seconds)
    if last_error is not None:
        raise RuntimeError("timed out waiting for kernel readiness") from last_error
    raise RuntimeError("timed out waiting for kernel readiness")


def _cleanup_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


if __name__ == "__main__":
    raise SystemExit(main())
