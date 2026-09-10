"""Global Agent execution bindings survive config updates and registration."""

from dataclasses import replace
import json
from pathlib import Path

import httpx
import pytest
import yaml

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LocalConfig,
    NodeConfig,
    RuntimeConfigOwner,
    load_local_config,
    save_local_config,
)
from personal_assistant.gateway.agent_config_sync import agent_operation_fingerprint
from personal_assistant.gateway.config_apply_receipts import ConfigApplyReceiptStore
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from tests.unit.personal_assistant._config_operation_helpers import (
    _agent_payload,
    _llm,
    _sync,
)


def _config(tmp_path: Path, mode: str = "global") -> LocalConfig:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(
            AgentWorkspaceConfig(
                agent_id="agent",
                workspace_root=workspace,
                work_mode=mode,
                default_model="test:model",
                title="Agent",
            ),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "config.yaml",
    )
    save_local_config(config, config.source_path)
    return config


@pytest.mark.parametrize("mode", ["single_thread", "global"])
def test_work_mode_roundtrip_and_registration(tmp_path: Path, mode: str) -> None:
    config = _config(tmp_path, mode)
    loaded = load_local_config(config.source_path)
    assert loaded.agents[0].work_mode == mode
    reporter = UpstreamReporter(
        node=config.node,
        agents=loaded.agents,
        send_frame=lambda *_: None,
    )
    assert reporter.send_register()["agent_work_modes"] == {"agent": mode}
    if mode == "single_thread":
        raw = yaml.safe_load(config.source_path.read_text())
        raw["agents"][0].pop("work_mode")
        config.source_path.write_text(yaml.safe_dump(raw))
        assert load_local_config(config.source_path).agents[0].work_mode == mode


def test_legacy_apply_retains_global_binding_across_retry(tmp_path: Path) -> None:
    config = _config(tmp_path)
    previous = {**_agent_payload(config.agents[0]), "work_mode": "global"}
    candidate = {**previous, "display_name": "Updated"}
    candidate.pop("work_mode")
    request = {
        "operation_id": "legacy-apply",
        "candidate_fingerprint": agent_operation_fingerprint(candidate),
        "expected_previous_fingerprint": agent_operation_fingerprint(previous),
        "agent": candidate,
    }
    receipts = ConfigApplyReceiptStore(tmp_path / "receipts.json")
    sync = _sync(config, receipts=receipts)
    result = sync.handle_agent_config_operation("apply", request)
    assert result["status"] == "applied", result
    applied = load_local_config(config.source_path)
    assert applied.agents[0].work_mode == "global"
    assert applied.agents[0].workspace_root == config.agents[0].workspace_root
    assert applied.agents[0].title == "Updated"
    assert (
        _sync(applied, receipts=receipts).handle_agent_config_operation(
            "apply", request
        )
        == result
    )


@pytest.mark.parametrize("invalid_mode", [None, "", "threaded", []])
def test_yaml_rejects_invalid_work_mode(tmp_path: Path, invalid_mode: object) -> None:
    config = _config(tmp_path)
    raw = yaml.safe_load(config.source_path.read_text())
    raw["agents"][0]["work_mode"] = invalid_mode
    config.source_path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="work_mode"):
        load_local_config(config.source_path)


@pytest.mark.parametrize("change", ["mode", "workspace"])
def test_apply_rejects_global_identity_changes(tmp_path: Path, change: str) -> None:
    config = _config(tmp_path)
    previous = {**_agent_payload(config.agents[0]), "work_mode": "global"}
    candidate = dict(previous)
    if change == "mode":
        candidate["work_mode"] = "single_thread"
    else:
        candidate["workspace_root"] = str(tmp_path / "other")
    sync = _sync(config, receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"))
    result = sync.handle_agent_config_operation(
        "apply",
        {
            "operation_id": "invalid-apply",
            "candidate_fingerprint": agent_operation_fingerprint(candidate),
            "expected_previous_fingerprint": agent_operation_fingerprint(previous),
            "agent": candidate,
        },
    )
    assert result["status"] == "rejected"
    assert load_local_config(config.source_path).agents == config.agents
    assert not (tmp_path / "other").exists()


@pytest.mark.parametrize("method", ["replace", "persist"])
@pytest.mark.parametrize("change", ["mode", "workspace"])
def test_runtime_owner_rejects_global_identity_changes(
    tmp_path: Path,
    method: str,
    change: str,
) -> None:
    config = _config(tmp_path)
    original = config.source_path.read_bytes()
    agent = config.agents[0]
    updated = replace(
        config,
        agents=(
            replace(
                agent,
                **(
                    {"work_mode": "single_thread"}
                    if change == "mode"
                    else {
                        "workspace_root": tmp_path / "other",
                    }
                ),
            ),
        ),
    )
    owner = RuntimeConfigOwner(config)
    with pytest.raises(ValueError, match="immutable"):
        if method == "replace":
            owner.replace(updated)
        else:
            owner.persist(lambda _: updated, save_config=save_local_config)
    assert owner.snapshot() == config
    assert config.source_path.read_bytes() == original


def test_skill_patch_preserves_omitted_work_mode(tmp_path: Path) -> None:
    config = _config(tmp_path)
    sync = _sync(config, receipts=ConfigApplyReceiptStore(tmp_path / "receipts.json"))
    sent = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"agent_id": "agent"})

    with httpx.Client(
        transport=httpx.MockTransport(respond), base_url="http://im.test"
    ) as client:
        sync._client = client
        sync._patch_agent_skills("agent", {"skills": []}, ["plan"])
        sync._patch_agent_skills(
            "agent", {"skills": [], "work_mode": "global"}, ["plan"]
        )
    assert "work_mode" not in sent[0]
    assert sent[1]["work_mode"] == "global"
