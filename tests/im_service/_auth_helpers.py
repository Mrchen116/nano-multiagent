"""Shared auth helpers for IM integration + contract tests (feat-340-M1).

After R4, all IM HTTP routes require a Bearer token. Tests use these helpers to
register a tenant, install the access token onto a TestClient, and seed extra
participant users under the same tenant when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


@dataclass(frozen=True)
class AuthedUser:
    """Registered user + token bundle."""

    id: str
    username: str
    display_name: str
    owner_id: str
    access_token: str
    refresh_token: str


def make_app_client(tmp_path: Path, *, db_name: str = "im.db") -> TestClient:
    """Build one fresh FastAPI app + TestClient against a temp sqlite file."""
    app = create_app(db_path=tmp_path / db_name)
    return TestClient(app)


def register_user(
    client: TestClient,
    *,
    username: str,
    display_name: str | None = None,
    password: str = "hunter2-strong",
    locale: str = "en",
    active: bool = True,
    admin: bool = True,
) -> AuthedUser:
    """Register a user via /im/v1/auth/register and return tokens + user payload."""
    response = client.post(
        "/im/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "display_name": display_name or username.title(),
            "locale": locale,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    user = body["user"]
    # Legacy business fixtures represent admitted members. Admission tests call
    # raw public registration (or active=False), never a product bypass.
    if active:
        connection = client.app.state.connection
        connection.execute(
            "UPDATE users SET membership_status='active',is_company_admin=? WHERE id=?",
            (int(admin), user["id"]),
        )
        connection.commit()
    return AuthedUser(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        owner_id=user["owner_id"],
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
    )


def authorize(client: TestClient, user: AuthedUser) -> None:
    """Install the user's bearer token onto the TestClient default headers."""
    client.headers.update({"Authorization": f"Bearer {user.access_token}"})


def seed_user_under_owner(
    client: TestClient,
    *,
    username: str,
    display_name: str | None = None,
    owner_id: str,
) -> str:
    """Create a passwordless participant user manually placed under ``owner_id`` and return id."""
    from IM.infra.repositories.users import UserRepository

    connection = client.app.state.connection
    repo = UserRepository(connection)
    # feat-340-M18 R9-1: agent profile reads now lazily provision ``agent:<id>`` rows,
    # so a fixture that seeds the same username after a /im/v1/agents call would race
    # against the lazy bootstrap. Treat that case as idempotent and return the
    # existing row instead of failing the whole test on a UNIQUE constraint.
    existing = repo.get_user_by_username(username=username)
    if existing is not None:
        created = existing
    else:
        created = repo.create_user(
            username=username, display_name=display_name or username.title()
        )
    if created.owner_id != owner_id:
        connection.execute(
            "UPDATE users SET owner_id = ? WHERE id = ?", (owner_id, created.id)
        )
        connection.commit()
    return created.id


def register_and_authorize(
    client: TestClient,
    *,
    username: str = "owner",
    display_name: str | None = None,
) -> AuthedUser:
    """Register and authorize the client in one call."""
    user = register_user(client, username=username, display_name=display_name)
    authorize(client, user)
    return user


def seed_runtime_credential(connection, *, node_id: str, owner_id: str) -> str:
    """Provision a previously enrolled test node; proof itself has dedicated integration coverage."""
    import hashlib
    import secrets
    from IM.infra.repositories.nodes import NodeRepository

    nodes = NodeRepository(connection)
    if nodes.get_node(node_id=node_id) is None:
        nodes.upsert_node(node_id=node_id, node_name=node_id, owner_id=owner_id)
    connection.execute(
        "UPDATE nodes SET owner_id=? WHERE node_id=? AND (owner_id IS NULL OR owner_id='')",
        (owner_id, node_id),
    )
    token = secrets.token_urlsafe(32)
    connection.execute(
        "UPDATE users SET membership_status='active' WHERE owner_id=?", (owner_id,)
    )
    connection.execute(
        "INSERT INTO node_binding_state(node_id,owner_id,node_epoch,runtime_token_hash) VALUES(?,?,1,?) ON CONFLICT(node_id) DO UPDATE SET runtime_token_hash=excluded.runtime_token_hash",
        (node_id, owner_id, hashlib.sha256(token.encode()).hexdigest()),
    )
    connection.commit()
    return token


