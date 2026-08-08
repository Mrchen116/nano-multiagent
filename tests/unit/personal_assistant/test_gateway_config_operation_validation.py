"""Gateway config-operation validation and canonicalization tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LocalConfig,
    NodeConfig,
    load_local_config,
    save_local_config,
)
from personal_assistant.gateway import agent_config_sync as sync_module
from personal_assistant.gateway.agent_config_sync import (
    agent_operation_fingerprint,
    canonical_agent_operation_payload,
)
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore
from tests.unit.personal_assistant._config_operation_helpers import (
    _agent_payload,
    _llm,
    _sync,
)


def test_config_operation_rejects_invalid_effort_and_operation_id_reuse(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(AgentWorkspaceConfig(agent_id="seed", workspace_root=workspace),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    receipts = ConfigApplyReceiptStore(tmp_path / "receipts.json")
    gateway = _sync(config, receipts=receipts)
    agent = {
        "agent_id": "bad",
        "display_name": "Bad",
        "skills": [],
        "tool_allowlist": [],
        "group_reply_policy": "manual",
        "default_model": "test:model",
        "reasoning_effort": "unsupported",
        "workspace_root": None,
        "features": {},
        "custom_prompt": None,
        "heartbeat_json": None,
    }
    request = {
        "operation_id": "op-stable",
        "candidate_fingerprint": agent_operation_fingerprint(agent),
        "expected_previous_fingerprint": None,
        "agent": agent,
    }

    rejected = gateway.handle_agent_config_operation("create", request)
    assert rejected["status"] == "rejected"
    assert rejected["error_code"] == "invalid_agent_config"

    changed = {**agent, "reasoning_effort": "high"}
    reused = gateway.handle_agent_config_operation(
        "create",
        {
            **request,
            "candidate_fingerprint": agent_operation_fingerprint(changed),
            "agent": changed,
        },
    )
    assert reused["status"] == "rejected"
    assert reused["error_code"] == "operation_id_reused"


def test_config_operation_accepts_effort_for_inherited_default_model(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(agent_id="seed", workspace_root=workspace)
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    gateway = _sync(
        config,
        receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"),
    )
    candidate = {**_agent_payload(agent), "reasoning_effort": "max"}

    result = gateway.handle_agent_config_operation(
        "apply",
        {
            "operation_id": "op-inherited-default-effort",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": agent_operation_fingerprint(
                _agent_payload(agent)
            ),
            "agent": candidate,
        },
    )

    assert result["status"] == "applied"
    assert result["agent"]["default_model"] is None
    assert result["agent"]["reasoning_effort"] == "max"
    restored = load_local_config(config.source_path)
    assert restored.agents[0].default_model is None
    assert restored.agents[0].reasoning_effort == "max"


def test_config_operation_rejects_operation_id_reused_with_new_expected_state(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="seed",
        workspace_root=workspace,
        title="Seed",
        default_model="test:model",
        reasoning_effort="low",
    )
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    gateway = _sync(
        config,
        receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"),
    )
    candidate = {**_agent_payload(agent), "reasoning_effort": "high"}
    request = {
        "operation_id": "op-expected",
        "candidate_fingerprint": agent_operation_fingerprint(candidate),
        "expected_previous_fingerprint": agent_operation_fingerprint(
            _agent_payload(agent)
        ),
        "agent": candidate,
    }

    assert (
        gateway.handle_agent_config_operation("apply", request)["status"] == "applied"
    )
    reused = gateway.handle_agent_config_operation(
        "apply",
        {**request, "expected_previous_fingerprint": "different-state"},
    )

    assert reused["status"] == "rejected"
    assert reused["error_code"] == "operation_id_reused"


def test_create_operation_preserves_omitted_skills_until_gateway_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(AgentWorkspaceConfig(agent_id="seed", workspace_root=workspace),),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    monkeypatch.setattr(
        sync_module,
        "_default_pa_global_skill_names",
        lambda: ("global-a", "global-b"),
    )
    gateway = _sync(
        config,
        receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"),
    )
    candidate = {
        "agent_id": "created",
        "display_name": "Created",
        "tool_allowlist": [],
        "group_reply_policy": "manual",
        "default_model": "test:model",
        "reasoning_effort": "high",
        "workspace_root": "",
        "features": {},
        "custom_prompt": "",
        "heartbeat_json": None,
    }
    canonical = canonical_agent_operation_payload(candidate)

    assert canonical["skills"] is None
    assert canonical["custom_prompt"] is None
    assert canonical["workspace_root"] is None
    assert agent_operation_fingerprint(candidate) == agent_operation_fingerprint(
        {**candidate, "skills": None, "custom_prompt": None}
    )

    result = gateway.handle_agent_config_operation(
        "create",
        {
            "operation_id": "op-create-default-skills",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": None,
            "agent": candidate,
        },
    )

    assert result["status"] == "applied"
    assert result["agent"]["skills"] == ["global-a", "global-b"]
    restored = load_local_config(config.source_path)
    created = next(agent for agent in restored.agents if agent.agent_id == "created")
    assert created.skills == ("global-a", "global-b")


def test_apply_operation_rejects_omitted_skills(tmp_path: Path) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(agent_id="seed", workspace_root=workspace)
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    gateway = _sync(
        config,
        receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"),
    )
    candidate = _agent_payload(agent)
    candidate.pop("skills")

    result = gateway.handle_agent_config_operation(
        "apply",
        {
            "operation_id": "op-apply-missing-skills",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": agent_operation_fingerprint(
                _agent_payload(agent)
            ),
            "agent": candidate,
        },
    )

    assert result["status"] == "rejected"
    assert result["error_code"] == "invalid_agent_config"
    assert "requires skills" in result["message"]
