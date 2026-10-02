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
            "type": "group",
            "title": "Images",
            "participant_ids": [user.id],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_regular_uploads_follow_membership_and_cannot_grant_access_by_url(
    tmp_path: Path,
):
    """Ordinary files share the conversation boundary, including later messages."""
    with make_app_client(tmp_path) as client:
        alice = register_and_authorize(client)
        bob = register_user(client, username="member-bob")
        outsider = register_user(client, username="outsider")
        created = client.post(
            "/im/v1/conversations",
            json={
                "type": "group",
                "title": "Shared",
                "participant_ids": [alice.id, bob.id],
            },
        )
        assert created.status_code == 201, created.text
        cid = created.json()["id"]
        upload = client.post(
            "/im/v1/uploads",
            params={"conversation_id": cid, "file_name": "notes.txt"},
            content=b"private team notes",
            headers={"Content-Type": "text/plain"},
        )
        assert upload.status_code == 201, upload.text
        attachment = upload.json()
        assert attachment["url"].startswith(f"/im/v1/conversations/{cid}/attachments/")
        authorize(client, bob)
        assert client.get(attachment["url"]).content == b"private team notes"
        authorize(client, outsider)
        assert client.get(attachment["url"]).status_code == 404
        own = _conversation(client, outsider)
        copied = client.post(
            f"/im/v1/conversations/{own}/messages",
            json={
                "sender": {"type": "user", "id": outsider.id},
                "content": "copied",
                "attachments": [attachment],
            },
        )
        assert copied.status_code == 404
        assert client.get("/im/uploads/anything.txt").status_code == 404


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
        assert client.app.state.message_image_repository.capacity()["service"][
            "used_bytes"
        ] == len(PNG)
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
                "type": "direct",
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


