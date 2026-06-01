"""Unit tests for tests/e2e/conftest.py session finalizer (bugfix-359 M1/R2).

不通过 pytest session 走 — 测试不能在自己的 session 里触发 session teardown,
所以直接调 ``_scan_leaked_pids`` / ``_kill_leaked_processes`` 两个函数。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest


def _load_conftest_module() -> Any:
    """Load tests/e2e/conftest.py as a regular module so we can call its helpers."""
    repo_root = Path(__file__).resolve().parents[2]
    conftest_path = repo_root / "tests" / "e2e" / "conftest.py"
    spec = importlib.util.spec_from_file_location(
        "_e2e_conftest_for_test", conftest_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_conftest_module()


def _spawn_fake_leak(marker_cmdline: str) -> subprocess.Popen[bytes]:
    """Spawn a `python -c` subprocess whose cmdline contains ``marker_cmdline``.

    把 marker 嵌进 -c 字符串里 — ``ps`` 输出 cmdline 时会原样带上 -c 的内容,
    这样就能用现成的 ps 扫描器测试到匹配/不匹配逻辑,而不需要伪造 cmdline。
    """
    code = f"# {marker_cmdline}\nimport time; time.sleep(60)"
    # CRITICAL: start_new_session=True 让 fake leak 在自己的进程组里。否则
    # _kill_leaked_processes 走 killpg(pgid) 时会按 pytest runner 自己的 pgid 杀,
    # 把 pytest 一起带走 — 测试会半路崩溃,看不到任何 fail/error。
    return subprocess.Popen([sys.executable, "-c", code], start_new_session=True)


def _await_in_ps(pid: int, *, timeout: float = 3.0) -> None:
    """Poll until ps -p sees the pid (Popen.pid != ps visible may be racy on slow CI)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid="],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.stdout.strip():
            return
        time.sleep(0.05)
    raise AssertionError(f"pid {pid} did not appear in ps within {timeout}s")


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)


def test_scan_finds_personal_assistant_main_in_pytest_tmpdir() -> None:
    marker = "personal_assistant.main --config /tmp/pytest-of-tester/pytest-99/test_x/node-config.yaml"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids()
        pids = {p for p, _ in leaked}
        assert proc.pid in pids, f"scanner missed leaked pid {proc.pid}; saw {leaked}"
    finally:
        _terminate(proc)


def test_scan_finds_kernel_app_in_pytest_tmpdir() -> None:
    marker = "uvicorn personal_assistant.kernel_app:app --host 127.0.0.1 --port 11111 (pytest-of-tester/pytest-99/test_x/)"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids()
        pids = {p for p, _ in leaked}
        assert proc.pid in pids
    finally:
        _terminate(proc)


def test_scan_skips_non_pytest_paths() -> None:
    """personal_assistant.main 路径不含 pytest-of-/pytest-NN/ 的不该被扫到。"""
    marker = "personal_assistant.main --config /Users/dev/.nano-assistant/config.yaml"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids()
        pids = {p for p, _ in leaked}
        assert proc.pid not in pids, (
            f"scanner false-positive on prod path; leaked={leaked}"
        )
    finally:
        _terminate(proc)


def test_scan_skips_pytest_path_without_target_needle() -> None:
    """命中 pytest tmpdir 但不是 personal_assistant.main / kernel_app 的不追。"""
    marker = "some-other-tool --config /tmp/pytest-of-tester/pytest-99/test_x/data.json"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids()
        pids = {p for p, _ in leaked}
        assert proc.pid not in pids
    finally:
        _terminate(proc)


def test_scan_excludes_provided_pids() -> None:
    marker = "personal_assistant.main --config /tmp/pytest-of-tester/pytest-99/test_x/node-config.yaml"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids(exclude={proc.pid})
        pids = {p for p, _ in leaked}
        assert proc.pid not in pids
    finally:
        _terminate(proc)


def test_kill_leaked_processes_actually_kills() -> None:
    marker = "personal_assistant.main --config /tmp/pytest-of-tester/pytest-99/test_kill/node-config.yaml"
    proc = _spawn_fake_leak(marker)
    try:
        _await_in_ps(proc.pid)
        leaked = _MOD._scan_leaked_pids()
        targets = [(p, cmd) for p, cmd in leaked if p == proc.pid]
        assert targets, "scanner did not find the spawned fake leak"
        killed = _MOD._kill_leaked_processes(targets)
        assert (proc.pid, targets[0][1]) in killed
        # process should be reaped within a moment
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert proc.poll() is not None, "leaked process survived SIGKILL"
    finally:
        _terminate(proc)


def test_emit_warnings_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    _MOD._emit_warnings(
        [
            (
                12345,
                "personal_assistant.main --config /tmp/pytest-of-x/pytest-0/y/cfg.yaml",
            )
        ]
    )
    captured = capsys.readouterr()
    assert "WARN: pytest finalizer killed leaked process" in captured.err
    assert "pid=12345" in captured.err
