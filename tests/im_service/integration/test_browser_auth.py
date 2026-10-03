"""Browser Cookie transport remains isolated from programmatic authentication."""

from fastapi.testclient import TestClient

from IM.app import create_app


BROWSER = {"X-IM-Session": "browser", "Origin": "https://im.example.test"}
CREDENTIALS = {
    "username": "alice",
    "password": "browser-test-password",
    "display_name": "Alice",
}


def test_browser_cookie_rotation_and_program_api_boundary(tmp_path):
    app = create_app(db_path=tmp_path / "im.db", public_url="https://im.example.test")
    with TestClient(app, base_url="https://im.example.test") as client:
        response = client.post(
            "/im/v1/auth/register", headers=BROWSER, json=CREDENTIALS
        )
        assert response.status_code == 201
        assert "refresh_token" not in response.json()
        cookie = response.headers["set-cookie"]
        assert (
            "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
        )
        assert "Domain=" not in cookie
        assert response.headers["cache-control"] == "no-store"
        original = client.cookies.get("im_refresh")
        assert original
        native = client.post("/im/v1/auth/refresh", json={})
        assert native.status_code == 422
        assert "set-cookie" not in native.headers
        refreshed = client.post("/im/v1/auth/refresh", headers=BROWSER, json={})
        assert refreshed.status_code == 200
        assert "refresh_token" not in refreshed.json()
        assert client.cookies.get("im_refresh") != original
        replay = client.post("/im/v1/auth/refresh", json={"refresh_token": original})
        assert replay.status_code == 401
        assert "set-cookie" not in replay.headers
        logged_out = client.post("/im/v1/auth/logout", headers=BROWSER, json={})
        assert logged_out.status_code == 200
        assert not client.cookies.get("im_refresh")
        assert (
            client.post("/im/v1/auth/refresh", headers=BROWSER, json={}).status_code
            == 401
        )


def test_untrusted_browser_origin_cannot_mutate_session(tmp_path):
    app = create_app(db_path=tmp_path / "im.db", public_url="https://im.example.test")
    with TestClient(app, base_url="https://im.example.test") as client:
        registered = client.post(
            "/im/v1/auth/register", headers=BROWSER, json=CREDENTIALS
        )
        assert registered.status_code == 201
        original = client.cookies.get("im_refresh")
        for origin in (None, "https://evil.test", "https://im.example.test.evil.test"):
            headers = {"X-IM-Session": "browser"}
            if origin:
                headers["Origin"] = origin
            for endpoint in ("login", "register", "refresh", "logout"):
                response = client.post(
                    f"/im/v1/auth/{endpoint}", headers=headers, json=CREDENTIALS
                )
                assert response.status_code == 403
                assert "set-cookie" not in response.headers
        assert client.cookies.get("im_refresh") == original
        assert (
            client.post("/im/v1/auth/refresh", headers=BROWSER, json={}).status_code
            == 200
        )


def test_served_html_has_https_policy_without_blocking_api_docs(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        '<html><script src="/assets/app.js"></script></html>'
    )
    app = create_app(
        db_path=tmp_path / "im.db",
        public_url="https://im.example.test",
        frontend_dist_dir=dist,
    )
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        assert page.headers["strict-transport-security"] == "max-age=86400"
        assert page.headers["x-frame-options"] == "DENY"
        assert page.headers["x-content-type-options"] == "nosniff"
        assert "content-security-policy" not in client.get("/docs").headers
        assert client.get("/im/v1/auth/me").headers["cache-control"] == "no-store"
