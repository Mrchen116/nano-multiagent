"""Durable Gateway Agent config-operation recovery tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
    LocalConfig,
    NodeConfig,
    RuntimeConfigOwner,
    load_local_config,
    save_local_config,
)
from personal_assistant.config.model_reasoning import (
    ModelReasoningCatalog,
    ModelReasoningCapability,
)
from personal_assistant.gateway import agent_config_sync as sync_module
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync,
    agent_operation_fingerprint,
    canonical_agent_operation_payload,
)
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore


class _InjectedCrash(RuntimeError):
    pass


def _llm() -> LLMConfigPayload:
    return LLMConfigPayload(
        default_model="test:model",
        providers=(
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:1",
                models=(
                    LLMModelPayload(
                        name="test:model",
                        reasoning=ModelReasoningCapability(
                            kind="selectable",
                            default="high",
                            levels=("low", "high", "max"),
                        ),
                    ),
                ),
            ),
        ),
    )


def _agent_payload(agent: AgentWorkspaceConfig) -> dict[str, object]:
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.title or agent.agent_id,
        "skills": list(agent.skills),
        "tool_allowlist": list(agent.tool_allowlist),
        "group_reply_policy": agent.group_reply_policy or "manual",
        "default_model": agent.default_model,
        "reasoning_effort": agent.reasoning_effort,
        "workspace_root": str(agent.workspace_root),
        "features": dict(agent.features),
        "custom_prompt": agent.custom_prompt,
        "heartbeat_json": None,
    }


def _sync(
    config: LocalConfig,
    *,
    receipts: ConfigApplyReceiptStore,
    phase_hook=None,
) -> IMAgentConfigSync:
    catalog = LiveAgentCatalog(config.agents)
    return IMAgentConfigSync(
        base_url="http://im.invalid",
        token=None,
        agent_catalog=catalog,
        session_binder=object(),  # type: ignore[arg-type]
        local_config=config,
        config_owner=RuntimeConfigOwner(config),
        workspace_root_factory=lambda agent_id: (
            config.source_path.parent / "workspaces" / agent_id
        ),
        reasoning_catalog=ModelReasoningCatalog(config.llm),
        operation_receipts=receipts,
        operation_phase_hook=phase_hook,
    )


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
