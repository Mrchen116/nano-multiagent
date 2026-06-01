"""Tests for IMAuthClient — IM token refresh and login HTTP operations."""

from __future__ import annotations

import json

import httpx
import pytest

from personal_assistant.auth.im_auth_client import IMAuthClient, IMAuthError


class _MockTransport(httpx.AsyncBaseTransport):
    """Replay pre-baked responses without real network I/O."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not self._responses:
            raise RuntimeError(f"unexpected request: {request.method} {request.url}")
        return self._responses.pop(0)


def _json_response(data: dict, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens_on_success() -> None:
    """refresh() returns (access_token, refresh_token) when IM returns 200."""
    transport = _MockTransport(
        [
            _json_response(
                {
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                }
            )
        ]
    )
    client = IMAuthClient(base_url="http://localhost:8011", transport=transport)

    access, refresh = await client.refresh("old-refresh")

    assert access == "new-access"
    assert refresh == "new-refresh"


@pytest.mark.asyncio
async def test_refresh_raises_on_401() -> None:
    """refresh() raises IMAuthError when IM returns 401 (token expired/revoked)."""
    transport = _MockTransport(
        [_json_response({"detail": "invalid refresh token"}, status_code=401)]
    )
    client = IMAuthClient(base_url="http://localhost:8011", transport=transport)

    with pytest.raises(IMAuthError):
        await client.refresh("expired-refresh")


@pytest.mark.asyncio
async def test_login_returns_tokens_on_success() -> None:
    """login() returns (access_token, refresh_token) on successful credential auth."""
    transport = _MockTransport(
        [
            _json_response(
                {
                    "access_token": "fresh-access",
                    "refresh_token": "fresh-refresh",
                }
            )
        ]
    )
    client = IMAuthClient(base_url="http://localhost:8011", transport=transport)

    access, refresh = await client.login(username="nano", password="nano1234")

    assert access == "fresh-access"
    assert refresh == "fresh-refresh"


@pytest.mark.asyncio
async def test_login_raises_on_bad_credentials() -> None:
    """login() raises IMAuthError when IM returns 401 (wrong password)."""
    transport = _MockTransport(
        [_json_response({"detail": "invalid credentials"}, status_code=401)]
    )
    client = IMAuthClient(base_url="http://localhost:8011", transport=transport)

    with pytest.raises(IMAuthError):
        await client.login(username="nano", password="wrong")


@pytest.mark.asyncio
async def test_refresh_sends_correct_body() -> None:
    """refresh() sends the refresh_token in the JSON body to POST /im/v1/auth/refresh."""
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"access_token": "a", "refresh_token": "r"})

    client = IMAuthClient(
        base_url="http://localhost:8011", transport=_CapturingTransport()
    )
    await client.refresh("my-refresh-token")

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert str(req.url).endswith("/im/v1/auth/refresh")
    body = json.loads(req.content)
    assert body.get("refresh_token") == "my-refresh-token"


@pytest.mark.asyncio
async def test_login_sends_correct_body() -> None:
    """login() sends username+password in the JSON body to POST /im/v1/auth/login."""
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"access_token": "a", "refresh_token": "r"})

    client = IMAuthClient(
        base_url="http://localhost:8011", transport=_CapturingTransport()
    )
    await client.login(username="nano", password="nano1234")

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert str(req.url).endswith("/im/v1/auth/login")
    body = json.loads(req.content)
    assert body.get("username") == "nano"
    assert body.get("password") == "nano1234"