class GatewaySocketFixture:
    """Defer the real authenticated handshake until the fixture's first node frame."""

    def __init__(self, client: TestClient, *, headers=None):
        self.client = client
        self.headers = headers or client.headers
        self.socket = None
        self.context = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.socket is not None:
            return self.context.__exit__(*args)

    def send_json(self, frame):
        if self.socket is None:
            authorization = self.headers.get(
                "Authorization", self.headers.get("authorization", "")
            )
            owner_id = self.client.app.state.auth_service.verify_access_token(
                authorization.removeprefix("Bearer ")
            )
            node_id = frame.get("payload", {}).get("node_id", "fixture-node")
            token = seed_runtime_credential(
                self.client.app.state.connection, node_id=node_id, owner_id=owner_id
            )
            payload = frame.get("payload", {})
            if payload.get("credential_public_key"):
                c = self.client.app.state.connection
                c.execute(
                    "INSERT OR IGNORE INTO node_credential_keys VALUES (?,?,?,?,?,datetime('now'))",
                    (
                        node_id,
                        owner_id,
                        payload["credential_key_id"],
                        payload["credential_algorithm"],
                        payload["credential_public_key"],
                    ),
                )
                c.commit()
            self.context = self.client.websocket_connect(
                "/im/ws/gateway", headers={"Authorization": "Bearer " + token}
            )
            self.socket = self.context.__enter__()
        return self.socket.send_json(frame)

    def send_text(self, text):
        import json

        try:
            frame = json.loads(text)
        except ValueError:
            frame = {}
        if self.socket is None:
            # Establish a proven node transport before testing malformed frames.
            authorization = self.headers.get(
                "Authorization", self.headers.get("authorization", "")
            )
            owner_id = self.client.app.state.auth_service.verify_access_token(
                authorization.removeprefix("Bearer ")
            )
            node_id = (
                frame.get("payload", {}).get("node_id", "fixture-node")
                if isinstance(frame, dict)
                else "fixture-node"
            )
            token = seed_runtime_credential(
                self.client.app.state.connection, node_id=node_id, owner_id=owner_id
            )
            self.context = self.client.websocket_connect(
                "/im/ws/gateway", headers={"Authorization": "Bearer " + token}
            )
            self.socket = self.context.__enter__()
        return self.socket.send_text(text)

    def __getattr__(self, name):
        return getattr(self.socket, name)


def gateway_socket(client: TestClient, *, headers=None):
    """Return an enrolled-machine fixture rather than presenting a human JWT as a node."""
    return GatewaySocketFixture(client, headers=headers)


def browser_socket(client: TestClient, access_token: str):
    """Exchange an active human session for a one-use ticket and trusted Origin."""
    response = client.post(
        "/im/v1/auth/ws-ticket", headers={"Authorization": "Bearer " + access_token}
    )
    assert response.status_code == 200, response.text
    return client.websocket_connect(
        "/im/ws/user?ticket=" + response.json()["ticket"],
        headers={"Origin": client.app.state.public_url.rstrip("/")},
    )


from IM.ws.gateway.sessions import GatewaySessions


class EnrolledGatewaySessions(GatewaySessions):
    """Unit assembly with the app handshake's already-verified node state attached."""

    async def register(self, *, websocket, payload, authenticated_owner_id):
        from types import SimpleNamespace

        if self._node_persistence is not None:
            node_id = payload["node_id"]
            connection = self._node_persistence._connection
            if not authenticated_owner_id:
                from IM.infra.repositories.users import UserRepository

                repo = UserRepository(connection)
                user = repo.get_user_by_username(
                    username="fixture-owner"
                ) or repo.create_user(
                    username="fixture-owner", display_name="Fixture Owner"
                )
                authenticated_owner_id = user.id
            if (
                connection.execute(
                    "SELECT 1 FROM users WHERE owner_id=?", (authenticated_owner_id,)
                ).fetchone()
                is None
            ):
                connection.execute(
                    "INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES (?,?,?,?,datetime('now'),'active')",
                    (
                        authenticated_owner_id,
                        authenticated_owner_id,
                        "Fixture Owner",
                        authenticated_owner_id,
                    ),
                )
                connection.commit()
            seed_runtime_credential(
                connection, node_id=node_id, owner_id=authenticated_owner_id
            )
            row = connection.execute(
                "SELECT node_epoch FROM node_binding_state WHERE node_id=?", (node_id,)
            ).fetchone()
            websocket.state = SimpleNamespace(
                authenticated_node_id=node_id, authenticated_node_epoch=row[0]
            )
        return await super().register(
            websocket=websocket,
            payload=payload,
            authenticated_owner_id=authenticated_owner_id,
        )
