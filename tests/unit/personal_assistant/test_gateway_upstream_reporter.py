"""Unit tests for UpstreamReporter: node.register, heartbeat, report, delivery_receipt."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import NodeConfig
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_agent_capabilities_payload,
    build_node_capabilities_payload,
    build_runtime_capabilities,
)

from ._im_connection_helpers import _agents, _build_test_kernel, _write_skill


def test_upstream_reporter_builds_register_heartbeat_report_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_skill(tmp_path / ".nanoassistant" / "skills", "plan")
    _write_skill(
        tmp_path / ".claude" / "skills", "playwright", frontmatter_name='"playwright"'
    )
    gstack_target_root = (
        tmp_path / ".gstack" / "repos" / "gstack" / ".agents" / "skills"
    )
    _write_skill(
        gstack_target_root,
        "gstack-plan-design-review",
        frontmatter_name="plan-design-review",
    )
    codex_skills_root = tmp_path / ".codex" / "skills"
    codex_skills_root.mkdir(parents=True, exist_ok=True)
    (codex_skills_root / "gstack-plan-design-review").symlink_to(
        gstack_target_root / "gstack-plan-design-review", target_is_directory=True
    )
    agents = _agents(tmp_path)
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1", user_id="user-1"),
        agents=agents,
        send_frame=lambda message_type, payload: frames.append((message_type, payload)),
        capabilities=build_runtime_capabilities(kernel),
        node_name="MacBook",
        version="1.2.3",
    )

    register = reporter.send_register()
    heartbeat = reporter.send_heartbeat(
        status="online", last_error=None, extra={"running_runs": 2}
    )
    report = reporter.send_report(
        run_id="run-1",
        status="completed",
        agent_id="agent-a",
        session_key="web:user:agent-a",
    )
    receipt = reporter.send_delivery_receipt(
        relay_task_id="relay-1", delivery_status="completed", detail="ok"
    )

    assert register["node_id"] == "node-1"
    assert register["agents"] == ["agent-a"]
    assert register["capabilities"] == {
        "relay": True,
        "send_message": True,
        "config_sync": True,
    }
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
    tmp_path: Path,
) -> None:
    """default_system_prompt exposed via node.capabilities must not contain RUNTIME_FILL
    placeholders (feat-379-M5 ISSUE-4).

    The sections-based prompt assembler replaced RUNTIME_FILL tokens; sending the raw
    template to the IM frontend causes garbage text in the agent-create system_prompt
    prefill.  The field must be either a clean rendered string or empty.
    """
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    caps = build_runtime_capabilities(kernel)
    assert "<RUNTIME_FILL:" not in caps.default_system_prompt, (
        "default_system_prompt must not contain <RUNTIME_FILL:*> placeholders — "
        "use empty string or a pre-rendered template (feat-379-M5 ISSUE-4)"
    )


# ---------------------------------------------------------------------------
# feat-379-M7 ISSUE-1: node-level capabilities must carry FEATURE_REGISTRY projection
# ---------------------------------------------------------------------------


def test_build_node_capabilities_payload_includes_features(tmp_path: Path) -> None:
    """node.capabilities.resolve must return a non-empty features list.

    ISSUE-1 root cause: the handler called build_runtime_capabilities().as_payload()
    which has no 'features' key.  We now call build_node_capabilities_payload() which
    injects a feature projection with available=True for all entries (node level has
    no per-agent tool_allowlist to constrain availability).
    """
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    payload = build_node_capabilities_payload(kernel)
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


def test_build_node_capabilities_payload_has_required_keys(tmp_path: Path) -> None:
    """node capabilities payload must carry models, skills, tools, features."""
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    payload = build_node_capabilities_payload(kernel)
    for key in ("models", "skills", "tools", "features", "platform_default_model"):
        assert key in payload, f"node capabilities payload missing '{key}'"


def test_node_capabilities_models_carry_provider(tmp_path: Path) -> None:
    """bugfix-429 R5: each model entry carries its registered provider so the IM
    agent-config dropdown can label the model's format (anthropic / openai_compat)."""
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    payload = build_node_capabilities_payload(kernel)
    models = payload["models"]
    assert isinstance(models, list) and models
    by_name = {m["name"]: m["provider"] for m in models}
    assert by_name["kimiCoding:K2.6"] == "anthropic"
    assert by_name["codex_oauth:gpt-5.5"] == "openai_compat"


