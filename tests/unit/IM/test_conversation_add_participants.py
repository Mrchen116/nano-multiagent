"""Unit tests for adding participants to an existing conversation (feat-438-M1).

Covers the new ``POST /conversations/{id}/participants`` endpoint and its
repository backing ``add_participants``, plus the decision-5 contract that the
serialized participant carries ``user_id`` so the frontend can drive the
``DELETE /participants/{user_id}`` remove path (CRITICAL-1 regression).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import ConversationRepository, UserRepository


def _build_repos(tmp_path: Path) -> tuple[UserRepository, ConversationRepository]:
    """Build repositories bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return UserRepository(connection), ConversationRepository(connection)


# ---------------------------------------------------------------------------
# Repository layer: add_participants
# ---------------------------------------------------------------------------


def test_add_participants_resolves_agent_and_inserts(tmp_path: Path) -> None:
    """An agent reference is resolved to its user row and inserted as membership."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    agent = users.create_user(username="agent:planner", display_name="Planner")

    convo = conversations.create_conversation(
        title="Solo", participant_ids=[alice.id], creator_id=alice.id
    )

    updated = conversations.add_participants(
        conversation_id=convo.id, references=["agent:planner"]
    )

    assert agent.id in updated.participant_ids
    agent_actor = next(p for p in updated.participants if p.type == "agent")
    # decision 5: the agent participant's id is the logical agent_id, while
    # user_id is the stable UUID used by the remove endpoint.
    assert agent_actor.id == "planner"
    assert agent_actor.user_id == agent.id


def test_add_participants_idempotent_skips_existing(tmp_path: Path) -> None:
    """Re-adding an already-present agent neither duplicates nor raises."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    users.create_user(username="agent:planner", display_name="Planner")

    convo = conversations.create_conversation(
        title="Solo", participant_ids=[alice.id], creator_id=alice.id
    )
    conversations.add_participants(conversation_id=convo.id, references=["agent:planner"])
    updated = conversations.add_participants(
        conversation_id=convo.id, references=["agent:planner"]
    )

    agent_count = sum(1 for p in updated.participants if p.type == "agent")
    assert agent_count == 1


def test_add_participants_empty_raises(tmp_path: Path) -> None:
    """An empty reference list is rejected."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    convo = conversations.create_conversation(
        title="Solo", participant_ids=[alice.id], creator_id=alice.id
    )

    with pytest.raises(ValueError, match="participants must not be empty"):
        conversations.add_participants(conversation_id=convo.id, references=[])


def test_add_participants_unknown_agent_raises(tmp_path: Path) -> None:
    """A reference that resolves to no user is rejected."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    convo = conversations.create_conversation(
        title="Solo", participant_ids=[alice.id], creator_id=alice.id
    )

    with pytest.raises(ValueError, match="unknown users"):
        conversations.add_participants(
            conversation_id=convo.id, references=["agent:ghost"]
        )


def test_add_participants_conversation_not_found_raises(tmp_path: Path) -> None:
    """Adding to a missing conversation raises ValueError."""
    users, conversations = _build_repos(tmp_path)
    users.create_user(username="agent:planner", display_name="Planner")

    with pytest.raises(ValueError, match="conversation_id not found"):
        conversations.add_participants(
            conversation_id="nonexistent", references=["agent:planner"]
        )


def test_add_participants_does_not_refreeze_config_profile_version(
    tmp_path: Path,
) -> None:
    """decision 3: adding to an existing conversation keeps its frozen config version."""
    users, conversations = _build_repos(tmp_path)
    alice = users.create_user(username="alice", display_name="Alice")
    users.create_user(username="agent:planner", display_name="Planner")

    convo = conversations.create_conversation(
        title="Solo", participant_ids=[alice.id], creator_id=alice.id
    )
    before = conversations.get_conversation(conversation_id=convo.id)
    assert before is not None

    updated = conversations.add_participants(
        conversation_id=convo.id, references=["agent:planner"]
    )

    assert updated.config_profile_version == before.config_profile_version


# ---------------------------------------------------------------------------
# HTTP route: POST /im/v1/conversations/{id}/participants
# ---------------------------------------------------------------------------


def _make_app(tmp_path: Path) -> object:
    """Build a FastAPI app wired to a fresh temporary DB."""
    from IM.app import create_app

    return create_app(db_path=tmp_path / "im.db", upload_dir=tmp_path / "uploads")


