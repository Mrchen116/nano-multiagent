from __future__ import annotations

from pathlib import Path

from scripts.acceptance import m170_runtime


def test_rebuild_runtime_clears_stale_artifacts_and_recreates_layout(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "m170-runtime"
    monkeypatch.setattr(m170_runtime, "RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(m170_runtime, "RUNTIME_DB", runtime_root / "im_service.sqlite3")
    monkeypatch.setattr(m170_runtime, "RUNTIME_CONFIG", runtime_root / "node-config.yaml")
    monkeypatch.setattr(m170_runtime, "RUNTIME_IM_LOG", runtime_root / "im.log")
    monkeypatch.setattr(m170_runtime, "RUNTIME_GATEWAY_LOG", runtime_root / "gateway.log")
    monkeypatch.setattr(m170_runtime, "RUNTIME_HEARTBEAT_STATE", runtime_root / "heartbeat-state.json")
    monkeypatch.setattr(m170_runtime, "RUNTIME_GATEWAY_STATE", runtime_root / ".gateway-state.json")
    monkeypatch.setattr(m170_runtime, "RUNTIME_UPLOADS", runtime_root / "uploads")
    monkeypatch.setattr(m170_runtime, "RUNTIME_WORKSPACE", runtime_root / "workspace")

    runtime_root.mkdir(parents=True)
    (runtime_root / "im_service.sqlite3").write_text("old-db", encoding="utf-8")
    (runtime_root / "gateway.log").write_text("old-gateway", encoding="utf-8")
    (runtime_root / "im.log").write_text("old-im", encoding="utf-8")
    (runtime_root / "heartbeat-state.json").write_text("old-heartbeat", encoding="utf-8")
    (runtime_root / ".gateway-state.json").write_text("{}", encoding="utf-8")
    (runtime_root / "uploads").mkdir()
    (runtime_root / "uploads" / "stale.txt").write_text("stale", encoding="utf-8")
    (runtime_root / "workspace").mkdir()
    (runtime_root / "workspace" / "stale.txt").write_text("stale", encoding="utf-8")

    stop_calls: list[float] = []
    monkeypatch.setattr(m170_runtime, "stop_runtime", lambda timeout_seconds=m170_runtime.DEFAULT_STOP_TIMEOUT_SECONDS: stop_calls.append(timeout_seconds) or {})

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

    config_text = (runtime_root / "node-config.yaml").read_text(encoding="utf-8")
    assert "m170-node" in config_text
    assert "18031" in config_text
    assert "18070" in config_text
