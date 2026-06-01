"""E2E test session finalizer — kill any leaked subprocesses.

bugfix-359: e2e 测试 ``tests/e2e/test_personal_assistant_main_e2e.py`` 在异常路径
(测试超时 / assert 失败 / Ctrl-C)下会留下 ``personal_assistant.main --foreground``
和它的 kernel uvicorn 子进程。即便 §R1 把 ``_terminate_background_pid`` / ``stop_gateway``
都改成 killpg,只要测试在跑到清理代码前就异常,daemon 还是飞了。

本 finalizer 是兜底:session teardown 时扫一遍系统进程,cmdline 命中 pytest-of-<user>/pytest-NN/
的 ``personal_assistant.main`` 或 ``uvicorn personal_assistant.kernel_app`` 一律 SIGKILL,
每条打一行 ``WARN:`` 让 dev 立刻看到 — 兜底干净不等于测试自身清理也干净,留下的告警就是
"测试本身的清理路径有 bug,请修"。
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import warnings
from typing import Iterable

import pytest

# 匹配 pytest tmpdir 路径里的 pytest 标识(macOS / Linux 通用)。
# pytest 默认 basetemp 形如 /private/var/folders/.../pytest-of-<user>/pytest-<NN>/...
# 或 /tmp/pytest-of-<user>/pytest-<NN>/...
_PYTEST_TMP_RE = re.compile(r"pytest-of-[^/\s]+/pytest-\d+/")

# 只追这两类进程 — Gateway 父 + kernel uvicorn 子。其它 cmdline 命中 pytest tmpdir 的
# 比如 SQLite 连接的 wal 文件路径出现在 fd 表里(实际不会出现在 cmdline),不在追杀范围。
_LEAK_NEEDLES = (
    "personal_assistant.main",
    "personal_assistant.kernel_app",
)


def _scan_leaked_pids(*, exclude: Iterable[int] = ()) -> list[tuple[int, str]]:
    """Return ``(pid, cmdline)`` for processes whose cmdline matches a pytest tmpdir.

    用 ``ps -ww -eo pid=,command=`` 跨平台拿当前用户的进程表。``=`` 后缀去掉表头。
    ``-ww`` 取消列宽截断 — Linux 非 tty 下 ``ps`` 默认按终端宽度裁列,含长 pytest
    tmpdir 路径的 cmdline 会被截掉,导致漏报泄漏进程;macOS 不截断故本地不暴露。
    匹配条件:cmdline 同时含 pytest 临时目录标识 + Gateway/kernel 关键词。
    """
    exclude_set = set(exclude)
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
        if not _PYTEST_TMP_RE.search(cmd):
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
def _e2e_session_process_leak_finalizer() -> Iterable[None]:
    """Autouse session finalizer — runs at session teardown only."""
    yield
    leaked = _scan_leaked_pids(exclude={os.getpid()})
    if not leaked:
        return
    killed = _kill_leaked_processes(leaked)
    _emit_warnings(killed)


# refactor-372-M1: 按路径自动给 tests/e2e/ 下的所有 item 打 e2e marker。
# 用 hook 而非逐文件手写 pytestmark，保证新增文件天然被覆盖不会再漏标。
# TESTING_GUIDE §3 已认可此法；design.md 决策 1 选定此方案。
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-apply ``e2e`` marker to every item whose path is inside ``tests/e2e/``.

    Prevents ``pytest -m "not e2e"`` from accidentally collecting tests that
    need real processes or network services.  Previously only 4 of 29 e2e
    files carried the marker explicitly; the other 25 leaked into the baseline
    run and caused spurious failures.
    """
    e2e_marker = pytest.mark.e2e
    for item in items:
        if "tests/e2e/" in str(item.path):
            item.add_marker(e2e_marker, append=False)
