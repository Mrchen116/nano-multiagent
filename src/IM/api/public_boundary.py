"""One company admission boundary for HTTP and bounded public request bodies."""

import asyncio
import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from IM.infra.auth_limits import RateLimited

JSON_LIMIT = 2 * 1024 * 1024


def client_source(scope: dict) -> str:
    """Trust Cloudflare's address only from the explicitly configured local tunnel."""
    peer = (scope.get("client") or ("unknown", 0))[0]
    trusted = os.getenv("IM_TRUSTED_PROXY", "")
    if trusted and peer == trusted:
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"cf-connecting-ip", b"").decode("ascii", "ignore")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


def browser_origin_allowed(scope: dict, public_url: str) -> bool:
    """Compare exact configured origins; no prefix or substring acceptance."""
    origin = dict(scope.get("headers", [])).get(b"origin", b"").decode()
    parsed = urlsplit(public_url)
    allowed = {f"{parsed.scheme}://{parsed.netloc}"}
    allowed.update(
        value.strip()
        for value in os.getenv("IM_BROWSER_ORIGINS", "").split(",")
        if value.strip()
    )
    return origin in allowed


class _ResponseRevoked(Exception):
    """Stop a response whose principal lost access after headers were sent."""


class CompanyBoundary:
    """Serialize admitted API effects with membership revocation in one IM worker.

    The shared SQLite connection and live socket registry belong to one process.
    Buffer bounded JSON before taking the lock, so a slow unauthenticated body
    cannot hold the membership transition lock.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/im/v1/"):
            return await self.app(scope, receive, send)
        transport_send = send

        async def bounded_send(message):
            async with asyncio.timeout(5):
                await transport_send(message)

        send = bounded_send
        path = scope["path"]
        method = scope["method"]
        streaming = method == "POST" and (
            path == "/im/v1/uploads"
            or (path.startswith("/im/v1/conversations/") and path.endswith("/images"))
        )
        if not streaming and method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = bytearray()
            try:
                async with asyncio.timeout(15):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > JSON_LIMIT:
                            return await JSONResponse(
                                {"detail": "request body too large"}, status_code=413
                            )(scope, receive, send)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await JSONResponse(
                    {"detail": "request body timed out"}, status_code=408
                )(scope, receive, send)
            consumed = False
            original_receive = receive

            async def buffered_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {
                        "type": "http.request",
                        "body": bytes(body),
                        "more_body": False,
                    }
                return await original_receive()

            receive = buffered_receive
        if streaming:
            # Slow bodies use per-owner upload slots; admission is rechecked under
            # the company gate only when the completed file is published.
            return await self.app(scope, receive, send)
        state = scope["app"].state
        await state.company_gate.acquire()
        gate_held = True
        protected_response = False

        async def response_send(message):
            nonlocal gate_held
            if message["type"] == "http.response.start" and gate_held:
                # Route effects are committed before headers. Slow socket writes
                # must not prevent another request from revoking membership.
                state.company_gate.release()
                gate_held = False
            if protected_response and message["type"] == "http.response.body":
                try:
                    async with state.company_gate:
                        await current_data_principal(Request(scope, receive=receive))
                except HTTPException:
                    await bounded_send(
                        {"type": "http.response.body", "body": b"", "more_body": False}
                    )
                    raise _ResponseRevoked
            await bounded_send(message)

        send = response_send
        try:
            request = Request(scope, receive=receive)
            try:
                source = client_source(scope)
                limits = state.auth_limits
                if path == "/im/v1/auth/register":
                    limits.check("register:source:" + source, limit=5, window=900)
                    limits.check("register:service", limit=100, window=3600)
                elif path == "/im/v1/auth/login":
                    limits.check("login:source:" + source, limit=30, window=300)
                elif path == "/im/v1/auth/refresh":
                    limits.check("refresh:source:" + source, limit=60, window=60)
                elif path.startswith("/im/v1/device-binding/"):
                    limits.check("bind:source:" + source, limit=60, window=60)
                public_identity = path in {
                    "/im/v1/auth/register",
                    "/im/v1/auth/login",
                    "/im/v1/auth/refresh",
                    "/im/v1/auth/logout",
                    "/im/v1/auth/me",
                }
                if not public_identity and not path.startswith(
                    "/im/v1/device-binding/"
                ):
                    from IM.api.deps import current_data_principal

                    await current_data_principal(request)
                    protected_response = True
                await self.app(scope, receive, send)
            except _ResponseRevoked:
                return
            except RateLimited as exc:
                await JSONResponse(
                    {
                        "detail": "temporarily rate limited",
                        "retry_after": exc.retry_after,
                    },
                    status_code=429,
                    headers={"Retry-After": str(exc.retry_after)},
                )(scope, receive, send)
            except HTTPException as exc:
                await JSONResponse(
                    {"detail": exc.detail},
                    status_code=exc.status_code,
                    headers=exc.headers,
                )(scope, receive, send)
        finally:
            if gate_held:
                state.company_gate.release()