def test_image_target_preflight_resolves_user_and_checks_sender_membership(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    with make_app_client(tmp_path) as client:
        user = register_and_authorize(client)
        seed_user_under_owner(client, username="agent:writer", owner_id=user.owner_id)
        AgentProfileRepository(client.app.state.connection).upsert_profile(
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
        private_group = _conversation(client, user)
        monkeypatch.setattr(
            client.app.state.gateway_sessions,
            "authenticate_access_token",
            AsyncMock(
                return_value=SimpleNamespace(
                    node_id="node-test", owner_id=user.owner_id
                )
            ),
        )
        response = client.post(
            "/im/v1/image-delivery/target",
            json={"agent_id": "writer", "target": user.id},
        )
        assert response.status_code == 200, response.text
        conversation_id = response.json()["conversation_id"]
        retry = client.post(
            "/im/v1/image-delivery/target",
            json={"agent_id": "writer", "target": user.id},
        )
        assert retry.json() == response.json()
        assert (
            MessageRepository(client.app.state.connection).list_all_messages(
                conversation_id=conversation_id
            )
            == []
        )
        denied = client.post(
            "/im/v1/image-delivery/target",
            json={"agent_id": "writer", "target": private_group},
        )
        assert denied.status_code == 404
        wrong_agent = client.post(
            "/im/v1/image-delivery/target",
            json={"agent_id": "unowned", "target": user.id},
        )
        assert wrong_agent.status_code == 404
        monkeypatch.setattr(
            client.app.state.gateway_sessions,
            "authenticate_access_token",
            AsyncMock(return_value=None),
        )
        assert (
            client.post(
                "/im/v1/image-delivery/target",
                json={"agent_id": "writer", "target": user.id},
            ).status_code
            == 401
        )


def test_attachment_capacity_is_atomic_and_admin_only(tmp_path, monkeypatch):
    """Quota rejection retains accepted files and never exposes owner usage to members."""
    from IM.infra import attachment_quota

    monkeypatch.setattr(attachment_quota, "OWNER_LIMIT_BYTES", 8)
    monkeypatch.setattr(attachment_quota, "SERVICE_LIMIT_BYTES", 12)
    with make_app_client(tmp_path) as client:
        user = register_user(client, username="member", admin=False)
        authorize(client, user)
        cid = _conversation(client, user)
        params = {"conversation_id": cid, "file_name": "notes.txt"}
        first = client.post(
            "/im/v1/uploads",
            params=params,
            content=b"12345678",
            headers={"Content-Type": "text/plain"},
        )
        assert first.status_code == 201
        rejected = client.post(
            "/im/v1/uploads",
            params=params,
            content=b"x",
            headers={"Content-Type": "text/plain"},
        )
        assert rejected.status_code == 507
        assert rejected.json() == {"detail": "attachment upload unavailable"}
        assert client.get(first.json()["url"]).content == b"12345678"
        assert client.get("/im/v1/attachments/capacity").status_code == 403
        with client.app.state.connection:
            client.app.state.connection.execute(
                "UPDATE users SET is_company_admin = 1 WHERE id = ?", (user.id,)
            )
        capacity = client.get("/im/v1/attachments/capacity")
        assert capacity.status_code == 200
        assert capacity.json()["owners"] == [
            {
                "owner_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "used_bytes": 8,
                "reserved_bytes": 0,
                "limit_bytes": 8,
                "full": True,
            }
        ]
        second = register_user(client, username="second", admin=False)
        authorize(client, second)
        second_cid = _conversation(client, second)
        rejected = client.post(
            "/im/v1/uploads",
            params={"conversation_id": second_cid, "file_name": "second.txt"},
            content=b"12345",
            headers={"Content-Type": "text/plain"},
        )
        assert (
            rejected.status_code == 507
        )  # service total, although this owner has room
        authorize(client, user)
        repository = client.app.state.message_image_repository
        assert not list(repository.directory.glob(".*.tmp"))
        assert client.delete(f"/im/v1/conversations/{cid}").status_code == 204
        assert repository.capacity()["service"]["used_bytes"] == 0


def test_streamed_upload_concurrency_failure_and_restart_reclaim(tmp_path, monkeypatch):
    """Blocked streams consume owner slots; interruption and restart reclaim reservations."""
    import asyncio
    from IM.infra import attachment_quota
    from IM.infra.repositories.message_images import (
        AttachmentBusyError,
        AttachmentCapacityError,
    )

    monkeypatch.setattr(attachment_quota, "OWNER_LIMIT_BYTES", 8)
    monkeypatch.setattr(attachment_quota, "SERVICE_LIMIT_BYTES", 8)
    with make_app_client(tmp_path) as client:
        user = register_and_authorize(client)
        cid = _conversation(client, user)
        repository = client.app.state.message_image_repository

        async def exercise():
            proceed = asyncio.Event()
            both_started = asyncio.Event()
            started = 0

            async def chunks():
                nonlocal started
                yield b"1234"
                started += 1
                if started == 2:
                    both_started.set()
                await proceed.wait()
                yield b"x"

            async def upload(key):
                return await repository.put_stream(
                    conversation_id=cid,
                    source_key=key,
                    chunks=chunks(),
                    owner_id=user.id,
                    content_type="text/plain",
                    file_name="x.txt",
                    max_bytes=10,
                )

            first = asyncio.create_task(upload("first"))
            second = asyncio.create_task(upload("second"))
            await both_started.wait()
            assert repository.capacity()["service"]["reserved_bytes"] == 8
            with pytest.raises(AttachmentBusyError):
                await upload("third")
            proceed.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
            assert any(
                isinstance(result, AttachmentCapacityError) for result in results
            )
            assert repository.capacity()["service"]["reserved_bytes"] == 0
            assert not list(repository.directory.glob(".*.tmp"))

        asyncio.run(exercise())
        with client.app.state.connection:
            client.app.state.connection.execute(
                "INSERT INTO attachment_storage VALUES ('interrupted', ?, 3, 'reserved')",
                (user.id,),
            )
        (repository.directory / ".interrupted.tmp").write_bytes(b"abc")
        repository.reconcile_storage()
        assert repository.capacity()["service"]["reserved_bytes"] == 0
        assert not list(repository.directory.glob(".*.tmp"))
