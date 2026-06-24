"""Gateway 进程生死管理 —— 重启 worktree 内的 Gateway（验证进程重启后会话续接）。

从 ``_im_client`` 拆出（单文件 ≤400 行）：IM 黑盒 HTTP 客户端与「重启被测 Gateway 子进程」
是两件事，后者集中在此。杀进程**组**（非单 pid）对齐 e2e-down.sh / AGENTS.md stop_pidfile
范式，避免 relay/heartbeat worker 成孤儿。
"""

from __future__ import annotations

import os
import signal
import subprocess
import time

from ._im_polling import poll_until


def _terminate_process_group(pid: int, *, grace: float = 10.0) -> None:
    """优雅杀 Gateway(SIGTERM → 等 → SIGKILL),对齐 e2e-down.sh / stop_pidfile。

    Gateway 是 supervisor(范式 B):自己 spawn relay / heartbeat / run_queue 等 worker。
    **只在 pid 是自己进程组的组长时**(``getpgid(pid) == pid``——即由 ``start_new_session``
    起的独立进程组)才 ``killpg`` 杀整组,这样它的 worker 不成孤儿。

    **关键安全护栏**:e2e-up.sh 起的 Gateway **没有** setsid,继承的是 pytest 进程组;若对它
    无脑 ``killpg(getpgid(pid))`` 会把整个 pytest 进程组(含 pytest 自己)一起 SIGTERM 杀掉
    (表现为 pytest 退出码 144)。故非组长的 pid 退回**单 pid** kill——Gateway 作为 supervisor
    收到 SIGTERM 会自行向其 worker 传播,不会留孤儿。
    """
    try:
        is_group_leader = os.getpgid(pid) == pid
    except ProcessLookupError:
        return

    def _signal(sig: int) -> None:
        if is_group_leader:
            os.killpg(pid, sig)  # 独立进程组 → 整组杀,worker 不成孤儿。
        else:
            os.kill(pid, sig)  # 继承 pytest 组 → 只杀 Gateway 本身,绝不碰 pytest 组。

    try:
        _signal(signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)
    try:
        _signal(signal.SIGKILL)
    except ProcessLookupError:
        pass


def restart_gateway(wt_dir: str, im_port: str) -> None:
    """重启 worktree 内的 Gateway 进程,复用同 config(保 node_id / workspace → 验续接)。

    e2e-up.sh 用 ``--foreground`` 起 Gateway(范式 B),pid 落在 ``$wt_dir/.gateway.pid``。
    先优雅杀**整个进程组**(避免 relay/heartbeat worker 成孤儿),再用同一份
    ``.gateway-config.yaml`` 以 ``start_new_session`` 重起(让新 Gateway 成进程组长,
    便于本函数下次/teardown 整组清理),等就绪标志出现。
    """
    pid_file = os.path.join(wt_dir, ".gateway.pid")
    cfg = os.path.join(wt_dir, ".gateway-config.yaml")
    log = os.path.join(wt_dir, ".gateway.log")

    # 1) 优雅杀旧进程组。
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            old_pid = int(f.read().strip())
        _terminate_process_group(old_pid)

    # 2) 重起(复用同 config 同 node_id → 工作区/会话续接)。
    # repo_root 从本测试文件位置反推(tests/e2e/critical_paths → repo),
    # 不依赖 wt_dir 是 git 仓(它是 pytest tmp,非 checkout)。
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(repo_root, "src")
    log_handle = open(log, "a")
    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "personal_assistant.main",
            "--config",
            cfg,
            "--im-service-url",
            f"http://127.0.0.1:{im_port}",
            "--foreground",
            "--auto-bind",
        ],
        cwd=repo_root,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # 新进程组 → 后续可整组 killpg,worker 不成孤儿。
    )
    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    # 3) 等就绪标志(沿用 e2e-up.sh 的探测口径)。
    ready_markers = (
        "auto-bound to IM",
        "Gateway started",
        "node_id=",
        "im_connection",
    )

    def _ready() -> bool:
        if proc.poll() is not None:
            raise AssertionError(f"gateway died during restart; see {log}")
        try:
            with open(log) as f:
                tail = f.read()
        except FileNotFoundError:
            return False
        return any(marker in tail for marker in ready_markers)

    poll_until(
        _ready, lambda r: r, timeout=40.0, interval=0.5, desc="gateway readiness"
    )
