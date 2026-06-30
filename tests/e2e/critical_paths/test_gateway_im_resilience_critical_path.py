"""关键路径 13:Gateway-IM 连接韧性(bugfix-446)。

spec Req「断线后自动重连(含宿主级瞬态故障)」「启动顺序对 IM 可用性不敏感」。

旅程(经真 IM + 真 Gateway 两进程,只看 IM `/im/v1/nodes` 节点状态):
  A 场景:节点 online → kill IM → 重启 IM → 节点**无需重启 Gateway**自动回 online。
  B 场景:先起 Gateway(IM 未起)→ Gateway 不崩 → 再起 IM → 节点变 online。

真栈由 ``scripts/e2e-resilience.sh`` 驱动(它自取 ephemeral 端口、隔离 config、kill/restart
IM、轮询节点状态)。本测试只是把脚本接入 pytest 套件做登记与门控。连接韧性纯走 WS
register/heartbeat,不调模型,故**不门控 LLM proxy**——只门控 live 开关 + 主 config 存在。

机器「休眠」无法在 CI 直接模拟,用 kill IM 进程(socket 死、需重连)作等价故障(design 决策 5)。
"""

from __future__ import annotations

import os
import signal
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "e2e-resilience.sh"
_MAIN_CONFIG = Path.home() / ".nano-assistant" / "config.yaml"


def _gate_or_skip() -> None:
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip(
            "set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run the resilience critical path "
            "(scripts/e2e-resilience.sh)"
        )
    if not _MAIN_CONFIG.exists():
        pytest.skip(
            f"main config not found: {_MAIN_CONFIG} — create it first (see AGENTS.md, "
            "must include the llm: section)"
        )


def _run_resilience_script(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        with suppress(subprocess.TimeoutExpired):
            process.wait()
        stdout = exc.output or ""
        stderr = exc.stderr or ""
        output = f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        raise AssertionError(
            f"resilience e2e timed out after {timeout}s:\n{output}"
        ) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


@pytest.mark.e2e
def test_gateway_recovers_node_online_after_transient_faults(
    tmp_path: Path,
) -> None:
    """真栈跑两场景到「节点回 online」可见结果,脚本 rc=0 即通过。"""
    _gate_or_skip()

    result = _run_resilience_script(
        [
            "bash",
            str(_SCRIPT),
            "--wt",
            str(tmp_path),
            "--main-config",
            str(_MAIN_CONFIG),
        ],
        cwd=_REPO_ROOT,
        timeout=400,
    )
    output = f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    assert result.returncode == 0, f"resilience e2e failed:\n{output}"
    assert "RESILIENCE E2E PASS" in result.stdout, f"missing success marker:\n{output}"
