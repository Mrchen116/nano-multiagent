"""Unit tests for group conversation rename via PATCH (M235)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import ConversationRepository, UserRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_repos(tmp_path: Path) -> tuple[UserRepository, ConversationRepository]:
    """Build repositories bound to a temporary SQLite database."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return UserRepository(connection), ConversationRepository(connection)


def _make_group(
    users: UserRepository,
    conversations: ConversationRepository,
) -> tuple[object, object]:
    """Create two users and a 3-participant group conversation for testing."""
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    carol = users.create_user(username="carol", display_name="Carol")
    convo = conversations.create_conversation(
        title="Alice + Bob + Carol",
        participant_ids=[alice.id, bob.id, carol.id],
        creator_id=alice.id,
    )
    return alice, convo


# ---------------------------------------------------------------------------
# Repository layer tests
# ---------------------------------------------------------------------------


def test_update_conversation_title_changes_stored_title(tmp_path: Path) -> None:
    """update_conversation with a new title persists the change."""
    users, conversations = _build_repos(tmp_path)
    _alice, convo = _make_group(users, conversations)

    updated = conversations.update_conversation(
        conversation_id=convo.id,
        title="My Custom Group",
        is_pinned=None,
        is_muted=None,
    )

    assert updated.title == "My Custom Group"
    # Verify persistence by re-loading.
    reloaded = conversations.get_conversation(conversation_id=convo.id)
    assert reloaded is not None
    assert reloaded.title == "My Custom Group"


def test_update_conversation_empty_title_raises_value_error(tmp_path: Path) -> None:
    """update_conversation rejects blank or whitespace-only title."""
    users, conversations = _build_repos(tmp_path)
    _alice, convo = _make_group(users, conversations)

    with pytest.raises(ValueError, match="title must be non-empty"):
        conversations.update_conversation(
            conversation_id=convo.id,
            title="   ",
            is_pinned=None,
            is_muted=None,
        )


def test_update_conversation_not_found_raises_value_error(tmp_path: Path) -> None:
    """update_conversation raises ValueError when conversation does not exist."""
    _, conversations = _build_repos(tmp_path)

    with pytest.raises(ValueError, match="conversation_id not found"):
        conversations.update_conversation(
            conversation_id="nonexistent",
            title="New Name",
            is_pinned=None,
            is_muted=None,
        )


def test_update_conversation_partial_only_title_changed(tmp_path: Path) -> None:
    """Passing only title leaves is_pinned and is_muted unchanged."""
    users, conversations = _build_repos(tmp_path)
    _alice, convo = _make_group(users, conversations)

    # Pin the conversation first.
    conversations.update_conversation(
        conversation_id=convo.id,
        title=None,
        is_pinned=True,
        is_muted=False,
    )

    # Now rename only.
    updated = conversations.update_conversation(
        conversation_id=convo.id,
        title="Renamed Group",
        is_pinned=None,
        is_muted=None,
    )

    assert updated.title == "Renamed Group"
    assert updated.is_pinned is True
    assert updated.is_muted is False


# ---------------------------------------------------------------------------
# HTTP route tests (PATCH /im/v1/conversations/{id})
# ---------------------------------------------------------------------------


def _make_test_client(tmp_path: Path) -> tuple[object, str, str]:
    """Create a FastAPI app wired to a temporary DB; return (app, alice_id, convo_id).

    Returns a FastAPI app (not a TestClient) so callers can use it inside
    ``with TestClient(app) as client:`` to trigger the lifespan startup.
    """
    from IM.app import create_app

    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    carol = users.create_user(username="carol", display_name="Carol")
    convo = conversations.create_conversation(
        title="Alice + Bob",
        participant_ids=[alice.id, bob.id, carol.id],
        creator_id=alice.id,
    )
    connection.close()
    app = create_app(db_path=db_path, upload_dir=tmp_path / "uploads")
    return app, alice.id, convo.id


def test_patch_title_returns_updated_conversation(tmp_path: Path) -> None:
    """PATCH /im/v1/conversations/{id} with {title} returns 200 and new title."""
    app, _alice_id, convo_id = _make_test_client(tmp_path)

    with TestClient(app) as client:
        response = client.patch(
            f"/im/v1/conversations/{convo_id}",
            json={"title": "Team Alpha"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Team Alpha"
    assert data["id"] == convo_id


def test_patch_empty_title_returns_400(tmp_path: Path) -> None:
    """PATCH with blank title returns 400 Bad Request."""
    app, _alice_id, convo_id = _make_test_client(tmp_path)

    with TestClient(app) as client:
        response = client.patch(
            f"/im/v1/conversations/{convo_id}",
            json={"title": "   "},
        )

    assert response.status_code == 400


def test_patch_title_nonexistent_returns_404(tmp_path: Path) -> None:
    """PATCH on missing conversation_id returns 404."""
    app, _alice_id, _convo_id = _make_test_client(tmp_path)

    with TestClient(app) as client:
        response = client.patch(
            "/im/v1/conversations/does-not-exist",
            json={"title": "Whatever"},
        )

    assert response.status_code == 404
