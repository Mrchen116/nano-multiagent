from __future__ import annotations

from pathlib import Path
import sqlite3

import yaml

from scripts.acceptance import m170_runtime


def _patch_runtime_paths(monkeypatch, runtime_root: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr(m170_runtime, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(m170_runtime, "RUNTIME_DB", runtime_root / "im_service.sqlite3")
    monkeypatch.setattr(
        m170_runtime, "RUNTIME_CONFIG", runtime_root / "node-config.yaml"
    )
    monkeypatch.setattr(m170_runtime, "RUNTIME_IM_LOG", runtime_root / "im.log")
    monkeypatch.setattr(
        m170_runtime, "RUNTIME_GATEWAY_LOG", runtime_root / "gateway.log"
    )
    monkeypatch.setattr(
        m170_runtime, "RUNTIME_HEARTBEAT_STATE", runtime_root / "heartbeat-state.json"
    )
    monkeypatch.setattr(
        m170_runtime, "RUNTIME_GATEWAY_STATE", runtime_root / ".gateway-state.json"
    )
    monkeypatch.setattr(m170_runtime, "RUNTIME_UPLOADS", runtime_root / "uploads")
    monkeypatch.setattr(m170_runtime, "RUNTIME_WORKSPACE", runtime_root / "workspace")


def test_rebuild_runtime_clears_stale_artifacts_and_recreates_layout(
    monkeypatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "m170-runtime"
    _patch_runtime_paths(monkeypatch, runtime_root)

    runtime_root.mkdir(parents=True)
    (runtime_root / "im_service.sqlite3").write_text("old-db", encoding="utf-8")
    (runtime_root / "gateway.log").write_text("old-gateway", encoding="utf-8")
    (runtime_root / "im.log").write_text("old-im", encoding="utf-8")
    (runtime_root / "heartbeat-state.json").write_text(
        "old-heartbeat", encoding="utf-8"
    )
    (runtime_root / ".gateway-state.json").write_text("{}", encoding="utf-8")
    (runtime_root / "uploads").mkdir()
    (runtime_root / "uploads" / "stale.txt").write_text("stale", encoding="utf-8")
    (runtime_root / "workspace").mkdir()
    (runtime_root / "workspace" / "stale.txt").write_text("stale", encoding="utf-8")

    stop_calls: list[float] = []
    monkeypatch.setattr(
        m170_runtime,
        "stop_runtime",
        lambda timeout_seconds=m170_runtime.DEFAULT_STOP_TIMEOUT_SECONDS: (
            stop_calls.append(timeout_seconds) or {}
        ),
    )

    result = m170_runtime.rebuild_runtime()

    assert stop_calls == [m170_runtime.DEFAULT_STOP_TIMEOUT_SECONDS]
    assert result["status"] == "rebuilt"
    assert (runtime_root / "im_service.sqlite3").exists() is True
    assert (runtime_root / "node-config.yaml").exists() is True
    assert (runtime_root / "uploads").is_dir() is True
    assert (runtime_root / "workspace").is_dir() is True
    assert (runtime_root / "uploads" / "stale.txt").exists() is False
    assert (runtime_root / "workspace" / "stale.txt").exists() is False
    assert (runtime_root / "gateway.log").exists() is False
    assert (runtime_root / "im.log").exists() is False
    assert (runtime_root / "heartbeat-state.json").exists() is False
    assert (runtime_root / ".gateway-state.json").exists() is False
    assert (runtime_root / "workspace" / "assistant").is_dir() is True
    assert (runtime_root / "workspace" / "agent-m170-alpha").is_dir() is True
    assert (runtime_root / "workspace" / "agent-m170-beta").is_dir() is True


def test_rebuild_runtime_writes_canonical_m170_node_config(
    monkeypatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "m170-runtime"
    _patch_runtime_paths(monkeypatch, runtime_root)
    monkeypatch.setattr(
        m170_runtime,
        "stop_runtime",
        lambda timeout_seconds=m170_runtime.DEFAULT_STOP_TIMEOUT_SECONDS: {},
    )

    m170_runtime.rebuild_runtime()

    payload = yaml.safe_load(
        (runtime_root / "node-config.yaml").read_text(encoding="utf-8")
    )

    assert payload["node"] == {"node_id": "m170-node"}
    assert [agent["agent_id"] for agent in payload["agents"]] == [
        "assistant",
        "agent-m170-alpha",
        "agent-m170-beta",
    ]
    assert [agent["title"] for agent in payload["agents"]] == [
        "My Assistant",
        "Agent M170 Alpha",
        "Agent M170 Beta",
    ]
    assert payload["im_service"] == {"url": "http://127.0.0.1:18031"}
    assert "18070" in payload["kernel"]["command"]


def test_rebuild_runtime_seeds_canonical_agent_profiles_into_fresh_db(
    monkeypatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "m170-runtime"
    _patch_runtime_paths(monkeypatch, runtime_root)
    monkeypatch.setattr(
        m170_runtime,
        "stop_runtime",
        lambda timeout_seconds=m170_runtime.DEFAULT_STOP_TIMEOUT_SECONDS: {},
    )

    m170_runtime.rebuild_runtime()

    connection = sqlite3.connect(runtime_root / "im_service.sqlite3")
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT agent_id, owner_id, node_id, display_name, description, system_prompt, group_reply_policy, workspace_root
            FROM agent_profiles
            ORDER BY rowid
            """
        ).fetchall()
    finally:
        connection.close()

    assert [dict(row) for row in rows] == [
        {
            "agent_id": "assistant",
            "owner_id": "",
            "node_id": None,
            "display_name": "assistant",
            "description": "Runtime agent advertised by m170-node.",
            "system_prompt": "You are assistant.",
            "group_reply_policy": "MENTION",
            "workspace_root": str((runtime_root / "workspace" / "assistant").resolve()),
        },
        {
            "agent_id": "agent-m170-alpha",
            "owner_id": "",
            "node_id": None,
            "display_name": "Agent M170 Alpha",
            "description": "Runtime agent advertised by m170-node.",
            "system_prompt": "Reply exactly with ALPHA_ACK_M170.",
            "group_reply_policy": "MENTION",
            "workspace_root": str(
                (runtime_root / "workspace" / "agent-m170-alpha").resolve()
            ),
        },
        {
            "agent_id": "agent-m170-beta",
            "owner_id": "",
            "node_id": None,
            "display_name": "Agent M170 Beta",
            "description": "Runtime agent advertised by m170-node.",
            "system_prompt": "Reply exactly with BETA_ACK_M170.",
            "group_reply_policy": "MENTION",
            "workspace_root": str(
                (runtime_root / "workspace" / "agent-m170-beta").resolve()
            ),
        },
    ]


def test_resolve_canonical_repo_root_collapses_worktree_checkout_to_main_repo() -> None:
    script_path = Path(
        "/repo/nano-multiagent/.worktrees/M204/scripts/acceptance/m170_runtime.py"
    )

    resolved = m170_runtime._resolve_canonical_repo_root(script_path)

    assert resolved == Path("/repo/nano-multiagent")
    assert resolved / "ACCEPTANCE" / "m170-runtime" == Path(
        "/repo/nano-multiagent/ACCEPTANCE/m170-runtime"
    )


def test_stop_runtime_terminates_duplicate_gateway_and_kernel_processes(
    monkeypatch, tmp_path: Path
) -> None:
    runtime_root = tmp_path / "m170-runtime"
    _patch_runtime_paths(monkeypatch, runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "node-config.yaml").write_text(
        "node:\n  node_id: m170-node\nagents:\n- agent_id: assistant\n",
        encoding="utf-8",
    )
    (runtime_root / ".gateway-state.json").write_text('{"pid": 200}', encoding="utf-8")
    (runtime_root / ".im-state.json").write_text('{"pid": 300}', encoding="utf-8")

    monkeypatch.setattr(
        m170_runtime,
        "stop_gateway",
        lambda config_path: f"STOPPED config={config_path}",
    )
    monkeypatch.setattr(
        m170_runtime, "_wait_for_url", lambda url, timeout_seconds: False
    )
    monkeypatch.setattr(
        m170_runtime, "_list_gateway_pids_for_config", lambda config_path: {111, 200}
    )
    monkeypatch.setattr(m170_runtime, "_list_listener_pids", lambda port: {222, 300})
    terminated: list[tuple[int, float]] = []
    monkeypatch.setattr(
        m170_runtime,
        "_terminate_pid",
        lambda pid, timeout_seconds: terminated.append((pid, timeout_seconds)),
    )
    kill_calls: list[tuple[int, int]] = []

    def _fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(m170_runtime.os, "kill", _fake_kill)

    result = m170_runtime.stop_runtime(timeout_seconds=3.5)

    assert result["gateway"] == f"STOPPED config={runtime_root / 'node-config.yaml'}"
    assert result["im_url_stopped"] == "true"
    assert terminated == [(111, 3.5), (222, 3.5)]
    assert kill_calls == [(200, 0), (300, m170_runtime.signal.SIGTERM)]
    assert (runtime_root / ".im-state.json").exists() is False


def test_resolve_canonical_repo_root_keeps_main_checkout_path() -> None:
    script_path = Path("/repo/nano-multiagent/scripts/acceptance/m170_runtime.py")

    resolved = m170_runtime._resolve_canonical_repo_root(script_path)

    assert resolved == Path("/repo/nano-multiagent")
    assert resolved / "ACCEPTANCE" / "m170-runtime" == Path(
        "/repo/nano-multiagent/ACCEPTANCE/m170-runtime"
    )
