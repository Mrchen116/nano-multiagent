from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    GatewayLifecycleConfig,
    HeartbeatConfig,
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
    LocalConfig,
    NodeConfig,
    normalize_model_fallbacks,
    resolve_model_candidates,
    resolve_run_model,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.model_fallback import (
    ModelStickyStore,
    StickyModelOverride,
    model_chain_changed,
    next_candidate,
    should_failover,
)


def _agent(
    default_model: str | None = "primary",
    fallbacks: tuple[str, ...] = (),
) -> AgentWorkspaceConfig:
    return AgentWorkspaceConfig(
        agent_id="a",
        workspace_root=Path("/tmp/a"),
        default_model=default_model,
        model_fallbacks=fallbacks,
    )


def test_candidates_without_sticky_are_head_then_fallbacks() -> None:
    assert resolve_model_candidates(
        _agent("primary", ("backup", "third")),
        product_default="prod",
        sticky=None,
    ) == ["primary", "backup", "third"]


def test_candidates_with_sticky_skip_earlier_models() -> None:
    assert resolve_model_candidates(
        _agent("primary", ("backup", "third")),
        product_default="prod",
        sticky="backup",
    ) == ["backup", "third"]


def test_empty_fallbacks_are_just_the_chain_head() -> None:
    assert resolve_model_candidates(
        _agent("primary"), product_default="prod", sticky=None
    ) == ["primary"]
    assert resolve_run_model(_agent("primary"), product_default="prod") == "primary"


def test_normalize_drops_primary_and_unknown_ids_raise() -> None:
    assert normalize_model_fallbacks(
        ["primary", "backup", "backup"],
        known_models={"primary", "backup", "third"},
        primary="primary",
        field_name="model_fallbacks",
    ) == ("backup",)
    try:
        normalize_model_fallbacks(
            ["ghost"],
            known_models={"primary"},
            primary="primary",
            field_name="model_fallbacks",
        )
    except ValueError as exc:
        assert "model_fallbacks" in str(exc)
    else:
        raise AssertionError("unknown fallback must conflict")


def test_sticky_store_clears_all_sessions_for_an_agent() -> None:
    store = ModelStickyStore()
    store.set("sess-a", "agent-1", StickyModelOverride("backup"))
    store.set("sess-b", "agent-1", StickyModelOverride("third"))
    store.set("sess-c", "agent-2", StickyModelOverride("other"))
    store.clear_agent("agent-1")
    assert store.get("sess-a") is None
    assert store.get("sess-b") is None
    assert store.get("sess-c") == StickyModelOverride("other")


def test_saving_model_chain_is_detected_for_sticky_reset() -> None:
    previous = _agent("primary", ("backup",))
    same = replace(previous, title="renamed")
    changed = replace(previous, model_fallbacks=("third",))
    assert model_chain_changed(previous, same) is False
    assert model_chain_changed(previous, changed) is True


def test_auth_failsover_and_context_length_does_not() -> None:
    assert should_failover("auth") is True
    assert should_failover("quota") is True
    assert should_failover("context_length") is False
    assert should_failover("other") is False
    assert next_candidate(["primary", "backup"], "primary") == "backup"


def test_publishing_changed_fallbacks_clears_agent_sticky(tmp_path: Path) -> None:
    workspace = tmp_path / "a"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        default_model="primary",
        model_fallbacks=("backup",),
    )
    catalog = LiveAgentCatalog((agent,))
    config = LocalConfig(
        node=NodeConfig(node_id="node-a"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=LLMConfigPayload(
            default_model="primary",
            providers=(
                LLMProviderPayload(
                    name="test",
                    base_url="http://127.0.0.1:4000",
                    models=(
                        LLMModelPayload(name="primary"),
                        LLMModelPayload(name="backup"),
                        LLMModelPayload(name="third"),
                    ),
                ),
            ),
        ),
        source_path=tmp_path / "config.yaml",
    )
    sticky = ModelStickyStore()
    sticky.set("sess-1", "agent-a", StickyModelOverride("backup", noticed=True))
    sync = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        agent_catalog=catalog,
        session_binder=MagicMock(),
        local_config=config,
        sticky_store=sticky,
    )
    sync._publish_agent_config(replace(agent, model_fallbacks=("third",)))
    assert sticky.get("sess-1") is None
