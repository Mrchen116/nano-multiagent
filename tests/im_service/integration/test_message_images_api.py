"""Private reply images remain owner-scoped, immutable and available after fork."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.messages import MessageRepository
from .conftest import (
    authorize,
    make_app_client,
    register_and_authorize,
    register_user,
    seed_user_under_owner,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"snapshot"


def _conversation(client, user):
    response = client.post(
        "/im/v1/conversations",
        json={
            "title": "Images",
            "participant_ids": [user.id],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client, conversation_id, *, data=PNG, key="output:0", mime="image/png"):
    return client.post(
        f"/im/v1/conversations/{conversation_id}/images",
        params={"file_name": "../../snapshot.png"},
        content=data,
        headers={"Content-Type": mime, "Idempotency-Key": key},
    )


def test_images_are_private_immutable_and_persist_after_restart(tmp_path: Path):
    with make_app_client(tmp_path) as client:
        alice = register_and_authorize(client)
        conversation_id = _conversation(client, alice)
        created = _upload(client, conversation_id)
        assert created.status_code == 201, created.text
        image = created.json()
        assert image["file_name"] == "snapshot.png"
        assert image["content_type"] == "image/png"
        assert image["url"].startswith(
            f"/im/v1/conversations/{conversation_id}/images/"
        )
        read = client.get(image["url"])
        assert read.content == PNG
        assert read.headers["cache-control"] == "private, no-store"
        assert read.headers["x-content-type-options"] == "nosniff"
        again = _upload(client, conversation_id)
        assert again.status_code == 200
        assert again.json() == image
        assert (
            _upload(client, conversation_id, data=PNG + b"changed").status_code == 409
        )
        bob = register_user(client, username="bob")
        authorize(client, bob)
        assert client.get(image["url"]).status_code == 404
        assert _upload(client, conversation_id).status_code == 404
        client.headers.pop("Authorization")
        assert client.get(image["url"]).status_code == 401
        assert _upload(client, conversation_id).status_code == 401
        # No resource is exposed by the legacy public static mount.
        assert list((tmp_path / "uploads").iterdir()) == []

    with make_app_client(tmp_path) as client:
        login = client.post(
            "/im/v1/auth/login",
            json={
                "username": alice.username,
                "password": "hunter2-strong",
            },
        )
        assert login.status_code == 200
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        assert client.get(image["url"]).content == PNG


@pytest.mark.parametrize(
    "data,mime,expected",
    [
        (b"<svg></svg>", "image/svg+xml", 415),
        (b"not an image", "image/png", 415),
        (PNG, "image/jpeg", 415),
        (PNG + bytes(10 * 1024 * 1024), "image/png", 413),
        (b"GIF89a" + b"raster", "image/gif", 201),
        (b"\xff\xd8\xff" + b"raster", "image/jpeg", 201),
        (b"RIFF1234WEBPraster", "image/webp", 201),
    ],
    ids=["svg", "invalid", "mismatch", "oversized", "gif", "jpeg", "webp"],
)
def test_image_upload_type_and_size_boundary(tmp_path: Path, data, mime, expected):
    with make_app_client(tmp_path) as client:
        user = register_and_authorize(client)
        conversation_id = _conversation(client, user)
        response = _upload(client, conversation_id, data=data, mime=mime)
        assert response.status_code == expected, response.text


def test_failed_snapshot_write_does_not_publish_resource(tmp_path: Path, monkeypatch):
    with make_app_client(tmp_path) as client:
        user = register_and_authorize(client)
        conversation_id = _conversation(client, user)
        original = Path.replace

        def fail_replace(self, target):
            raise OSError("disk unavailable")

        monkeypatch.setattr(Path, "replace", fail_replace)
        with pytest.raises(OSError):
            _upload(client, conversation_id)
        monkeypatch.setattr(Path, "replace", original)
        # The same key must still be creatable, with no incomplete row exposed.
        response = _upload(client, conversation_id)
        assert response.status_code == 201
        assert client.get(response.json()["url"]).content == PNG


def test_fork_rebinds_image_urls_and_source_deletion_keeps_snapshot(
    tmp_path: Path, monkeypatch
):
    with make_app_client(tmp_path) as client:
        user = register_and_authorize(client)
        agent_user_id = seed_user_under_owner(
            client, username="agent:writer", owner_id=user.owner_id
        )
        profiles = AgentProfileRepository(client.app.state.connection)
        profiles.upsert_profile(
            agent_id="writer",
            owner_id=user.owner_id,
            display_name="Writer",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model="test",
            node_id="node-test",
            workspace_root=None,
        )
        response = client.post(
            "/im/v1/conversations",
            json={
                "title": "Writer",
                "participant_ids": [f"user:{user.id}", "agent:writer"],
            },
        )
        assert response.status_code == 201, response.text
        source_id = response.json()["id"]
        uploaded = _upload(client, source_id)
        assert uploaded.status_code == 201, uploaded.text
        source_url = uploaded.json()["url"]
        messages = MessageRepository(client.app.state.connection)
        message = messages.create_message(
            conversation_id=source_id,
            sender_user_id=agent_user_id,
            sender_type="agent",
            content=f"Before ![one]({source_url}) after ![again]({source_url})",
            kernel_message_id="kernel-one",
        )
        monkeypatch.setattr(
            client.app.state.gateway_sessions,
            "is_connected",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            client.app.state.gateway_control,
            "request_fork_session",
            AsyncMock(
                return_value={
                    "ok": True,
                    "new_session_id": "branch",
                    "id_map": {"kernel-one": "branch-one"},
                }
            ),
        )
        fork = client.post(
            f"/im/v1/conversations/{source_id}/fork",
            json={"fork_message_id": message.id},
        )
        assert fork.status_code == 201, fork.text
        target_id = fork.json()["id"]
        copied = messages.list_all_messages(conversation_id=target_id)[0]
        target_url = copied.content.split("](")[1].split(")")[0]
        assert target_url.startswith(f"/im/v1/conversations/{target_id}/images/")
        assert source_url not in copied.content
        assert copied.content.count(target_url) == 2
        assert client.delete(f"/im/v1/conversations/{source_id}").status_code == 204
        assert client.get(source_url).status_code == 404
        assert client.get(target_url).content == PNG
