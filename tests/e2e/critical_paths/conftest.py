"""关键路径 e2e 套件的起栈 fixture + 门控。

design.md 决策 1:不在 Python 重写起栈,session 级 fixture subprocess 调
``scripts/e2e-up.sh --wt <pytest tmp>`` 起**真 IM + 真 Gateway 进程**,source
``.e2e-ports.env`` 拿 ``IM_URL`` / ``NODE_ID``,session 结束调 ``e2e-down.sh``。

门控沿用既有范式(决策 3):``NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1`` + ``GET :4000/health``
双门控。缺 env / 缺 proxy / 缺 ~/.nano-assistant/config.yaml → **干净 skip,不崩**。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from ._im_client import IMClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
_E2E_UP = _REPO_ROOT / "scripts" / "e2e-up.sh"
_E2E_DOWN = _REPO_ROOT / "scripts" / "e2e-down.sh"
_MAIN_CONFIG = Path.home() / ".nano-assistant" / "config.yaml"
_LLM_PROXY_HEALTH = "http://127.0.0.1:4000/health"


def _live_proxy_available() -> bool:
    """``GET :4000/health`` 200 即认为本地 LLM proxy 可用(沿用既有 e2e 探活口径)。"""
    try:
        return httpx.get(_LLM_PROXY_HEALTH, timeout=1.5).status_code == 200
    except httpx.HTTPError:
        return False


def _gate_or_skip() -> None:
    """三道门控:env 开关 / proxy 探活 / 主 config 存在。任一不满足 → 干净 skip。"""
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip(
            "set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run critical-path e2e "
            "(use scripts/e2e-critical.sh)"
        )
    if not _live_proxy_available():
        pytest.skip(f"LLM proxy unavailable at {_LLM_PROXY_HEALTH}")
    if not _MAIN_CONFIG.exists():
        pytest.skip(
            f"main config not found: {_MAIN_CONFIG} — create it first (see AGENTS.md "
            "'minimum config example', must include the llm: section)"
        )


@dataclass
class E2EStack:
    """一套已起好的真进程栈的连接信息 + worktree 目录(供重启 Gateway 用)。"""

    im_url: str
    im_port: str
    node_id: str
    wt_dir: str


def _parse_ports_env(ports_env: Path) -> dict[str, str]:
    """解析 e2e-up.sh 写出的 ``.e2e-ports.env``(``export K=V`` 行)。"""
    values: dict[str, str] = {}
    for line in ports_env.read_text().splitlines():
        line = line.strip()
        if not line.startswith("export ") or "=" not in line:
            continue
        key, _, val = line[len("export ") :].partition("=")
        values[key.strip()] = val.strip()
    return values


@pytest.fixture(scope="session")
def e2e_stack(tmp_path_factory: pytest.TempPathFactory) -> E2EStack:
    """起真 IM + 真 Gateway 进程栈(session 级,全套共享一次起停)。

    决策 1 风险缓解:必须传 ``--wt <pytest tmp>`` 把 ``.pid/.log/.gateway-config.yaml``
    隔离进临时目录,**绝不污染主仓**。
    """
    _gate_or_skip()

    wt_dir = tmp_path_factory.mktemp("e2e_critical_stack")
    # e2e-up.sh 用 git 探 repo root(写 .gateway-workspace 等),tmp 目录非 git 仓 →
    # 它已 fallback 到 dirname。但 free-ports.sh / scripts 仍按 $0 定位,无碍。
    # 仍需 worktree 内有 scripts/,故把脚本所需的相对依赖通过绝对路径调用解决。
    up = subprocess.run(
        [
            "bash",
            str(_E2E_UP),
            "--wt",
            str(wt_dir),
            "--main-config",
            str(_MAIN_CONFIG),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if up.returncode != 0:
        # 起栈失败:把 IM/Gateway 日志拼进报错,符合「失败留可诊断证据」(spec Req)。
        _dump_logs(wt_dir)
        pytest.fail(
            f"e2e-up.sh failed (rc={up.returncode}):\n"
            f"--- stdout ---\n{up.stdout}\n--- stderr ---\n{up.stderr}"
        )

    ports_env = wt_dir / ".e2e-ports.env"
    if not ports_env.exists():
        _dump_logs(wt_dir)
        pytest.fail(f".e2e-ports.env not produced; stdout:\n{up.stdout}")

    values = _parse_ports_env(ports_env)
    stack = E2EStack(
        im_url=values["IM_URL"],
        im_port=values["IM_PORT"],
        node_id=values.get("NODE_ID", ""),
        wt_dir=str(wt_dir),
    )

    yield stack

    # teardown:必走 e2e-down.sh(决策 1);残留由 tests/e2e/conftest.py finalizer 兜底。
    subprocess.run(
        ["bash", str(_E2E_DOWN), "--wt", str(wt_dir)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _dump_logs(wt_dir: Path) -> None:
    """把 IM / Gateway 日志 tail 到 stderr,失败时留可诊断证据(spec Req)。"""
    for name in (".im.log", ".gateway.log"):
        log = wt_dir / name
        if log.exists():
            tail = "\n".join(log.read_text().splitlines()[-40:])
            print(f"\n===== {name} (tail) =====\n{tail}")


@pytest.fixture
def im_user(e2e_stack: E2EStack) -> IMClient:
    """一个已登录 nano 测试用户的 IM 客户端(function 级,自动 close)。"""
    client = IMClient(e2e_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    yield client
    client.close()


def pytest_configure(config: pytest.Config) -> None:
    """注册 ``slow`` marker(决策 5:cron/heartbeat 等时间驱动路径隔离子集)。"""
    config.addinivalue_line(
        "markers",
        "slow: time-driven critical paths (cron/heartbeat); filter with -m 'not slow'",
    )
