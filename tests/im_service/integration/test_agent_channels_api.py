"""HTTP integration coverage for agent external-channel control."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.channel_credentials import generate_channel_key_pair
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository

from .conftest import authorize, register_user


def _seed_agent(client: TestClient, *, owner_id: str) -> None:
    NodeRepository(client.app.state.connection).upsert_node(
        node_id="node-a",
        node_name="Node A",
        owner_id=owner_id,
        status="online",
    )
    AgentProfileRepository(client.app.state.connection).upsert_profile(
        agent_id="agent-a",
        owner_id=owner_id,
        node_id="node-a",
        display_name="Agent A",
        description="",
        system_prompt="You are Agent A.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    pair = generate_channel_key_pair(private_seed=b"e" * 32)
    client.app.state.channel_control_store.register_node_public_key(
        owner_id=owner_id,
        node_id="node-a",
        key_id=pair.key_id,
        algorithm="X25519-HKDF-SHA256-AES-256-GCM",
        public_key=pair.public_key,
    )


def test_create_list_and_patch_feishu_channel_without_secret_leak(
    tmp_path: Path, caplog
) -> None:
    """The real HTTP entry enforces uniqueness and explicit keep/replace semantics."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _seed_agent(client, owner_id=owner.owner_id)

        created = client.post(
            "/im/v1/agents/agent-a/channels",
            json={
                "provider": "feishu",
                "enabled": True,
                "config": {"app_id": "cli_original"},
                "credentials": {"mode": "replace", "app_secret": "http-secret"},
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["provider"] == "feishu"
        assert body["config"] == {"app_id": "cli_original"}
        assert body["secret_configured"] is True
        assert body["sync_state"] == "pending"
        assert body["observed"] is None
        assert "credential" not in body
        assert "http-secret" not in created.text
        channel_id = body["channel_id"]

        duplicate = client.post(
            "/im/v1/agents/agent-a/channels",
            json={
                "provider": "feishu",
                "config": {"app_id": "cli_second"},
                "credentials": {"mode": "replace", "app_secret": "other"},
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "channel_provider_already_exists"

        listed = client.get("/im/v1/agents/agent-a/channels")
        assert listed.status_code == 200
        assert listed.json() == [body]

        kept = client.patch(
            f"/im/v1/agents/agent-a/channels/{channel_id}",
            json={
                "channel_revision": 1,
                "enabled": False,
                "config": {"app_id": "cli_original"},
                "credentials": {"mode": "keep"},
            },
        )
        assert kept.status_code == 200
        assert kept.json()["channel_revision"] == 2

        invalid_keep = client.patch(
            f"/im/v1/agents/agent-a/channels/{channel_id}",
            json={
                "channel_revision": 2,
                "enabled": True,
                "config": {"app_id": "cli_replacement"},
                "credentials": {"mode": "keep"},
            },
        )
        assert invalid_keep.status_code == 422
        assert invalid_keep.json()["detail"]["code"] == "channel_credentials_required"

        replaced = client.patch(
            f"/im/v1/agents/agent-a/channels/{channel_id}",
            json={
                "channel_revision": 2,
                "enabled": True,
                "config": {"app_id": "cli_replacement"},
                "credentials": {
                    "mode": "replace",
                    "app_secret": "replacement-secret",
                },
            },
        )
        assert replaced.status_code == 200
        assert replaced.json()["channel_revision"] == 3
        assert "replacement-secret" not in replaced.text
        assert "http-secret" not in caplog.text
        assert "replacement-secret" not in caplog.text


def test_channels_api_hides_another_owners_agent(tmp_path: Path) -> None:
    """Agent channel lists use authenticated owner scope at the HTTP boundary."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as owner_client:
        owner = register_user(owner_client, username="owner")
        authorize(owner_client, owner)
        _seed_agent(owner_client, owner_id=owner.owner_id)
        intruder = register_user(owner_client, username="intruder")
        authorize(owner_client, intruder)

        response = owner_client.get("/im/v1/agents/agent-a/channels")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "channel_not_found"


def test_offline_disable_delete_reload_and_actions_keep_truthful_state(
    tmp_path: Path,
) -> None:
    """Offline desired mutations persist while live-only actions fail explicitly."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _seed_agent(client, owner_id=owner.owner_id)
        created = client.post(
            "/im/v1/agents/agent-a/channels",
            json={
                "provider": "feishu",
                "config": {"app_id": "cli_offline"},
                "credentials": {"mode": "replace", "app_secret": "offline-secret"},
            },
        ).json()
        channel_id = created["channel_id"]

        disabled = client.patch(
            f"/im/v1/agents/agent-a/channels/{channel_id}",
            json={
                "channel_revision": 1,
                "enabled": False,
                "config": {"app_id": "cli_offline"},
                "credentials": {"mode": "keep"},
            },
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
        assert disabled.json()["sync_state"] == "pending"

        reconnect = client.post(
            f"/im/v1/agents/agent-a/channels/{channel_id}/actions/reconnect"
        )
        assert reconnect.status_code == 409
        assert reconnect.json()["detail"]["code"] == "channel_node_offline"

        deleted = client.delete(
            f"/im/v1/agents/agent-a/channels/{channel_id}?channel_revision=2"
        )
        assert deleted.status_code == 200
        removal = deleted.json()
        assert removal["resource_type"] == "removal"
        assert removal["apply_state"] == "pending"
        assert removal["display_config"] == {"app_id_suffix": "fline"}
        assert "secret" not in deleted.text.lower()
        assert client.get("/im/v1/agents/agent-a/channels").json() == [removal]

        duplicate = client.post(
            "/im/v1/agents/agent-a/channels",
            json={
                "provider": "feishu",
                "config": {"app_id": "cli_duplicate"},
                "credentials": {"mode": "replace", "app_secret": "duplicate"},
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "channel_deletion_pending"

        retry = client.post(
            f"/im/v1/agents/agent-a/channel-removals/{channel_id}/actions/retry"
        )
        assert retry.status_code == 409
        assert retry.json()["detail"]["code"] == "channel_node_offline"
