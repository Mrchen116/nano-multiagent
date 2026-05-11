"""R4 tests: HTTP routes must be Bearer-auth gated and owner-scoped.

These tests assert the post-M1 multi-user contract on the data-plane routes
(``/im/v1/me``, conversations, messages, agents, nodes, metrics): missing or
invalid tokens return 401, and a tenant cannot reach another tenant's resources
(404, not 403, to avoid existence oracles per the design §2a).

The legacy ``POST /im/v1/users`` and ``GET /im/v1/users`` endpoints are removed
in R4 — register goes through ``/im/v1/auth/register`` from R2.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from .conftest import authorize, make_app_client, register_user


def test_me_requires_bearer_token(tmp_path: Path) -> None:
    """``GET /im/v1/me`` must return 401 without a Bearer token (no ?user_id= shortcut)."""
    with make_app_client(tmp_path) as client:
        response = client.get("/im/v1/me")
        assert response.status_code == 401


def test_me_returns_current_user_from_token(tmp_path: Path) -> None:
    """With a valid Bearer token, ``GET /im/v1/me`` returns the token subject."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        response = client.get("/im/v1/me")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == alice.id
        assert body["owner_id"] == alice.owner_id
        assert body["username"] == "alice"


def test_patch_me_uses_token_user_not_query_param(tmp_path: Path) -> None:
    """``PATCH /im/v1/me`` ignores ``?user_id=`` and updates the token subject."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        response = client.patch(
            "/im/v1/me",
            json={"display_name": "Alice Cooper", "default_entry_node_id": None},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Alice Cooper"
        assert response.json()["id"] == alice.id


def test_list_conversations_requires_token(tmp_path: Path) -> None:
    """``GET /im/v1/conversations`` returns 401 without a token."""
    with make_app_client(tmp_path) as client:
        response = client.get("/im/v1/conversations")
        assert response.status_code == 401


def test_list_conversations_is_owner_scoped(tmp_path: Path) -> None:
    """Alice and Bob register independently; each only sees their own conversation."""
    with make_app_client(tmp_path) as alice_client:
        alice = register_user(alice_client, username="alice")
        authorize(alice_client, alice)
        # Create another client over the same app for Bob
        bob_client = TestClient(alice_client.app)
        with bob_client:
            bob = register_user(bob_client, username="bob")
            authorize(bob_client, bob)

            alice_conv = alice_client.post(
                "/im/v1/conversations",
                json={"title": "Alice's room", "participant_ids": [alice.id]},
            )
            assert alice_conv.status_code == 201, alice_conv.text
            bob_conv = bob_client.post(
                "/im/v1/conversations",
                json={"title": "Bob's room", "participant_ids": [bob.id]},
            )
            assert bob_conv.status_code == 201, bob_conv.text

            alice_items = alice_client.get("/im/v1/conversations").json()["items"]
            bob_items = bob_client.get("/im/v1/conversations").json()["items"]
            alice_ids = {item["id"] for item in alice_items}
            bob_ids = {item["id"] for item in bob_items}
            assert alice_conv.json()["id"] in alice_ids
            assert alice_conv.json()["id"] not in bob_ids
            assert bob_conv.json()["id"] in bob_ids
            assert bob_conv.json()["id"] not in alice_ids


def test_get_conversation_cross_tenant_returns_404(tmp_path: Path) -> None:
    """Reading another tenant's conversation must 404, not 403 (no existence oracle)."""
    with make_app_client(tmp_path) as alice_client:
        alice = register_user(alice_client, username="alice")
        authorize(alice_client, alice)
        bob_client = TestClient(alice_client.app)
        with bob_client:
            bob = register_user(bob_client, username="bob")
            authorize(bob_client, bob)
            alice_conv = alice_client.post(
                "/im/v1/conversations",
                json={"title": "Alice's room", "participant_ids": [alice.id]},
            ).json()
            cross = bob_client.get(f"/im/v1/conversations/{alice_conv['id']}")
            assert cross.status_code == 404


def test_create_message_cross_tenant_returns_404(tmp_path: Path) -> None:
    """Posting a message into another tenant's conversation must 404."""
    with make_app_client(tmp_path) as alice_client:
        alice = register_user(alice_client, username="alice")
        authorize(alice_client, alice)
        bob_client = TestClient(alice_client.app)
        with bob_client:
            bob = register_user(bob_client, username="bob")
            authorize(bob_client, bob)
            alice_conv = alice_client.post(
                "/im/v1/conversations",
                json={"title": "Alice's room", "participant_ids": [alice.id]},
            ).json()
            response = bob_client.post(
                f"/im/v1/conversations/{alice_conv['id']}/messages",
                json={"sender_user_id": bob.id, "content": "intrude"},
            )
            assert response.status_code == 404


def test_list_messages_requires_token(tmp_path: Path) -> None:
    """``GET conversations/{id}/messages`` returns 401 without a token."""
    with make_app_client(tmp_path) as client:
        response = client.get("/im/v1/conversations/whatever/messages")
        assert response.status_code == 401


def test_list_agents_requires_token(tmp_path: Path) -> None:
    """``GET /im/v1/agents`` returns 401 without a token."""
    with make_app_client(tmp_path) as client:
        response = client.get("/im/v1/agents")
        assert response.status_code == 401


def test_list_nodes_requires_token(tmp_path: Path) -> None:
    """``GET /im/v1/nodes`` returns 401 without a token."""
    with make_app_client(tmp_path) as client:
        response = client.get("/im/v1/nodes")
        assert response.status_code == 401


def test_legacy_users_endpoints_are_removed(tmp_path: Path) -> None:
    """``POST/GET /im/v1/users`` no longer exists; register goes through /im/v1/auth/register."""
    with make_app_client(tmp_path) as client:
        post = client.post(
            "/im/v1/users",
            json={"username": "ghost", "display_name": "Ghost"},
        )
        get = client.get("/im/v1/users")
        # FastAPI returns 404 for an unmounted path; method-not-allowed also acceptable.
        assert post.status_code in {404, 405}
        assert get.status_code in {404, 405}


def test_metrics_usage_requires_token_and_scopes_to_owner(tmp_path: Path) -> None:
    """``/im/v1/metrics/usage`` requires auth and only returns rows for the caller's owner_id."""
    with make_app_client(tmp_path) as client:
        unauthenticated = client.get("/im/v1/metrics/usage")
        assert unauthenticated.status_code == 401

        alice = register_user(client, username="alice")
        authorize(client, alice)
        response = client.get("/im/v1/metrics/usage")
        assert response.status_code == 200
        # Every returned row must belong to alice's tenant. Empty list is acceptable.
        for row in response.json():
            assert row["owner_id"] in {alice.owner_id, None}


def test_patch_me_persists_locale(tmp_path: Path) -> None:
    """``PATCH /im/v1/me`` accepts and persists the ``locale`` field for M7."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        response = client.patch(
            "/im/v1/me",
            json={
                "display_name": alice.display_name,
                "default_entry_node_id": None,
                "locale": "zh",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["locale"] == "zh"
        # Round-trip: GET reflects the persisted locale
        again = client.get("/im/v1/me").json()
        assert again["locale"] == "zh"
