"""Keep manual private titles durable across external synchronization."""

import pytest

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.conversations import ConversationRepository
from tests.im_service.unit.test_conversation_repository_intents import (
    _InsertRaceConnection,
    _seed_external_participants,
)


def setup(tmp_path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    owner, user = _seed_external_participants(connection)
    params = dict(
        external_source="feishu",
        external_chat_id="rename-case",
        agent_id="plato",
        title="Source title",
        is_group=False,
        participant_ids=[f"user:{user}", "agent:plato"],
        owner_id=owner,
        creator_id=f"user:{user}",
    )
    return connection, params


@pytest.mark.parametrize("is_group", [False, True])
def test_custom_direct_title_survives_sync_but_group_sync_stays_unchanged(
    tmp_path, is_group
):
    connection, params = setup(tmp_path)
    params["is_group"] = is_group
    repo = ConversationRepository(connection)
    original = repo.find_or_create_external_conversation(**params).conversation
    updated = repo.find_or_create_external_conversation(
        **{**params, "title": "Updated source"}
    )
    assert updated.conversation.title == "Updated source"
    repo.update_conversation(
        conversation_id=original.id, title="My title", is_pinned=None, is_muted=None
    )
    repo.update_conversation(
        conversation_id=original.id, title=None, is_pinned=True, is_muted=None
    )
    synced = repo.find_or_create_external_conversation(**params).conversation
    assert synced.id == original.id
    assert synced.title == ("Source title" if is_group else "My title")
    assert synced.is_pinned


def test_competing_shadow_insert_retains_a_manual_direct_title(tmp_path):
    connection, params = setup(tmp_path)
    competitor = ConversationRepository(connect(tmp_path / "im.db"))

    def create_and_rename():
        created = competitor.find_or_create_external_conversation(**params).conversation
        competitor.update_conversation(
            conversation_id=created.id,
            title="Manual title",
            is_pinned=None,
            is_muted=None,
        )

    raced = _InsertRaceConnection(connection, on_external_insert=create_and_rename)
    result = ConversationRepository(raced).find_or_create_external_conversation(
        **params
    )
    assert result.created is False
    assert result.conversation.title == "Manual title"


def test_existing_database_gains_custom_title_flag_without_rewriting_titles(tmp_path):
    connection, params = setup(tmp_path)
    repo = ConversationRepository(connection)
    original = repo.find_or_create_external_conversation(**params).conversation
    connection.execute("ALTER TABLE conversations DROP COLUMN title_is_custom")
    connection.commit()
    initialize_schema(connection)
    initialize_schema(connection)
    row = connection.execute(
        "SELECT title,title_is_custom FROM conversations WHERE id=?", (original.id,)
    ).fetchone()
    assert tuple(row) == ("Source title", 0)
