"""HTTP data routes authenticate and isolate tenant-owned resources."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository

from .conftest import authorize, make_app_client, register_user


def test_data_routes_require_bearer_token(tmp_path: Path) -> None:
    """Reject unauthenticated reads at every public data-route family."""
    paths = (
        "/im/v1/me",
        "/im/v1/conversations",
        "/im/v1/conversations/missing/messages",
        "/im/v1/agents",
        "/im/v1/nodes",
        "/im/v1/metrics/usage",
    )
    with make_app_client(tmp_path) as client:
        for path in paths:
            assert client.get(path).status_code == 401


def test_me_uses_token_subject_and_persists_updates(tmp_path: Path) -> None:
    """Read and update the bearer-token subject without a query identity shortcut."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)

        updated = client.patch(
            f"/im/v1/me?user_id=not-{alice.id}",
            json={
                "display_name": "Alice Cooper",
                "default_entry_node_id": None,
                "locale": "zh",
            },
        )
        current = client.get("/im/v1/me")

    assert updated.status_code == 200
    assert updated.json()["id"] == alice.id
    assert current.json()["display_name"] == "Alice Cooper"
    assert current.json()["locale"] == "zh"


def test_resources_are_hidden_across_tenants(tmp_path: Path) -> None:
    """Hide another tenant's conversations, messages, agents, and nodes."""
    with make_app_client(tmp_path) as alice_client:
        alice = register_user(alice_client, username="alice")
        authorize(alice_client, alice)
        with TestClient(alice_client.app) as bob_client:
            bob = register_user(bob_client, username="bob")
            authorize(bob_client, bob)

            conversation = alice_client.post(
                "/im/v1/conversations",
                json={"title": "Alice room", "participant_ids": [alice.id]},
            ).json()
            conversation_id = conversation["id"]

            nodes = NodeRepository(alice_client.app.state.connection)
            nodes.upsert_node(
                node_id="node-alice",
                node_name="Alice Node",
                owner_id=alice.owner_id,
            )
            profiles = AgentProfileRepository(alice_client.app.state.connection)
            profiles.upsert_profile(
                agent_id="alice-agent",
                owner_id=alice.owner_id,
                node_id="node-alice",
                display_name="Alice Agent",
                description="",
                skills=[],
                tool_allowlist=[],
                group_reply_policy="manual",
                default_model=None,
                workspace_root=None,
            )

            assert (
                bob_client.get(f"/im/v1/conversations/{conversation_id}").status_code
                == 404
            )
            assert (
                bob_client.patch(
                    f"/im/v1/conversations/{conversation_id}",
                    json={"is_pinned": True},
                ).status_code
                == 404
            )
            assert (
                bob_client.delete(f"/im/v1/conversations/{conversation_id}").status_code
                == 404
            )
            assert (
                bob_client.get(
                    f"/im/v1/conversations/{conversation_id}/messages"
                ).status_code
                == 404
            )
            assert (
                bob_client.post(
                    f"/im/v1/conversations/{conversation_id}/messages",
                    json={"sender_user_id": bob.id, "content": "intrude"},
                ).status_code
                == 404
            )
            assert bob_client.get("/im/v1/agents/alice-agent/config").status_code == 404
            assert (
                bob_client.get("/im/v1/nodes/node-alice/capabilities").status_code
                == 404
            )

            assert conversation_id not in {
                item["id"]
                for item in bob_client.get("/im/v1/conversations").json()["items"]
            }
            assert "alice-agent" not in {
                item["agent_id"] for item in bob_client.get("/im/v1/agents").json()
            }
            assert "node-alice" not in {
                item["node_id"] for item in bob_client.get("/im/v1/nodes").json()
            }
