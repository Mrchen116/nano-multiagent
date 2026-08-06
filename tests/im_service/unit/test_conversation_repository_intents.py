"""Intent-level tests for conversation persistence."""

from collections.abc import Callable
from pathlib import Path
import sqlite3

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.conversations import ExternalConversationWriteResult
from IM.infra.repositories.users import UserRepository


class _InsertRaceConnection:
    """Delegate to SQLite while injecting one competing external insert."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        on_external_insert: Callable[[], None],
    ) -> None:
        self._connection = connection
        self._on_external_insert = on_external_insert
        self._raced = False

    def execute(self, sql: str, parameters=()):
        if not self._raced and "INSERT INTO conversations(" in sql:
            self._raced = True
            self._on_external_insert()
        return self._connection.execute(sql, parameters)

    def executemany(self, sql: str, parameters):
        return self._connection.executemany(sql, parameters)

    def __enter__(self):
        return self._connection.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(exc_type, exc_value, traceback)


def _external_write(
    repository: ConversationRepository,
    *,
    owner_id: str,
    owner_user_id: str,
) -> ExternalConversationWriteResult:
    return repository.find_or_create_external_conversation(
        external_source="feishu",
        external_chat_id="oc_product",
        agent_id="plato",
        title="Plato · 产品群 · feishu",
        is_group=True,
        participant_ids=[f"user:{owner_user_id}", "agent:plato"],
        owner_id=owner_id,
        creator_id=f"user:{owner_user_id}",
    )


def _seed_external_participants(
    connection: sqlite3.Connection,
) -> tuple[str, str]:
    users = UserRepository(connection)
    owner = users.create_user(username="owner", display_name="Owner")
    users.create_user(username="agent:plato", display_name="Plato")
    AgentProfileRepository(connection).upsert_profile(
        agent_id="plato",
        owner_id=owner.owner_id,
        display_name="Plato",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="MENTION",
        default_model=None,
        workspace_root=None,
    )
    return owner.owner_id, owner.id


def test_external_find_or_create_reports_created_and_exists(tmp_path: Path) -> None:
    """Expose creation status without a caller-side pre-query."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    owner_id, owner_user_id = _seed_external_participants(connection)
    conversations = ConversationRepository(connection)

    first = _external_write(
        conversations, owner_id=owner_id, owner_user_id=owner_user_id
    )
    repeated = _external_write(
        conversations, owner_id=owner_id, owner_user_id=owner_user_id
    )

    assert first.created is True
    assert repeated.created is False
    assert repeated.conversation.id == first.conversation.id
    assert conversations.exists(first.conversation.id) is True
    assert conversations.exists("missing") is False


def test_external_find_or_create_reports_competing_insert_as_existing(
    tmp_path: Path,
) -> None:
    """Recover a uniqueness race and report that this caller did not create the row."""
    db_path = tmp_path / "im.db"
    primary = connect(db_path)
    initialize_schema(primary)
    owner_id, owner_user_id = _seed_external_participants(primary)
    competitor = connect(db_path)
    competing_repository = ConversationRepository(competitor)
    raced = _InsertRaceConnection(
        primary,
        on_external_insert=lambda: _external_write(
            competing_repository,
            owner_id=owner_id,
            owner_user_id=owner_user_id,
        ),
    )

    result = _external_write(
        ConversationRepository(raced),  # type: ignore[arg-type]
        owner_id=owner_id,
        owner_user_id=owner_user_id,
    )

    assert result.created is False
    assert (
        result.conversation.id
        == _external_write(
            competing_repository,
            owner_id=owner_id,
            owner_user_id=owner_user_id,
        ).conversation.id
    )
