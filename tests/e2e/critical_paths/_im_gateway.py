"""Gateway 进程生死管理 —— 重启 worktree 内的 Gateway（验证进程重启后会话续接）。

从 ``_im_client`` 拆出（单文件 ≤400 行）：IM 黑盒 HTTP 客户端与「重启被测 Gateway 子进程」
是两件事，后者集中在此。杀进程**组**（非单 pid）对齐 e2e-down.sh 和
docs/development/worktree-runtime.md 的清理契约，避免 relay/heartbeat worker 成孤儿。
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping
from datetime import datetime, timezone


def _terminate_process_group(pid: int, *, grace: float = 10.0) -> None:
    """优雅杀 Gateway(SIGTERM → 等 → SIGKILL),对齐 e2e-down.sh 的退出契约。

    Gateway 是 supervisor(范式 B):进程内持有 relay、heartbeat 与 coordinator 运行任务。
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


def restart_gateway(
    wt_dir: str,
    im_port: str,
    *,
    gateway_entrypoint: str | None = None,
    env_overrides: Mapping[str, str] | None = None,
) -> str:
    """重启 worktree 内的 Gateway 进程,复用同 config(保 node_id / workspace → 验续接)。

    e2e-up.sh 用 ``--foreground`` 起 Gateway(范式 B),pid 落在 ``$wt_dir/.gateway.pid``。
    先优雅杀**整个进程组**(避免 relay/heartbeat worker 成孤儿),再用同一份
    ``.gateway-config.yaml`` 以 ``start_new_session`` 重起(让新 Gateway 成进程组长,
    便于本函数下次/teardown 整组清理)。调用 journey 通过 IM 公开
    node generation 判定就绪，本函数不重复解读私有日志 marker。

    Args:
        wt_dir: Isolated stack runtime directory.
        im_port: Isolated IM listening port.
        gateway_entrypoint: Optional Python fixture runner that delegates to the
            production Gateway entry after installing a controlled process fault.
        env_overrides: Environment passed only to the replacement Gateway process.

    Returns:
        UTC generation floor sampled after the old process terminated.
    """
    pid_file = os.path.join(wt_dir, ".gateway.pid")
    cfg = os.path.join(wt_dir, ".gateway-config.yaml")
    log = os.path.join(wt_dir, ".gateway.log")

    # 1) 优雅杀旧进程组。
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            old_pid = int(f.read().strip())
        _terminate_process_group(old_pid)

    # Old-process shutdown may persist one final heartbeat. Readiness must use a
    # generation floor sampled only after termination has completed.
    replacement_started_after = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    # 2) 重起(复用同 config 同 node_id → 工作区/会话续接)。
    # repo_root 从本测试文件位置反推(tests/e2e/critical_paths → repo),
    # 不依赖 wt_dir 是 git 仓(它是 pytest tmp,非 checkout)。
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(repo_root, "src")
    if env_overrides is not None:
        env.update(env_overrides)
    gateway_command = (
        ["python", gateway_entrypoint]
        if gateway_entrypoint is not None
        else ["python", "-m", "personal_assistant.main"]
    )
    log_handle = open(log, "a")
    try:
        proc = subprocess.Popen(
            [
                *gateway_command,
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
    finally:
        log_handle.close()
    with open(pid_file, "w") as f:
        f.write(str(proc.pid))
    if proc.poll() is not None:
        raise AssertionError(f"gateway died during restart; see {log}")
    return replacement_started_after
