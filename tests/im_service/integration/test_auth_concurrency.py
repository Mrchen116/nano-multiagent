"""Authentication CPU admission and account throttling through real HTTP routes."""

import asyncio
import threading
import time
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.api.routes import auth
from IM.infra import auth_limits


CREDENTIALS = {
    "username": "alice",
    "password": "concurrency-test-password",
    "display_name": "Alice",
}


def test_wrong_password_cooldown_does_not_follow_account_to_another_source(
    tmp_path, monkeypatch
):
    now = [int(time.time())]
    monkeypatch.setattr(auth_limits, "time", SimpleNamespace(time=lambda: now[0]))
    monkeypatch.setenv("IM_TRUSTED_PROXY", "testclient")
    with TestClient(create_app(db_path=tmp_path / "im.db")) as client:
        assert client.post("/im/v1/auth/register", json=CREDENTIALS).status_code == 201
        for _ in range(10):
            now[0] += 2
            assert (
                client.post(
                    "/im/v1/auth/login",
                    json={**CREDENTIALS, "password": "wrong"},
                    headers={"CF-Connecting-IP": "192.0.2.1"},
                ).status_code
                == 401
            )
        now[0] += 2
        blocked = client.post(
            "/im/v1/auth/login",
            json=CREDENTIALS,
            headers={"CF-Connecting-IP": "192.0.2.1"},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 800
        assert (
            client.post(
                "/im/v1/auth/login",
                json=CREDENTIALS,
                headers={"CF-Connecting-IP": "192.0.2.2"},
            ).status_code
            == 200
        )
        target_busy = client.post(
            "/im/v1/auth/login",
            json=CREDENTIALS,
            headers={"CF-Connecting-IP": "192.0.2.3"},
        )
        assert target_busy.status_code == 429
        assert target_busy.headers["Retry-After"] == "1"
        now[0] += 1
        assert (
            client.post(
                "/im/v1/auth/login",
                json=CREDENTIALS,
                headers={"CF-Connecting-IP": "192.0.2.3"},
            ).status_code
            == 200
        )


def test_password_work_does_not_block_reads_or_release_cancelled_capacity(
    tmp_path, monkeypatch
):
    async def journey():
        app = create_app(db_path=tmp_path / "im.db")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                pair = (
                    await client.post("/im/v1/auth/register", json=CREDENTIALS)
                ).json()
                started, release = threading.Event(), threading.Event()
                calls = [0]
                original = auth.verify_password

                def slow_verify(*args):
                    calls[0] += 1
                    if calls[0] == 2:
                        started.set()
                    release.wait(5)
                    return original(*args)

                monkeypatch.setattr(auth, "verify_password", slow_verify)
                tasks = [
                    asyncio.create_task(
                        client.post(
                            "/im/v1/auth/login",
                            json={"username": name, "password": "wrong"},
                        )
                    )
                    for name in ("alice", "unknown")
                ]
                try:
                    assert await asyncio.to_thread(started.wait, 2)
                    response = await asyncio.wait_for(
                        client.get(
                            "/im/v1/auth/me",
                            headers={"Authorization": "Bearer " + pair["access_token"]},
                        ),
                        1,
                    )
                    assert response.status_code == 200
                    tasks[0].cancel()
                    try:
                        await tasks[0]
                    except asyncio.CancelledError:
                        pass
                    overloaded = await client.post(
                        "/im/v1/auth/login",
                        json={"username": "third", "password": "wrong"},
                    )
                    assert overloaded.status_code == 429
                    assert overloaded.headers["Retry-After"] == "1"
                finally:
                    release.set()
                    await asyncio.gather(*tasks, return_exceptions=True)
                assert not app.state.company_gate.locked()
                assert not app.state.connection.in_transaction

    asyncio.run(journey())
