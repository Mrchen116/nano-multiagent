"""Concurrent device binding transaction regressions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import threading

from IM.application.bind_service import BindService
from IM.infra.binding_store import BindingStore
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    AgentProfileRepository,
    BindRepository,
    NodeRepository,
    UserRepository,
)


def _service(connection: sqlite3.Connection, db_path: Path) -> BindService:
    return BindService(
        users=UserRepository(connection),
        nodes=NodeRepository(connection),
        binds=BindRepository(connection),
        profiles=AgentProfileRepository(connection),
        binding_store=BindingStore(db_path),
        bind_base_url="http://im.test/bind/confirm",
    )


def _protected_rows(
    connection: sqlite3.Connection,
) -> dict[str, list[tuple[object, ...]]]:
    tables = (
        "agent_channels",
        "channel_manifest_heads",
        "node_credential_keys",
        "agent_channel_removals",
    )
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
        for table in tables
    }


def test_cross_owner_concurrent_bind_has_one_atomic_winner(tmp_path: Path) -> None:
    """Bind guard and ownership writes commit once without touching channel ciphertext."""
    db_path = tmp_path / "binding.db"
    setup = connect(db_path)
    initialize_schema(setup)
    users = UserRepository(setup)
    alice = users.create_user(username="alice", display_name="Alice")
    bob = users.create_user(username="bob", display_name="Bob")
    nodes = NodeRepository(setup)
    nodes.upsert_node(node_id="node-race", node_name="Race")
    profiles = AgentProfileRepository(setup)
    profiles.upsert_profile(
        agent_id="agent-race",
        owner_id="",
        node_id="node-race",
        display_name="Race Agent",
        description="",
        system_prompt="Race safely.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    binds = BindRepository(setup)
    alice_bind = binds.create_bind_request(
        node_id="node-race", bind_base_url="http://im.test/bind/confirm"
    )
    bob_bind = binds.create_bind_request(
        node_id="node-race", bind_base_url="http://im.test/bind/confirm"
    )
    setup.executescript(
        """
        INSERT INTO node_credential_keys VALUES
          ('node-race', '', 'key-before', 'alg-before', 'public-before', 'time-before');
        INSERT INTO channel_manifest_heads VALUES
          ('node-race', '', 4, 3, NULL, NULL, 'init-before', 'time-before');
        INSERT INTO agent_channels VALUES
          ('channel-before', '', 'agent-race', 'node-race', 'feishu', 1,
           '{"app_id":"cli_before"}', 'fingerprint', 1, '{}',
           '{"ciphertext":"opaque"}', 'key-before', 1, 4,
           'time-before', 'time-before');
        INSERT INTO agent_channel_removals VALUES
          ('removed-before', 'token-before', '', 'agent-race', 'node-race',
           'feishu', '{"app_id":"cli_old"}', 2, 4, 'pending', NULL, NULL,
           NULL, 'expires-after', 'time-before', 'time-before');
        """
    )
    setup.commit()
    protected_before = _protected_rows(setup)

    alice_connection = connect(db_path)
    bob_connection = connect(db_path)
    alice_service = _service(alice_connection, db_path)
    bob_service = _service(bob_connection, db_path)
    start = threading.Barrier(2)

    def confirm(service: BindService, bind_id: str, user_id: str):
        start.wait()
        try:
            return service.confirm_bind(bind_id=bind_id, user_id=user_id)
        except ValueError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda args: confirm(*args),
                (
                    (alice_service, alice_bind.bind_id, alice.id),
                    (bob_service, bob_bind.bind_id, bob.id),
                ),
            )
        )

    winners = [result for result in results if not isinstance(result, ValueError)]
    losers = [result for result in results if isinstance(result, ValueError)]
    assert len(winners) == len(losers) == 1
    assert str(losers[0]) == "node already bound to another owner"
    winner = winners[0]
    winner_user = alice if winner.user_id == alice.id else bob
    loser_user = bob if winner_user is alice else alice
    assert (
        NodeRepository(setup).get_node(node_id="node-race").owner_id
        == winner_user.owner_id
    )
    assert profiles.get_profile(agent_id="agent-race").owner_id == winner_user.owner_id
    assert users.get_user(user_id=winner_user.id).default_entry_node_id == "node-race"
    assert users.get_user(user_id=loser_user.id).default_entry_node_id is None
    assert _protected_rows(setup) == protected_before

    winning_service = alice_service if winner_user is alice else bob_service
    assert (
        winning_service.confirm_bind(bind_id=winner.bind_id, user_id=winner_user.id)
        == winner
    )

    alice_connection.close()
    bob_connection.close()
    setup.close()
