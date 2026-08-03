"""cron_enabled sync IM → AgentWorkspaceConfig.

cron.enabled in IM AgentProfile (via features["cron_scheduling"]) must flow to
AgentWorkspaceConfig.cron_enabled via the sync client, so the scheduler gate
and prompt enabled_when gate work correctly.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    IMServiceConfig,
    GatewayLifecycleConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.gateway.agent_config_sync import (
    IMAgentConfigSync as _IMConfigSyncClient,
)
from tests.unit.personal_assistant._config_sync_test_owners import (
    build_config_sync_test_owners,
)


from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(LLMModelPayload(name="kimiCoding:K2.6"),),
        ),
    ),
)


def _make_local_config(tmp_path: Path, workspace_root: Path) -> LocalConfig:
    return LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(
            AgentWorkspaceConfig(agent_id="test-agent", workspace_root=workspace_root),
        ),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "config.yaml",
    )


# ---------------------------------------------------------------------------
# cron_enabled field sync tests
# ---------------------------------------------------------------------------


def test_sync_agent_passes_through_cron_enabled(tmp_path: Path) -> None:
    """sync_agent must write cron_enabled=True when IM payload has features.cron_scheduling=true.

    feat-394 M9-E: cron enable lives in features["cron_scheduling"]; the sync path reads
    it directly from payload["features"] without parsing the legacy cron JSON block.
    """
    workspace_root = tmp_path / "ws-cron"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "cron-agent",
                "display_name": "Cron Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
                # M9-E: enable comes from features, not cron JSON block
                "features": {"cron_scheduling": True},
            },
        )

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    sync.sync_agent(agent_id="cron-agent", profile_version=1)

    registered = owners.catalog.require("cron-agent").config
    assert registered.cron_enabled is True


def test_sync_agent_cron_disabled_by_default(tmp_path: Path) -> None:
    """When IM payload has no cron block, cron_enabled must default to False."""
    workspace_root = tmp_path / "ws-nocron"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "nocron-agent",
                "display_name": "No Cron Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
            },
        )

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    sync.sync_agent(agent_id="nocron-agent", profile_version=1)

    registered = owners.catalog.require("nocron-agent").config
    assert registered.cron_enabled is False


# ---------------------------------------------------------------------------
# feat-394 fix (supersedes M3 WARNING-1): cron is a gated capability decoupled
# from the user tool whitelist. cron_enabled must NEVER be written into
# tool_allowlist — it flows only via AgentWorkspaceConfig.cron_enabled and is
# appended to the effective session toolset at session-build time (see
# resolve_effective_tool_allowlist). Conflating the two turned an "unconfigured"
# allowlist into a configured ["cron"], which forced the R5-2 default-merge and
# made default tools impossible to disable.
# ---------------------------------------------------------------------------


def test_sync_agent_cron_enabled_does_not_pollute_tool_allowlist(
    tmp_path: Path,
) -> None:
    """cron_enabled=True must leave tool_allowlist untouched (no implicit 'cron').

    The user's saved whitelist is their explicit intent; cron is gated separately by
    cron_enabled. Injecting 'cron' here is what broke the whitelist semantics.
    """
    workspace_root = tmp_path / "ws-crongate"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "gate-agent",
                "display_name": "Gate Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
                # M9-E: enable comes from features, not cron JSON block
                "features": {"cron_scheduling": True},
                "tool_allowlist": ["read", "write"],
            },
        )

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    sync.sync_agent(agent_id="gate-agent", profile_version=1)

    registered = owners.catalog.require("gate-agent").config
    assert registered.cron_enabled is True
    assert tuple(registered.tool_allowlist) == ("read", "write"), (
        "cron_enabled must NOT mutate the stored tool_allowlist — cron is a gated "
        "capability appended at session-build, not a whitelist entry"
    )


def test_sync_agent_empty_allowlist_stays_empty_when_cron_enabled(
    tmp_path: Path,
) -> None:
    """Empty whitelist + cron on → tool_allowlist stays empty (cron not injected).

    This is the exact reported state: user enabled the CronCard switch without
    selecting any tool; the stored whitelist must remain empty so the UI faithfully
    reflects 'using defaults', not a phantom ['cron'] selection.
    """
    workspace_root = tmp_path / "ws-cronnogate"
    workspace_root.mkdir()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "nogate-agent",
                "display_name": "No Gate Agent",
                "profile_version": 1,
                "workspace_root": str(workspace_root),
                # M9-E: enable comes from features, not cron JSON block
                "features": {"cron_scheduling": True},
                "tool_allowlist": [],
            },
        )

    local_config = _make_local_config(tmp_path, workspace_root)
    owners = build_config_sync_test_owners(local_config)
    sync = _IMConfigSyncClient(
        base_url="http://im.local",
        token=None,
        **owners.kwargs(),
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler),
            base_url="http://im.local",
            trust_env=False,
        ),
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    sync.sync_agent(agent_id="nogate-agent", profile_version=1)

    registered = owners.catalog.require("nogate-agent").config
    assert registered.cron_enabled is True
    assert tuple(registered.tool_allowlist) == (), (
        "empty whitelist must stay empty; cron_enabled must not inject 'cron'"
    )