# ---------------------------------------------------------------------------
# feat-379-M9 R1 (决策 13): capabilities.tools 必须含 memory / skill_manage
# refactor-406-M2: tools now come from the Gateway projection (capability_projection)
# over the PA default/optional tool split, not the deleted reporter _build_tool_names.
# ---------------------------------------------------------------------------


def test_node_capabilities_tools_include_memory_and_skill_manage(
    tmp_path: Path,
) -> None:
    """capabilities.tools 必须含 memory 和 skill_manage。

    前端联动（决策13）依赖前端从 capabilities.tools 取 feature 要求的工具名把它们
    变绿；memory/skill_manage 在 PA 默认工具集中，投影必须把它们 advertise 出来。
    """
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    payload = build_node_capabilities_payload(kernel)
    names = {t["name"] for t in payload["tools"]}
    assert "memory" in names, (
        "memory 必须在 capabilities.tools 中 — 否则前端联动无法把 memory 工具变绿 (feat-379-M9 决策13)"
    )
    assert "skill_manage" in names, (
        "skill_manage 必须在 capabilities.tools 中 — 否则前端联动无法把 skill_manage 变绿 (feat-379-M9 决策13)"
    )


# ---------------------------------------------------------------------------
# bugfix-404-M2 R1: send_register 帧必须携带 agent_workspaces 字段
# ---------------------------------------------------------------------------


def test_send_register_includes_agent_workspaces(tmp_path: Path) -> None:
    """node.register 帧必须包含 agent_workspaces 映射（bugfix-404-M2 决策 3）。

    修前：帧只有 agents: [id]，不含 workspace_root 信息，IM 首次注册时凭空填 managed default。
    修后：帧还带 agent_workspaces: {agent_id: workspace_root}，让 IM 能用正确路径落库种子。
    """
    from personal_assistant.config.local_store import AgentWorkspaceConfig

    workspace = tmp_path / "my-workspace"
    workspace.mkdir()
    frames: list[tuple[str, dict[str, object]]] = []
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="n1"),
        agents=(AgentWorkspaceConfig(agent_id="Arch", workspace_root=workspace),),
        send_frame=lambda mt, p: frames.append((mt, p)),
        capabilities=build_runtime_capabilities(kernel),
    )
    payload = reporter.send_register()
    assert "agent_workspaces" in payload, (
        "node.register 帧必须含 agent_workspaces 字段 (bugfix-404-M2 决策 3)"
    )
    assert payload["agent_workspaces"] == {"Arch": str(workspace)}, (
        "agent_workspaces 必须是 {agent_id: workspace_root} 映射"
    )


def test_node_capabilities_tools_contain_all_feature_required_tools(
    tmp_path: Path,
) -> None:
    """capabilities.tools 必须含每个 feature 投影的 requires_tool 工具。

    联动逻辑（决策 12）依赖前端从 capabilities.tools 取工具名——若 feature 要求的
    工具不在列表，勾特性时找不到落点，联动失效。refactor-406-M2: 投影的 feature 集
    与 tools 集都出自 Gateway 投影层（capability_projection），此测试守二者一致。
    """
    from personal_assistant.reporter.capability_projection import FEATURE_PROJECTIONS

    kernel = _build_test_kernel(tmp_path / "kernel-root")
    payload = build_node_capabilities_payload(kernel)
    names_set = {t["name"] for t in payload["tools"]}
    for entry in FEATURE_PROJECTIONS:
        rt = entry["requires_tool"]
        if rt is not None:
            assert rt in names_set, (
                f"feature 要求工具 '{rt}' 必须在 capabilities.tools 中 (feat-379-M9 决策13)"
            )


# ---------------------------------------------------------------------------
# feat-430: per-agent capabilities skills must carry SKILL.md location so the
# IM slash picker can distinguish same-named skills at different paths (Q7).
# ---------------------------------------------------------------------------


def test_agent_capabilities_skills_carry_location(tmp_path: Path) -> None:
    """build_agent_capabilities_payload skill entries must expose 'location'."""
    workspace = tmp_path / "agent-ws"
    skills_root = workspace / ".nanoassistant" / "skills"
    _write_skill(skills_root, "doc")
    kernel = _build_test_kernel(tmp_path / "kernel-root")

    payload = build_agent_capabilities_payload(
        kernel, workspace_root=str(workspace)
    )
    skills = payload["skills"]
    assert isinstance(skills, list) and skills
    doc = next(s for s in skills if s["name"] == "doc")
    assert "location" in doc, "skill entry must carry a 'location' key (feat-430)"
    assert isinstance(doc["location"], str) and doc["location"].endswith(
        "doc/SKILL.md"
    )