def _register_owner(client: TestClient) -> tuple[dict, str]:
    """Register alice; return (auth headers, alice user id)."""
    reg = client.post(
        "/im/v1/auth/register",
        json={"username": "alice", "password": "pw12345678", "display_name": "Alice"},
    )
    assert reg.status_code in (200, 201), f"register failed: {reg.text}"
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, reg.json()["user"]["id"]


def _seed_agent(app: object, agent_id: str) -> str:
    """Create an ``agent:<agent_id>`` user via the live app connection; return its user_id."""
    agent = UserRepository(app.state.connection).create_user(  # type: ignore[attr-defined]
        username=f"agent:{agent_id}", display_name=agent_id
    )
    return agent.id


def test_post_participants_adds_agent_returns_200(tmp_path: Path) -> None:
    """POST with an agent actor returns 200 and the agent appears in participants."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        _seed_agent(app, "planner")
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]

        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": [{"type": "agent", "id": "planner"}]},
            headers=auth,
        )

    assert resp.status_code == 200, resp.text
    agents = [p for p in resp.json()["participants"] if p["type"] == "agent"]
    assert len(agents) == 1
    assert agents[0]["id"] == "planner"


def test_post_participants_idempotent(tmp_path: Path) -> None:
    """Re-adding the same agent stays 200 and does not duplicate."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        _seed_agent(app, "planner")
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]
        body = {"participants": [{"type": "agent", "id": "planner"}]}
        client.post(f"/im/v1/conversations/{convo_id}/participants", json=body, headers=auth)
        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants", json=body, headers=auth
        )

    assert resp.status_code == 200, resp.text
    agents = [p for p in resp.json()["participants"] if p["type"] == "agent"]
    assert len(agents) == 1


def test_post_participants_empty_returns_400(tmp_path: Path) -> None:
    """An empty participant list is rejected with 400."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]
        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": []},
            headers=auth,
        )

    assert resp.status_code == 400, resp.text


def test_post_participants_unknown_agent_returns_400(tmp_path: Path) -> None:
    """An unresolvable agent id is rejected with 400."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]
        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": [{"type": "agent", "id": "ghost"}]},
            headers=auth,
        )

    assert resp.status_code == 400, resp.text


def test_post_participants_cross_tenant_returns_404(tmp_path: Path) -> None:
    """Adding to a conversation outside the caller's tenant returns 404."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth_alice, alice_id = _register_owner(client)
        _seed_agent(app, "planner")
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth_alice,
        )
        convo_id = convo.json()["id"]

        reg_bob = client.post(
            "/im/v1/auth/register",
            json={"username": "bob", "password": "pw12345678", "display_name": "Bob"},
        )
        auth_bob = {"Authorization": f"Bearer {reg_bob.json()['access_token']}"}
        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": [{"type": "agent", "id": "planner"}]},
            headers=auth_bob,
        )

    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# decision 5 / CRITICAL-1: user_id is serialized and drives remove
# ---------------------------------------------------------------------------


def test_participant_payload_carries_user_id(tmp_path: Path) -> None:
    """The serialized agent participant exposes user_id distinct from its id."""
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        agent_user_id = _seed_agent(app, "planner")
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]
        resp = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": [{"type": "agent", "id": "planner"}]},
            headers=auth,
        )

    agent = next(p for p in resp.json()["participants"] if p["type"] == "agent")
    assert agent["id"] == "planner"
    assert agent["user_id"] == agent_user_id
    assert agent["user_id"] != agent["id"]


def test_remove_participant_by_user_id_removes_agent(tmp_path: Path) -> None:
    """CRITICAL-1: DELETE keyed on the participant's user_id actually removes it.

    Passing the agent's logical id would silently fail; the contract is that the
    frontend reads participant.user_id from the serialized payload and uses that.
    """
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        auth, alice_id = _register_owner(client)
        _seed_agent(app, "planner")
        convo = client.post(
            "/im/v1/conversations",
            json={"title": "Solo", "participant_ids": [alice_id]},
            headers=auth,
        )
        convo_id = convo.json()["id"]
        added = client.post(
            f"/im/v1/conversations/{convo_id}/participants",
            json={"participants": [{"type": "agent", "id": "planner"}]},
            headers=auth,
        )
        agent = next(p for p in added.json()["participants"] if p["type"] == "agent")

        removed = client.delete(
            f"/im/v1/conversations/{convo_id}/participants/{agent['user_id']}",
            headers=auth,
        )
        assert removed.status_code == 204, removed.text

        after = client.get(f"/im/v1/conversations/{convo_id}", headers=auth)

    assert all(p["type"] != "agent" for p in after.json()["participants"])
