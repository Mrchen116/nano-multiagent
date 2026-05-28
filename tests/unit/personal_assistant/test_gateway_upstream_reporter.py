"""Unit tests for UpstreamReporter: node.register, heartbeat, report, delivery_receipt."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import NodeConfig
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_node_capabilities_payload,
    build_runtime_capabilities,
)

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


def test_build_runtime_capabilities_default_system_prompt_has_no_runtime_fill_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """default_system_prompt exposed via node.capabilities must not contain RUNTIME_FILL
    placeholders (feat-379-M5 ISSUE-4).

    The sections-based prompt assembler replaced RUNTIME_FILL tokens; sending the raw
    template to the IM frontend causes garbage text in the agent-create system_prompt
    prefill.  The field must be either a clean rendered string or empty.
    """
    caps = build_runtime_capabilities()
    assert "<RUNTIME_FILL:" not in caps.default_system_prompt, (
        "default_system_prompt must not contain <RUNTIME_FILL:*> placeholders — "
        "use empty string or a pre-rendered template (feat-379-M5 ISSUE-4)"
    )


# ---------------------------------------------------------------------------
# feat-379-M7 ISSUE-1: node-level capabilities must carry FEATURE_REGISTRY projection
# ---------------------------------------------------------------------------


def test_build_node_capabilities_payload_includes_features() -> None:
    """node.capabilities.resolve must return a non-empty features list.

    ISSUE-1 root cause: the handler called build_runtime_capabilities().as_payload()
    which has no 'features' key.  We now call build_node_capabilities_payload() which
    injects a FEATURE_REGISTRY projection with available=True for all entries (node
    level has no per-agent tool_allowlist to constrain availability).
    """
    payload = build_node_capabilities_payload()
    assert "features" in payload, "node capabilities payload must carry 'features' key"
    features = payload["features"]
    assert isinstance(features, list) and len(features) > 0, (
        "features must be a non-empty list — FEATURE_REGISTRY has at least memory_curation"
    )
    for item in features:
        assert isinstance(item, dict)
        assert "key" in item
        assert "default_on" in item
        # Node-level: no per-agent allowlist → every feature is available
        assert item.get("available") is True, (
            f"node-level feature '{item.get('key')}' must have available=True "
            "(no tool_allowlist constrains node caps)"
        )


def test_build_node_capabilities_payload_has_required_keys() -> None:
    """node capabilities payload must carry models, skills, tools, features."""
    payload = build_node_capabilities_payload()
    for key in ("models", "skills", "tools", "features", "platform_default_model"):
        assert key in payload, f"node capabilities payload missing '{key}'"


# ---------------------------------------------------------------------------
# feat-379-M9 R1 (决策 13): _build_tool_names 必须含 memory / skill_manage
# ---------------------------------------------------------------------------


def test_build_tool_names_includes_memory_and_skill_manage() -> None:
    """capabilities.tools 必须含 memory 和 skill_manage。

    缺陷 A 根因：_build_tool_names() 以 runtime=None/hook_runner=None 建 registry，
    memory/skill_manage 需路径注入才进 list_specs() 的返回集合，导致即使它们在
    default_tool_ids 中也被过滤掉。修复后改为直接取 PERSONAL_ASSISTANT_PROFILE 的
    default_tool_ids + optional_tool_ids，确保工具名静态可达。
    """
    from personal_assistant.reporter.upstream_reporter import _build_tool_names

    names = _build_tool_names()
    assert "memory" in names, (
        "memory 必须在 capabilities.tools 中 — 否则前端联动无法把 memory 工具变绿 (feat-379-M9 决策13)"
    )
    assert "skill_manage" in names, (
        "skill_manage 必须在 capabilities.tools 中 — 否则前端联动无法把 skill_manage 变绿 (feat-379-M9 决策13)"
    )


def test_build_tool_names_contains_all_feature_registry_requires_tool() -> None:
    """capabilities.tools 必须含 FEATURE_REGISTRY 中所有 requires_tool 工具。

    联动逻辑（决策 12）依赖前端从 capabilities.tools 取工具名——若工具不在列表，
    勾特性时找不到落点，联动失效。
    """
    from personal_assistant.reporter.upstream_reporter import _build_tool_names
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    names_set = set(_build_tool_names())
    for entry in FEATURE_REGISTRY.values():
        rt = entry.get("requires_tool")
        if rt is not None:
            assert rt in names_set, (
                f"FEATURE_REGISTRY 要求工具 '{rt}' 必须在 capabilities.tools 中 (feat-379-M9 决策13)"
            )
