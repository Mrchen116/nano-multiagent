"""E2E session safety net for Gateway processes leaked by the current run.

Normal E2E fixtures own process cleanup.  This finalizer is the last-resort path
for interrupts and assertion failures: at session teardown it kills Gateway
commands whose config path is rooted in this pytest session's base temp
directory.  The ownership check is deliberately session-local so concurrent
pytest runs cannot reap each other's processes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest

# 只追 Gateway 入口进程。其它 cmdline 命中 pytest tmpdir 的进程不在追杀范围，
# 避免误杀测试 runner 或无关工具。
_LEAK_NEEDLES = ("personal_assistant.main",)


def _scan_leaked_pids(
    *, pytest_tmp_root: Path, exclude: Iterable[int] = ()
) -> list[tuple[int, str]]:
    """Return Gateway processes owned by ``pytest_tmp_root``.

    用 ``ps -ww -eo pid=,command=`` 跨平台拿当前用户的进程表。``=`` 后缀去掉表头。
    ``-ww`` 取消列宽截断 — Linux 非 tty 下 ``ps`` 默认按终端宽度裁列,含长 pytest
    tmpdir 路径的 cmdline 会被截掉,导致漏报泄漏进程;macOS 不截断故本地不暴露。
    匹配条件:cmdline 同时含当前 session 的 base temp 路径 + Gateway 关键词。
    """
    exclude_set = set(exclude)
    tmp_roots = {str(pytest_tmp_root), str(pytest_tmp_root.resolve())}
    try:
        completed = subprocess.run(
            ["ps", "-ww", "-eo", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    leaked: list[tuple[int, str]] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        head, _, cmd = line.partition(" ")
        try:
            pid = int(head)
        except ValueError:
            continue
        if pid in exclude_set:
            continue
        if not any(tmp_root in cmd for tmp_root in tmp_roots):
            continue
        if not any(needle in cmd for needle in _LEAK_NEEDLES):
            continue
        leaked.append((pid, cmd))
    return leaked


def _kill_leaked_processes(leaked: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """SIGKILL each ``(pid, cmd)`` (best-effort, killpg first then direct)."""
    killed: list[tuple[int, str]] = []
    for pid, cmd in leaked:
        sent = False
        try:
            pgid = os.getpgid(pid)
        except (ProcessLookupError, PermissionError):
            pgid = None
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
                sent = True
            except (ProcessLookupError, PermissionError):
                pass
        if not sent:
            try:
                os.kill(pid, signal.SIGKILL)
                sent = True
            except (ProcessLookupError, PermissionError):
                pass
        if sent:
            killed.append((pid, cmd))
    return killed


def _emit_warnings(killed: list[tuple[int, str]]) -> None:
    for pid, cmd in killed:
        # WARN 是给开发者看的:每出现一行就说明上一轮测试自己的清理路径漏了进程,
        # 兜底救场不等于本身干净。重定向到 stderr 而不是 warnings.warn,避免被
        # filterwarnings 吞掉。
        sys.stderr.write(
            f"WARN: pytest finalizer killed leaked process: pid={pid} cmdline={cmd}\n"
        )


@pytest.fixture(scope="session", autouse=True)
def _e2e_session_process_leak_finalizer(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterable[None]:
    """Autouse session finalizer — runs at session teardown only."""
    yield
    leaked = _scan_leaked_pids(
        pytest_tmp_root=tmp_path_factory.getbasetemp(), exclude={os.getpid()}
    )
    if not leaked:
        return
    killed = _kill_leaked_processes(leaked)
    _emit_warnings(killed)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-apply ``e2e`` marker to every item whose path is inside ``tests/e2e/``.

    Prevents ``pytest -m "not e2e"`` from accidentally collecting tests that
    need real processes or network services.
    """
    e2e_marker = pytest.mark.e2e
    for item in items:
        if "tests/e2e/" in str(item.path):
            item.add_marker(e2e_marker, append=False)
