"""Regression test: committed heartbeat config reaches the scheduler mirror."""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import httpx
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository
from personal_assistant.config.local_store import AgentWorkspaceConfig
from tests.helpers.inbound_pipeline import build_inbound_pipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)
from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

from ._gateway_helpers import (
    _FakeKernelClient,
    make_agent_configs,
    seed_user,
)


def _seed_heartbeat_enabled_agent(app, *, agent_id: str, owner_id: str) -> None:
    """Upsert one agent profile with heartbeat enabled (features.heartbeat=True)."""
    profiles = AgentProfileRepository(app.state.connection)
    profiles.upsert_profile(
        agent_id=agent_id,
        owner_id=owner_id,
        display_name=agent_id,
        description=f"profile for {agent_id}",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
        features={"heartbeat": True},
    )
    app.state.connection.execute(
        "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
        ("node-1", agent_id),
    )
    app.state.connection.commit()


def test_patch_heartbeat_disabled_reaches_scheduler(tmp_path: Path) -> None:
    """Disabling heartbeat after Gateway apply must stop the scheduler within one tick.

    Full pipeline exercised (no mocks on the communication path):
      IM PATCH features.heartbeat=False → Gateway applied result → IM commit
      → legacy mirror convergence reads GET /config?source=mirror
      → pipeline.register_agent(new AgentWorkspaceConfig(heartbeat_enabled=False))
      → HeartbeatScheduler.tick() skips the agent
    """
    agent_id = "hb-test-agent"
    app = create_app(db_path=tmp_path / "im.db")

    with TestClient(app) as client:
        # Setup: register owner, node, agent with heartbeat ON
        owner_id = seed_user(client, "owner")
        real_owner_id = (
            UserRepository(app.state.connection).get_user(user_id=owner_id).owner_id
        )
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1",
            node_name="Test",
            status="online",
            version="1.0.0",
            owner_id=real_owner_id,
        )
        _seed_heartbeat_enabled_agent(app, agent_id=agent_id, owner_id=real_owner_id)

        # Build gateway-side pipeline with heartbeat initially ON
        agents = make_agent_configs(tmp_path, agent_id)
        # Override: mark agent as heartbeat-enabled in memory (matching IM)
        agent_with_hb = AgentWorkspaceConfig(
            agent_id=agents[0].agent_id,
            workspace_root=agents[0].workspace_root,
            title=agents[0].title,
            features={"heartbeat": True},
        )
        kernel_client = _FakeKernelClient()
        from personal_assistant.gateway.channel_registry import ChannelRegistry
        from personal_assistant.channels.web_relay_adapter import WebRelayAdapter

        relay_adapter = WebRelayAdapter()
        run_queue = SessionRunQueue()
        session_store = SessionBindingStore()
        catalog = LiveAgentCatalog((agent_with_hb,))
        binder = GatewaySessionBinder(
            catalog=catalog, repository=session_store, kernel=kernel_client
        )
        pipeline = build_inbound_pipeline(
            kernel=kernel_client,
            agents=(agent_with_hb,),
            outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
            run_queue=run_queue,
            session_store=session_store,
            agent_catalog=catalog,
            session_binder=binder,
            default_agent_id=agent_id,
        )

        # Verify initial state: heartbeat enabled
        assert catalog.require(agent_id).config.heartbeat_enabled is True

        # Wire sync_client: uses the IM app's HTTP interface via ASGITransport
        # so sync_agent can GET /im/v1/agents/{id}/config?source=mirror from the
        # real IM app without a network port.
        # Access token from the client's current headers (set by seed_user).
        auth_token = (
            (client.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        )

        # Use TestClient's own sync transport so sync_agent can reach the real IM app
        # without a listening port.  The transport is the same one TestClient uses for
        # HTTP requests, so auth tokens and DB state are shared.
        im_http_client = httpx.Client(
            transport=client._transport,  # starlette._TestClientTransport (sync)
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {auth_token}"},
            trust_env=False,
        )
        from personal_assistant.config.local_store import (
            GatewayLifecycleConfig,
            HeartbeatConfig,
            IMServiceConfig,
            LocalConfig,
            NodeConfig,
        )

        _llm = LLMConfigPayload(
            default_model="test-model",
            providers=(
                LLMProviderPayload(
                    name="test",
                    base_url="http://127.0.0.1:4000",
                    models=(LLMModelPayload(name="test-model"),),
                ),
            ),
        )
        local_config = LocalConfig(
            node=NodeConfig(node_id="node-1", user_id=None),
            agents=(agent_with_hb,),
            channels=(),
            gateway=GatewayLifecycleConfig(),
            heartbeat=HeartbeatConfig(),
            im_service=IMServiceConfig(url="http://testserver"),
            llm=_llm,
            source_path=tmp_path / "config.yaml",
        )
        im_sync_client = IMAgentConfigSync(
            base_url="http://testserver",
            token=auth_token,
            agent_catalog=catalog,
            session_binder=binder,
            local_config=local_config,
            client=im_http_client,
            monotonic=lambda: 0.0,
            sleep=lambda _: None,
        )
        # Wire scheduler with live agents getter
        state_store = HeartbeatSchedulerStateStore(tmp_path / "heartbeat-state.json")
        scheduler = HeartbeatScheduler(
            agents=(),
            kernel_client=kernel_client,
            state_store=state_store,
            agent_catalog=catalog,
        )

        # Connect a gateway WS to IM
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "Test",
                        "version": "1.0.0",
                        "agents": [agent_id],
                        "capabilities": {"relay": True},
                    },
                }
            )
            websocket.receive_json()  # ack

            current = client.get(f"/im/v1/agents/{agent_id}/config?source=mirror")
            assert current.status_code == 200
            current_version = current.json()["profile_version"]

            # PATCH: disable heartbeat (the action under test)
            patch_result: dict[str, object] = {}
            patch_payload = {
                "profile_version": current_version,
                "display_name": agent_id,
                "description": "",
                "custom_prompt": f"You are {agent_id}.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "features": {"heartbeat": False},
            }

            def _patch_config() -> None:
                patch_result["response"] = client.patch(
                    f"/im/v1/agents/{agent_id}/config", json=patch_payload
                )

            patch_worker = threading.Thread(target=_patch_config)
            patch_worker.start()
            apply_frame = websocket.receive_json()
            assert apply_frame["type"] == "agent.config.apply"
            apply_payload = apply_frame["payload"]
            websocket.send_json(
                {
                    "type": "agent.config.apply.result",
                    "payload": {
                        "request_id": apply_payload["request_id"],
                        "node_id": "node-1",
                        "operation_id": apply_payload["operation_id"],
                        "status": "applied",
                        "candidate_fingerprint": apply_payload["candidate_fingerprint"],
                        "agent": apply_payload["agent"],
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            patch_worker.join(timeout=5)
            patched = patch_result["response"]
            assert patched.status_code == 200, patched.text
            im_sync_client.sync_agent(
                agent_id=agent_id,
                profile_version=patched.json()["profile_version"],
            )

        # After sync_agent ran, pipeline._agents must reflect heartbeat=False
        updated_agent = catalog.require(agent_id).config
        assert updated_agent.heartbeat_enabled is False, (
            f"Expected heartbeat_enabled=False after config.sync, "
            f"got features={updated_agent.features!r}. "
            "Bug: sync_agent did not update pipeline._agents correctly."
        )

        # Scheduler tick must skip this agent
        summary = asyncio.run(scheduler.tick())
        assert agent_id in summary.skipped_agents, (
            f"Expected scheduler to skip {agent_id!r} after heartbeat disabled, "
            f"but skipped_agents={summary.skipped_agents!r}."
        )
        assert len(summary.triggered_runs) == 0
