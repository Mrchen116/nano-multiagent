"""Gateway 进程生死管理 —— 重启 worktree 内的 Gateway（验证进程重启后会话续接）。

从 ``_im_client`` 拆出（单文件 ≤400 行）：IM 黑盒 HTTP 客户端与「重启被测 Gateway 子进程」
是两件事，后者集中在此。杀进程**组**（非单 pid）对齐 e2e-down.sh 和
docs/development/worktree-runtime.md 的清理契约，避免 relay/heartbeat worker 成孤儿。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path


def restart_gateway(
    wt_dir: str,
    im_port: str,
    *,
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
        env_overrides: Environment passed only to the replacement Gateway process.

    Returns:
        UTC generation floor sampled after the old process terminated.
    """
    pid_file = os.path.join(wt_dir, ".gateway.pid")
    cfg = os.path.join(wt_dir, ".gateway-config.yaml")
    log = os.path.join(wt_dir, "gateway.log")

    repo_root = str(Path(__file__).resolve().parents[3])
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required for the native Gateway")
    subprocess.run(
        [node, str(Path(repo_root) / "apps/node/lib/cli.js"), "stop", "--config", cfg],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

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
    if env_overrides is not None:
        env.update(env_overrides)
    gateway_command = [node, str(Path(repo_root) / "apps/node/lib/cli.js")]
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
