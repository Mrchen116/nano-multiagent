"""Durable Gateway Agent config-operation recovery tests."""

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
from personal_assistant.gateway.agent_config_sync import agent_operation_fingerprint
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore
from tests.unit.personal_assistant._config_operation_helpers import (
    _agent_payload,
    _llm,
    _sync,
)


class _InjectedCrash(RuntimeError):
    pass


@pytest.mark.parametrize("kind", ["create", "apply"])
@pytest.mark.parametrize(
    "crash_phase",
    ["prepared", "workspace_initialized", "config_persisted", "published"],
)
def test_config_operation_recovers_each_write_boundary_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    crash_phase: str,
) -> None:
    seed_workspace = tmp_path / "seed"
    seed_workspace.mkdir()
    target_workspace = tmp_path / "target"
    target_workspace.mkdir()
    target = AgentWorkspaceConfig(
        agent_id="target",
        workspace_root=target_workspace,
        title="Target",
        skills=("plan",),
        tool_allowlist=("read",),
        group_reply_policy="manual",
        default_model="test:model",
        reasoning_effort="low",
    )
    initial = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(agent_id="seed", workspace_root=seed_workspace),
            target,
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(initial, initial.source_path)
    receipts = ConfigApplyReceiptStore(tmp_path / "receipts.json")
    save_count = 0
    real_save = sync_module.save_local_config

    def counting_save(config: LocalConfig, path: str | Path) -> None:
        nonlocal save_count
        save_count += 1
        real_save(config, path)

    monkeypatch.setattr(sync_module, "save_local_config", counting_save)

    if kind == "create":
        agent = {
            "agent_id": "created",
            "display_name": "Created",
            "skills": ["plan"],
            "tool_allowlist": ["read"],
            "group_reply_policy": "manual",
            "default_model": "test:model",
            "reasoning_effort": "high",
            "workspace_root": None,
            "features": {"heartbeat": True},
            "custom_prompt": "Be precise.",
            "heartbeat_json": '{"every":"45m"}',
        }
        expected = None
    else:
        agent = {
            **_agent_payload(target),
            "reasoning_effort": "max",
            "heartbeat_json": '{"every":"45m"}',
        }
        expected = agent_operation_fingerprint(_agent_payload(target))
    request = {
        "operation_id": f"op-{kind}-{crash_phase}",
        "candidate_fingerprint": agent_operation_fingerprint(agent),
        "expected_previous_fingerprint": expected,
        "agent": agent,
    }

    def crash_at_phase(phase: str) -> None:
        if phase == crash_phase:
            raise _InjectedCrash(phase)

    with pytest.raises(_InjectedCrash, match=crash_phase):
        _sync(
            initial, receipts=receipts, phase_hook=crash_at_phase
        ).handle_agent_config_operation(kind, request)

    restarted_config = load_local_config(initial.source_path)
    restarted = _sync(restarted_config, receipts=receipts)
    result = restarted.config_operation_status(
        {"operation_id": request["operation_id"]}
    )

    assert result["status"] == "applied"
    assert result["candidate_fingerprint"] == request["candidate_fingerprint"]
    applied_agent = result["agent"]
    assert isinstance(applied_agent, dict)
    assert applied_agent["reasoning_effort"] == ("high" if kind == "create" else "max")
    assert applied_agent["heartbeat_json"] == '{"every":"45m"}'
    assert save_count == 1

    replay = restarted.handle_agent_config_operation(kind, request)
    assert replay == result
    assert save_count == 1
    final_config = load_local_config(initial.source_path)
    final_agents = [
        item
        for item in final_config.agents
        if item.agent_id == applied_agent["agent_id"]
    ]
    assert len(final_agents) == 1
    assert final_agents[0].reasoning_effort == applied_agent["reasoning_effort"]


def test_config_operation_apply_persists_model_fallbacks(tmp_path: Path) -> None:
    workspace = tmp_path / "seed"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="seed",
        workspace_root=workspace,
        title="Seed",
        skills=("plan",),
        tool_allowlist=("read",),
        group_reply_policy="manual",
        default_model="test:model",
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
    gateway = _sync(config, receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"))
    candidate = {**_agent_payload(agent), "model_fallbacks": ["backup:model"]}

    result = gateway.handle_agent_config_operation(
        "apply",
        {
            "operation_id": "op-apply-fallbacks",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": agent_operation_fingerprint(
                _agent_payload(agent)
            ),
            "agent": candidate,
        },
    )

    assert result["status"] == "applied"
    assert result["agent"]["model_fallbacks"] == ["backup:model"]
    restored = load_local_config(config.source_path)
    assert restored.agents[0].model_fallbacks == ("backup:model",)

    replay = gateway.handle_agent_config_operation(
        "apply",
        {
            "operation_id": "op-apply-fallbacks-again",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": agent_operation_fingerprint(candidate),
            "agent": candidate,
        },
    )
    assert replay["status"] == "applied"
