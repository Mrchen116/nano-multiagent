"""Browser protections for the served application and its HTTP resources."""

from urllib.parse import urlsplit


class SecurityHeaders:
    """Apply one policy using the configured public origin, including behind tunnels."""

    def __init__(self, app, public_url: str):
        self.app = app
        origin = urlsplit(public_url)
        self.https = origin.scheme == "https"
        ws_origin = f"{'wss' if self.https else 'ws'}://{origin.netloc}"
        self.csp = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
            f"connect-src 'self' {ws_origin}; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def protected_send(message):
            if message["type"] == "http.response.start":
                policy_keys = {
                    b"x-frame-options",
                    b"x-content-type-options",
                    b"referrer-policy",
                }
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in policy_keys
                ]
                headers.extend(
                    [
                        (b"x-frame-options", b"DENY"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    ]
                )
                if self.https:
                    headers.append((b"strict-transport-security", b"max-age=86400"))
                content_type = dict(headers).get(b"content-type", b"")
                if content_type.startswith(b"text/html") and scope["path"] not in {
                    "/docs",
                    "/docs/oauth2-redirect",
                    "/redoc",
                }:
                    headers.append((b"content-security-policy", self.csp.encode()))
                if scope["path"].startswith("/im/v1/auth/"):
                    headers = [
                        (key, value)
                        for key, value in headers
                        if key.lower() != b"cache-control"
                    ]
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, protected_send)
