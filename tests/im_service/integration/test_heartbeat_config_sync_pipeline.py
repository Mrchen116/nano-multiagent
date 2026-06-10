"""Regression test: PATCH features.heartbeat=False → config.sync → scheduler skips.

feat-394 bugfix: update_agent_config is a sync FastAPI route. In production uvicorn,
it runs in a thread pool where asyncio.get_running_loop() fails. The previous code fell
back to asyncio.run(push_config_sync(...)), which creates an isolated event loop that
cannot drive the main loop's WebSocket transport — the config.sync WS frame was silently
dropped. This test drives the real pipeline (IM PATCH → WS frame → sync_agent →
pipeline._agents → scheduler tick) without mocking, so the bug would surface as a missing
config.sync frame received by the gateway.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import AgentProfileRepository, NodeRepository, UserRepository
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.config.sync_client import ConfigSyncClient
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.main import _IMConfigSyncClient
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)
from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload

from ._gateway_helpers import (
    _FakeKernelClient,
    make_agent_configs,
    seed_node_and_profiles,
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
        system_prompt=f"You are {agent_id}.",
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
    """Disabling heartbeat via PATCH must stop the scheduler within one tick.

    Full pipeline exercised (no mocks on the communication path):
      IM PATCH features.heartbeat=False
      → WS config.sync frame delivered to connected gateway WS
      → sync_agent HTTP GET /config?source=mirror
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
        pipeline = InboundPipeline(
            kernel=kernel_client,
            agents=(agent_with_hb,),
            outbound_router=OutboundRouter(ChannelRegistry((relay_adapter,))),
            run_queue=run_queue,
            session_store=SessionBindingStore(),
            default_agent_id=agent_id,
        )

        # Verify initial state: heartbeat enabled
        assert pipeline._agents[agent_id].heartbeat_enabled is True  # noqa: SLF001

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
            LocalConfig,
            NodeConfig,
            HeartbeatConfig,
            IMServiceConfig,
            KernelConfig,
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
            kernel=KernelConfig(),
            heartbeat=HeartbeatConfig(),
            im_service=IMServiceConfig(url="http://testserver"),
            llm=_llm,
            source_path=tmp_path / "config.yaml",
        )
        im_sync_client = _IMConfigSyncClient(
            base_url="http://testserver",
            token=auth_token,
            pipeline=pipeline,
            local_config=local_config,
            client=im_http_client,
            monotonic=lambda: 0.0,
            sleep=lambda _: None,
        )
        config_sync_client = ConfigSyncClient(fetcher=im_sync_client.sync_agent)

        # Wire scheduler with live agents getter
        state_store = HeartbeatSchedulerStateStore(tmp_path / "heartbeat-state.json")
        scheduler = HeartbeatScheduler(
            agents=(),
            kernel_client=kernel_client,
            state_store=state_store,
        )
        scheduler._agents_getter = lambda: pipeline._agents.values()  # noqa: SLF001

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

            # Read current config (triggers agent.config.get WS frame from IM)
            current = client.get(f"/im/v1/agents/{agent_id}/config")
            assert current.status_code == 200
            # Drain the agent.config.get WS frame and send reply
            live_frame = websocket.receive_json()
            assert live_frame["type"] == "agent.config.get"
            websocket.send_json(
                {
                    "type": "agent.config",
                    "payload": {
                        "request_id": live_frame["payload"]["request_id"],
                        "agent_id": agent_id,
                        "agent": None,
                    },
                }
            )
            websocket.receive_json()  # ack for agent.config

            current_version = current.json()["profile_version"]

            # PATCH: disable heartbeat (the action under test)
            patched = client.patch(
                f"/im/v1/agents/{agent_id}/config",
                json={
                    "profile_version": current_version,
                    "display_name": agent_id,
                    "description": "",
                    "system_prompt": f"You are {agent_id}.",
                    "skills": [],
                    "tool_allowlist": [],
                    "group_reply_policy": "manual",
                    "features": {"heartbeat": False},
                },
            )
            assert patched.status_code == 200, patched.text

            # Gateway side: receive the config.sync WS frame (critical assertion —
            # if the frame is not sent, this will time out / fail)
            sync_frame = websocket.receive_json()
            assert sync_frame["type"] == "config.sync", (
                f"Expected config.sync frame after PATCH, got: {sync_frame['type']!r}. "
                "Bug: push_config_sync was not delivered to the connected gateway."
            )
            assert sync_frame["payload"]["agent_id"] == agent_id

            # Simulate gateway handling: handle_notification → sync_agent → register_agent
            config_sync_client.handle_notification(sync_frame["payload"])

        # After sync_agent ran, pipeline._agents must reflect heartbeat=False
        updated_agent = pipeline._agents[agent_id]  # noqa: SLF001
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
