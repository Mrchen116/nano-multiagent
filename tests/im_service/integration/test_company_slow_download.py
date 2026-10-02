"""Keep member revocation available while an attachment consumer stalls."""

from fastapi.testclient import TestClient
from IM.app import create_app
from .test_company_membership import register, headers


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
                    content=b"x" * 200000,
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
                    assert response.content == b"x" * 65536

    asyncio.run(journey())
