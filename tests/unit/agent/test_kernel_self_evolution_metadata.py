"""create_session re-homes per-agent self_evolution config (refactor-406-M3fix #5).

design 决策1 moves per-agent config into create_session. The legacy bootstrap read the
``self_evolution`` section from ``<workspace>/<dirname>/config.yaml`` into session
metadata; the self_improvement hook reads ``metadata["self_evolution"]`` for
skill_nudge_interval / memory_nudge_interval / enabled. The 2-layer create_session
dropped this read, so the hook fell back to hard-coded interval=10 regardless of user
config. This guards the re-homed read — using only workspace_root +
workspace_config_dirname to locate the file (no ConfigResolver).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import tests.conftest as _conftest
from agent.sdk import LLMConfig, build_kernel


def _build_kernel(repo_root: Path):
    return build_kernel(
        llm=LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD),
        tools=[],
        hooks=[],
        workspace_config_dirname=".nanoassistant",
        repo_root=repo_root,
    )


def test_create_session_reads_self_evolution_from_workspace_config(
    tmp_path: Path,
) -> None:
    """User config.yaml self_evolution values flow into session metadata."""
    ws = tmp_path / "agent-ws"
    cfg_dir = ws / ".nanoassistant"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text(
        "self_evolution:\n"
        "  skill_nudge_interval: 99\n"
        "  memory_nudge_interval: 77\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    kernel = _build_kernel(ws)
    session = asyncio.run(
        kernel.create_session(workspace_root=ws, enabled_tools=["read"], features={})
    )
    se = session.metadata.get("self_evolution", {})
    assert se.get("skill_nudge_interval") == 99, (
        "user skill_nudge_interval must reach session metadata (M3fix #5)"
    )
    assert se.get("memory_nudge_interval") == 77
    assert se.get("enabled") is False


def test_create_session_self_evolution_defaults_without_config(tmp_path: Path) -> None:
    """No config.yaml → platform defaults (interval=10), not empty dict."""
    ws = tmp_path / "no-config-ws"
    ws.mkdir()
    kernel = _build_kernel(ws)
    session = asyncio.run(
        kernel.create_session(workspace_root=ws, enabled_tools=["read"], features={})
    )
    se = session.metadata.get("self_evolution", {})
    assert se.get("skill_nudge_interval") == 10, (
        "absent config must fall back to default interval=10 (not empty → hook hard-default)"
    )
    assert se.get("enabled") is True


def test_create_session_caller_self_evolution_wins(tmp_path: Path) -> None:
    """Explicit metadata self_evolution is not overwritten by the config read."""
    ws = tmp_path / "explicit-ws"
    cfg_dir = ws / ".nanoassistant"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text(
        "self_evolution:\n  skill_nudge_interval: 99\n", encoding="utf-8"
    )
    kernel = _build_kernel(ws)
    session = asyncio.run(
        kernel.create_session(
            workspace_root=ws,
            enabled_tools=["read"],
            features={},
            metadata={"self_evolution": {"skill_nudge_interval": 5}},
        )
    )
    assert session.metadata["self_evolution"]["skill_nudge_interval"] == 5, (
        "caller-supplied self_evolution must win over the config-file read"
    )
