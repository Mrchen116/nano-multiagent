"""Common metadata for isolated, deterministic critical-path process stacks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml


@dataclass
class E2EStack:
    """一套已起好的真进程栈的连接信息 + worktree 目录(供重启 Gateway 用)。"""

    im_url: str
    im_port: str
    node_id: str
    wt_dir: str
    llm_model: str


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


def _selected_llm_model(config_path: Path) -> str:
    """Read the model selected in the isolated Gateway configuration."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    llm = config.get("llm") if isinstance(config, dict) else None
    model = llm.get("default_model") if isinstance(llm, dict) else None
    if not isinstance(model, str) or not model:
        raise ValueError(f"{config_path} is missing llm.default_model")
    return model


def _dump_logs(wt_dir: Path) -> None:
    """把 IM / Gateway 日志 tail 到 stderr,失败时留可诊断证据(spec Req)。"""
    for name in (".im.log", "gateway.log"):
        log = wt_dir / name
        if log.exists():
            tail = "\n".join(log.read_text().splitlines()[-40:])
            print(f"\n===== {name} (tail) =====\n{tail}")


def pytest_configure(config: pytest.Config) -> None:
    """注册 ``slow`` marker(决策 5:cron/heartbeat 等时间驱动路径隔离子集)。"""
    config.addinivalue_line(
        "markers",
        "slow: time-driven critical paths (cron/heartbeat); filter with -m 'not slow'",
    )
