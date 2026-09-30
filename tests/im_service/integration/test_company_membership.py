"""Company admission and revocation through real HTTP/session boundaries."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def register(client, username):
    response = client.post(
        "/im/v1/auth/register",
        json={
            "username": username,
            "password": "membership-test-only",
            "display_name": username,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def headers(pair):
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_pending_approval_suspension_and_admin_boundary(tmp_path: Path):
    with TestClient(create_app(db_path=tmp_path / "company.db")) as client:
        admin = register(client, "admin")
        pending = register(client, "member")
        assert pending["user"]["membership_status"] == "pending"
        assert client.get("/im/v1/auth/me", headers=headers(pending)).status_code == 200
        assert (
            client.get("/im/v1/conversations", headers=headers(pending)).status_code
            == 403
        )
        connection = client.app.state.connection
        connection.execute(
            "UPDATE users SET membership_status='active', is_company_admin=1 WHERE id=?",
            (admin["user"]["id"],),
        )
        connection.commit()
        listing = client.get("/im/v1/company/members", headers=headers(admin)).json()
        assert all(
            isinstance(member["is_company_admin"], bool)
            for member in listing["members"]
        )
        member_id = pending["user"]["id"]
        assert (
            client.post(
                f"/im/v1/company/members/{member_id}/approve", headers=headers(pending)
            ).status_code
            == 403
        )
        approved = client.post(
            f"/im/v1/company/members/{member_id}/approve", headers=headers(admin)
        )
        assert approved.status_code == 200, approved.text
        assert (
            client.get("/im/v1/conversations", headers=headers(pending)).status_code
            == 200
        )
        policies = client.get("/im/v1/policies", headers=headers(pending)).json()
        assert (
            client.patch(
                "/im/v1/policies", headers=headers(pending), json=policies
            ).status_code
            == 403
        )
        assert (
            client.patch(
                "/im/v1/policies", headers=headers(admin), json=policies
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/im/v1/company/members/{admin['user']['id']}/suspend",
                headers=headers(admin),
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/im/v1/company/members/{member_id}/suspend", headers=headers(admin)
            ).status_code
            == 200
        )
        assert (
            client.get("/im/v1/conversations", headers=headers(pending)).status_code
            == 401
        )
        fresh = client.post(
            "/im/v1/auth/login",
            json={"username": "member", "password": "membership-test-only"},
        ).json()
        assert fresh["user"]["membership_status"] == "suspended"
        assert client.get("/im/v1/auth/me", headers=headers(fresh)).status_code == 200
        assert (
            client.get("/im/v1/conversations", headers=headers(fresh)).status_code
            == 403
        )
        assert (
            client.post(
                f"/im/v1/company/members/{member_id}/approve", headers=headers(admin)
            ).status_code
            == 409
        )


def test_refresh_and_logout_revocations_survive_new_app(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IM_JWT_SECRET", "stable-test-signing-secret-at-least-32-bytes")
    db = tmp_path / "company.db"
    with TestClient(create_app(db_path=db)) as client:
        first = register(client, "member")
        second = client.post(
            "/im/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
        ).json()
    with TestClient(create_app(db_path=db)) as client:
        assert (
            client.post(
                "/im/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
            ).status_code
            == 401
        )
        assert client.get("/im/v1/auth/me", headers=headers(second)).status_code == 200
        assert (
            client.post(
                "/im/v1/auth/logout", json={"refresh_token": second["refresh_token"]}
            ).status_code
            == 200
        )
    with TestClient(create_app(db_path=db)) as client:
        assert (
            client.post(
                "/im/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
            ).status_code
            == 401
        )
        assert client.get("/im/v1/auth/me", headers=headers(second)).status_code == 401


def test_registration_throttle_ignores_forged_source_and_recovers(tmp_path: Path):
    with TestClient(create_app(db_path=tmp_path / "company.db")) as client:
        for index in range(5):
            register(client, f"member{index}")
        response = client.post(
            "/im/v1/auth/register",
            json={
                "username": "overflow",
                "password": "membership-test-only",
                "display_name": "Overflow",
            },
            headers={
                "X-Forwarded-For": "203.0.113.9",
                "CF-Connecting-IP": "203.0.113.10",
            },
        )
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0
        connection = client.app.state.connection
        assert (
            connection.execute(
                "SELECT 1 FROM users WHERE username='overflow'"
            ).fetchone()
            is None
        )
        connection.execute("UPDATE auth_rate_limits SET expires_at=0")
        connection.commit()
        register(client, "recovered")


def test_browser_ticket_single_use_origin_and_suspension(tmp_path: Path):
    from starlette.websockets import WebSocketDisconnect
    import pytest

    with TestClient(
        create_app(db_path=tmp_path / "company.db", public_url="http://testserver")
    ) as client:
        admin = register(client, "admin")
        member = register(client, "member")
        connection = client.app.state.connection
        connection.execute(
            "UPDATE users SET membership_status='active',is_company_admin=1 WHERE id=?",
            (admin["user"]["id"],),
        )
        connection.commit()
        assert (
            client.post("/im/v1/auth/ws-ticket", headers=headers(member)).status_code
            == 403
        )
        client.post(
            f"/im/v1/company/members/{member['user']['id']}/approve",
            headers=headers(admin),
        )
        ticket = client.post("/im/v1/auth/ws-ticket", headers=headers(member)).json()[
            "ticket"
        ]
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/im/ws/user?ticket={ticket}",
                headers={"Origin": "http://evil.invalid"},
            ):
                pass
        with client.websocket_connect(
            f"/im/ws/user?ticket={ticket}", headers={"Origin": "http://testserver"}
        ) as ws:
            ws.send_json({"op": "resume", "after_event_id": 0})
            ws.send_json({"op": "ping"})
            assert ws.receive_json()["op"] == "pong"
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(
                    f"/im/ws/user?ticket={ticket}",
                    headers={"Origin": "http://testserver"},
                ):
                    pass
            result = client.post(
                f"/im/v1/company/members/{member['user']['id']}/suspend",
                headers=headers(admin),
            )
            assert result.status_code == 200
            assert ws.receive_json() == {
                "op": "membership_changed",
                "membership_status": "suspended",
            }
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_suspension_interrupts_stream_publication_without_waiting_for_upload(
    tmp_path: Path,
):
    """A slow upload holds its own reservation, never the member-revocation lock."""
    import asyncio
    import httpx

    async def journey():
        app = create_app(db_path=tmp_path / "stream.db", public_url="http://testserver")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                pairs = []
                for name in ("admin", "member"):
                    r = await client.post(
                        "/im/v1/auth/register",
                        json={
                            "username": name,
                            "password": "membership-test-only",
                            "display_name": name,
                        },
                    )
                    pairs.append(r.json())
                admin, member = pairs
                app.state.connection.execute(
                    "UPDATE users SET membership_status='active',is_company_admin=(username='admin')"
                )
                app.state.connection.commit()
                chat = await client.post(
                    "/im/v1/conversations",
                    headers=headers(member),
                    json={
                        "type": "group",
                        "title": "Upload",
                        "participant_ids": [member["user"]["id"]],
                    },
                )
                assert chat.status_code == 201, chat.text
                started, resume = asyncio.Event(), asyncio.Event()

                async def chunks():
                    yield b"first"
                    started.set()
                    await resume.wait()
                    yield b"second"

                upload = asyncio.create_task(
                    client.post(
                        "/im/v1/uploads",
                        params={
                            "conversation_id": chat.json()["id"],
                            "file_name": "note.txt",
                        },
                        headers={**headers(member), "Content-Type": "text/plain"},
                        content=chunks(),
                    )
                )
                await asyncio.wait_for(started.wait(), 2)
                suspended = await asyncio.wait_for(
                    client.post(
                        f"/im/v1/company/members/{member['user']['id']}/suspend",
                        headers=headers(admin),
                    ),
                    2,
                )
                assert suspended.status_code == 200
                resume.set()
                rejected = await upload
                assert rejected.status_code == 401, rejected.text
                assert (
                    app.state.connection.execute(
                        "SELECT count(*) FROM attachment_storage"
                    ).fetchone()[0]
                    == 0
                )
                assert (
                    app.state.connection.execute(
                        "SELECT count(*) FROM message_images"
                    ).fetchone()[0]
                    == 0
                )

    asyncio.run(journey())


def test_restore_revokes_old_credentials_and_preserves_private_attachment(
    tmp_path, monkeypatch
):
    """Exercise the offline recovery SQL against a real HTTP-created snapshot."""
    import shutil
    import sqlite3
    from starlette.websockets import WebSocketDisconnect
    import pytest
    from tests.im_service.device_binding_helpers import complete_binding
    from IM.infra.device_binding import DeviceBindingStore

    monkeypatch.setenv("IM_JWT_SECRET", "restore-test-stable-secret-at-least-32-bytes")
    original_root = tmp_path / "original"
    original_root.mkdir()
    db, uploads = original_root / "im.db", original_root / "uploads"
    with TestClient(create_app(db_path=db, upload_dir=uploads)) as client:
        pair = register(client, "restore-member")
        client.app.state.connection.execute(
            "UPDATE users SET membership_status='active' WHERE id=?",
            (pair["user"]["id"],),
        )
        client.app.state.connection.commit()
        client.headers.update(headers(pair))
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "type": "group",
                "title": "Preserved",
                "participant_ids": [pair["user"]["id"]],
            },
        ).json()
        upload = client.post(
            "/im/v1/uploads",
            params={"conversation_id": conversation["id"], "file_name": "history.txt"},
            content=b"history survives restore",
            headers={"Content-Type": "text/plain"},
        )
        assert upload.status_code == 201, upload.text
        attachment_url = upload.json()["url"]
        ticket = client.post("/im/v1/auth/ws-ticket").json()["ticket"]
        runtime = complete_binding(client, tmp_path, node_id="restore-node")[
            "runtime_token"
        ]
    restored_root = tmp_path / "restored"
    restored_root.mkdir()
    restored_db, restored_uploads = restored_root / "im.db", restored_root / "uploads"
    with sqlite3.connect(db) as source, sqlite3.connect(restored_db) as target:
        source.backup(target)
    shutil.copytree(uploads, restored_uploads)
    shutil.copytree(original_root / "message-images", restored_root / "message-images")
    with sqlite3.connect(restored_db) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        restored.executescript("""
            BEGIN IMMEDIATE;
            UPDATE users SET auth_epoch=auth_epoch+1 WHERE password_hash IS NOT NULL;
            UPDATE auth_sessions SET revoked=1;
            DELETE FROM auth_ws_tickets;
            UPDATE node_binding_state SET node_epoch=node_epoch+1,runtime_token_hash=NULL;
            DELETE FROM node_binding_operations;
            COMMIT;
        """)
    with TestClient(
        create_app(db_path=restored_db, upload_dir=restored_uploads)
    ) as client:
        assert client.get("/im/v1/auth/me", headers=headers(pair)).status_code == 401
        assert (
            client.post(
                "/im/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            ).status_code
            == 401
        )
        assert DeviceBindingStore(restored_db).authenticate_runtime(runtime) is None
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/im/ws/user?ticket={ticket}",
                headers={"Origin": client.app.state.public_url},
            ):
                pass
        fresh = client.post(
            "/im/v1/auth/login",
            json={"username": "restore-member", "password": "membership-test-only"},
        ).json()
        response = client.get(attachment_url, headers=headers(fresh))
        assert response.status_code == 200
        assert response.content == b"history survives restore"


def test_slow_attachment_download_does_not_block_member_suspension(tmp_path):
    """Socket backpressure must not retain the lock that revokes company access."""
    import asyncio
    import httpx

    async def journey():
        app = create_app(
            db_path=tmp_path / "download.db", public_url="http://testserver"
        )
        body_started, release_body = asyncio.Event(), asyncio.Event()

        async def backpressured_app(scope, receive, send):
            async def blocked_send(message):
                if (
                    scope["path"].endswith("/" + resource_id)
                    and message["type"] == "http.response.body"
                ):
                    body_started.set()
                    await release_body.wait()
                await send(message)

            await app(scope, receive, blocked_send)

        resource_id = "not-created"
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=backpressured_app),
                base_url="http://testserver",
            ) as client:
                pairs = []
                for name in ("admin", "member"):
                    response = await client.post(
                        "/im/v1/auth/register",
                        json={
                            "username": name,
                            "password": "download-test-only",
                            "display_name": name,
                        },
                    )
                    pairs.append(response.json())
                admin, member = pairs
                app.state.connection.execute(
                    "UPDATE users SET membership_status='active',is_company_admin=(username='admin')"
                )
                app.state.connection.commit()
                chat = await client.post(
                    "/im/v1/conversations",
                    headers=headers(member),
                    json={
                        "type": "group",
                        "title": "Download",
                        "participant_ids": [member["user"]["id"]],
                    },
                )
                upload = await client.post(
                    "/im/v1/uploads",
                    params={
                        "conversation_id": chat.json()["id"],
                        "file_name": "note.txt",
                    },
                    headers={**headers(member), "Content-Type": "text/plain"},
                    content=b"private attachment",
                )
                assert upload.status_code == 201, upload.text
                url = upload.json()["url"]
                resource_id = url.rsplit("/", 1)[-1]
                download = asyncio.create_task(client.get(url, headers=headers(member)))
                try:
                    await asyncio.wait_for(body_started.wait(), 2)
                    suspended = await asyncio.wait_for(
                        client.post(
                            f"/im/v1/company/members/{member['user']['id']}/suspend",
                            headers=headers(admin),
                        ),
                        2,
                    )
                    assert suspended.status_code == 200
                    assert (
                        await client.get(
                            "/im/v1/conversations", headers=headers(member)
                        )
                    ).status_code == 401
                finally:
                    release_body.set()
                    response = await download
                    assert response.content == b"private attachment"

    asyncio.run(journey())
