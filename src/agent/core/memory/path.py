"""Memory root path derivation — shared by MemoryTool and runtime freeze flow.

Per-workspace 路径治理原则 (design.md 决策 10):
  任何 per-workspace 资源路径必须基于
  <session.workspace_root> / <profile.workspace_config_dirname> / <subdir> 派生。
  禁止硬编码 .nano / .nanoassistant / .nanocode 字符串；
  只允许在 product defaults.py 定义这些常量。
"""
from __future__ import annotations

from pathlib import Path


def derive_memory_root(workspace_root: Path, workspace_config_dirname: str) -> Path:
    """Derive per-session memory root from workspace root and product dirname.

    Both MemoryTool (write path) and runtime _ensure_memory_snapshot (read/freeze
    path) must call this helper so they always resolve to the same physical directory.

    Args:
        workspace_root: Absolute path to the agent's workspace directory.
        workspace_config_dirname: Product-specific config subdir name from
            product defaults.py (e.g. the value of WORKSPACE_CONFIG_DIRNAME constant).

    Returns:
        Path to the memory directory: <workspace_root>/<workspace_config_dirname>/memory/
    """
    return workspace_root / workspace_config_dirname / "memory"
