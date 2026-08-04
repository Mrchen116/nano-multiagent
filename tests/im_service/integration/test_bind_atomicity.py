"""Concurrent device binding remains atomic through the public HTTP API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository

from .conftest import authorize, make_app_client, register_user


def _protected_rows(connection) -> dict[str, list[tuple[object, ...]]]:  # noqa: ANN001
    tables = (
        "agent_channels",
        "channel_manifest_heads",
        "node_credential_keys",
        "agent_channel_removals",
    )
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
        for table in tables
    }


def test_cross_owner_concurrent_bind_has_one_atomic_winner(tmp_path: Path) -> None:
    """Commit exactly one owner without altering channel-control state."""
    with make_app_client(tmp_path) as alice_client:
        alice = register_user(alice_client, username="alice")
        authorize(alice_client, alice)
        with TestClient(alice_client.app) as bob_client:
            bob = register_user(bob_client, username="bob")
            authorize(bob_client, bob)
            connection = alice_client.app.state.connection
            NodeRepository(connection).upsert_node(
                node_id="node-race", node_name="Race"
            )
            AgentProfileRepository(connection).upsert_profile(
                agent_id="agent-race",
                owner_id="",
                node_id="node-race",
                display_name="Race Agent",
                description="",
                system_prompt="Race safely.",
                skills=[],
                tool_allowlist=[],
                group_reply_policy="manual",
                default_model=None,
                workspace_root=None,
            )
            connection.executescript(
                """
                INSERT INTO node_credential_keys VALUES
                  ('node-race', '', 'key-before', 'alg-before', 'public-before', 'time-before');
                INSERT INTO channel_manifest_heads VALUES
                  ('node-race', '', 4, 3, NULL, NULL, 'init-before', 'time-before');
                INSERT INTO agent_channels VALUES
                  ('channel-before', '', 'agent-race', 'node-race', 'feishu', 1,
                   '{"app_id":"cli_before"}', 'fingerprint', 1, '{}',
                   '{"ciphertext":"opaque"}', 'key-before', 1, 4,
                   'time-before', 'time-before');
                INSERT INTO agent_channel_removals VALUES
                  ('removed-before', 'token-before', '', 'agent-race', 'node-race',
                   'feishu', '{"app_id":"cli_old"}', 2, 4, 'pending', NULL, NULL,
                   NULL, 'expires-after', 'time-before', 'time-before');
                """
            )
            connection.commit()
            protected_before = _protected_rows(connection)

            alice_start = alice_client.post(
                "/im/v1/bind", json={"action": "start", "node_id": "node-race"}
            ).json()
            bob_start = bob_client.post(
                "/im/v1/bind", json={"action": "start", "node_id": "node-race"}
            ).json()

            def confirm(client: TestClient, bind_id: str):
                return client.post(
                    "/im/v1/bind",
                    json={"action": "confirm", "bind_id": bind_id},
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                alice_result = pool.submit(
                    confirm, alice_client, alice_start["bind_id"]
                )
                bob_result = pool.submit(confirm, bob_client, bob_start["bind_id"])
                responses = [alice_result.result(), bob_result.result()]

            winners = [
                response for response in responses if response.status_code == 201
            ]
            losers = [response for response in responses if response.status_code == 409]
            assert len(winners) == len(losers) == 1
            winner_user = alice if winners[0].json()["user_id"] == alice.id else bob
            loser_user = bob if winner_user is alice else alice

            node = NodeRepository(connection).get_node(node_id="node-race")
            profile = AgentProfileRepository(connection).get_profile(
                agent_id="agent-race"
            )
            assert node is not None and node.owner_id == winner_user.owner_id
            assert profile is not None and profile.owner_id == winner_user.owner_id
            assert _protected_rows(connection) == protected_before

            loser_client = bob_client if loser_user is bob else alice_client
            assert (
                loser_client.get("/im/v1/agents/agent-race/config").status_code == 404
            )
