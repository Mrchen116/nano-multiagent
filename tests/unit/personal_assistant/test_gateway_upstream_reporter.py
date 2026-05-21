"""Unit tests for UpstreamReporter: node.register, heartbeat, report, delivery_receipt."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import NodeConfig
from personal_assistant.reporter.upstream_reporter import UpstreamReporter, build_runtime_capabilities

from ._im_connection_helpers import _agents, _write_skill


def test_upstream_reporter_builds_register_heartbeat_report_and_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frames: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_skill(tmp_path / ".nanoassistant" / "skills", "plan")
    _write_skill(tmp_path / ".claude" / "skills", "playwright", frontmatter_name='"playwright"')
    gstack_target_root = tmp_path / ".gstack" / "repos" / "gstack" / ".agents" / "skills"
    _write_skill(gstack_target_root, "gstack-plan-design-review", frontmatter_name="plan-design-review")
    codex_skills_root = tmp_path / ".codex" / "skills"
    codex_skills_root.mkdir(parents=True, exist_ok=True)
    (codex_skills_root / "gstack-plan-design-review").symlink_to(gstack_target_root / "gstack-plan-design-review", target_is_directory=True)
    agents = _agents(tmp_path)
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1", user_id="user-1"),
        agents=agents,
        send_frame=lambda message_type, payload: frames.append((message_type, payload)),
        capabilities=build_runtime_capabilities(),
        node_name="MacBook",
        version="1.2.3",
    )

    register = reporter.send_register()
    heartbeat = reporter.send_heartbeat(status="online", last_error=None, extra={"running_runs": 2})
    report = reporter.send_report(run_id="run-1", status="completed", agent_id="agent-a", session_key="web:user:agent-a")
    receipt = reporter.send_delivery_receipt(relay_task_id="relay-1", delivery_status="completed", detail="ok")

    assert register["node_id"] == "node-1"
    assert register["agents"] == ["agent-a"]
    assert register["capabilities"] == {"relay": True, "send_message": True, "config_sync": True}
    assert "capabilities" not in heartbeat
    assert heartbeat["running_runs"] == 2
    assert report["run_id"] == "run-1"
    assert receipt["relay_task_id"] == "relay-1"
    assert [item[0] for item in frames] == [
        "node.register",
        "node.heartbeat",
        "node.report",
        "node.delivery_receipt",
    ]
