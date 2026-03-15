"""Stage the live M104 acceptance runtime so M149 can rerun against a usable browser path."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from IM.infra.db import initialize_schema

RUNTIME_ROOT = Path("/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime")
RUNTIME_DB = RUNTIME_ROOT / "im.db"
M149_AGENT_ID = "agent-m149-1773456058"
ACCEPTANCE_USER_USERNAME = "you"
NODE_ID = "m104-acceptance-node"
OLD_CONVERSATION_TITLE = "M149 OLD direct 1773456058"
NEW_CONVERSATION_TITLE = "M149 NEW direct 1773456058"
M149_WORKSPACE = RUNTIME_ROOT / "m149-freeze-workspace"


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection


def _ensure_runtime_user(connection: sqlite3.Connection, *, username: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT id, username, display_name, owner_id, default_entry_node_id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"runtime user missing: {username}")
    return row


def _ensure_agent_alias(connection: sqlite3.Connection, *, agent_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
        (f"agent:{agent_id}",),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"agent alias user missing: agent:{agent_id}")
    return row


def _conversation_snapshot(connection: sqlite3.Connection, conversation_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, title, type, owner_id, config_agent_id, config_profile_version, config_system_prompt
        FROM conversations
        WHERE id = ?
        """,
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"conversation missing after stage: {conversation_id}")
    return row


def _current_agent_snapshot(connection: sqlite3.Connection, *, agent_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT agent_id, profile_version, system_prompt FROM agent_profiles WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"agent profile missing: {agent_id}")
    return row


def _history_message_snapshot(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    user_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT m.id, m.content, rt.payload_json
        FROM messages m
        LEFT JOIN relay_tasks rt ON rt.message_id = m.id
        WHERE m.conversation_id = ?
          AND m.sender_user_id = ?
          AND rt.payload_json IS NOT NULL
        ORDER BY m.rowid ASC
        LIMIT 1
        """,
        (conversation_id, user_id),
    ).fetchone()


def _extract_frozen_snapshot_from_payload(payload_json: str) -> tuple[str | None, int | None, str | None]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None, None, None
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None, None, None
    agent_id = metadata.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id.strip():
        agent_id = None
    profile_version = metadata.get("config_profile_version")
    if not isinstance(profile_version, int):
        profile_version = None
    system_prompt = metadata.get("system_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        system_prompt = None
    return agent_id, profile_version, system_prompt


def _ensure_old_direct_conversation(connection: sqlite3.Connection, *, self_user_id: str, peer_user_id: str) -> sqlite3.Row:
    del peer_user_id
    conversation = connection.execute(
        "SELECT id FROM conversations WHERE title = ? ORDER BY rowid DESC LIMIT 1",
        (OLD_CONVERSATION_TITLE,),
    ).fetchone()
    if conversation is None:
        raise RuntimeError(
            "old M149 direct conversation is missing from the live runtime; recreate it from the saved M149 acceptance runtime first"
        )
    conversation_id = str(conversation["id"])

    history_row = _history_message_snapshot(connection, conversation_id=conversation_id, user_id=self_user_id)
    agent_id = profile_version = system_prompt = None
    if history_row is not None:
        agent_id, profile_version, system_prompt = _extract_frozen_snapshot_from_payload(str(history_row["payload_json"]))
    if agent_id is None:
        agent_id = M149_AGENT_ID
    if profile_version is None or system_prompt is None:
        agent_snapshot = _current_agent_snapshot(connection, agent_id=agent_id)
        if profile_version is None:
            profile_version = int(agent_snapshot["profile_version"])
        if system_prompt is None:
            system_prompt = str(agent_snapshot["system_prompt"])

    connection.execute(
        """
        UPDATE conversations
        SET config_agent_id = ?,
            config_profile_version = ?,
            config_system_prompt = ?
        WHERE id = ?
        """,
        (agent_id, profile_version, system_prompt, conversation_id),
    )
    return _conversation_snapshot(connection, conversation_id)


def _create_new_direct_conversation(connection: sqlite3.Connection, *, self_user_id: str, peer_user_id: str) -> sqlite3.Row:
    existing = connection.execute(
        "SELECT id FROM conversations WHERE title = ? ORDER BY rowid DESC LIMIT 1",
        (NEW_CONVERSATION_TITLE,),
    ).fetchone()
    if existing is not None:
        snapshot = _conversation_snapshot(connection, str(existing["id"]))
        if snapshot["config_agent_id"] is not None and snapshot["config_profile_version"] is not None:
            return snapshot
        connection.execute("DELETE FROM conversation_participants WHERE conversation_id = ?", (str(existing["id"]),))
        connection.execute("DELETE FROM conversations WHERE id = ?", (str(existing["id"]),))

    created_at = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[0]
    conversation_id = connection.execute("SELECT lower(hex(randomblob(16)))").fetchone()[0]
    owner_id = connection.execute("SELECT lower(hex(randomblob(16)))").fetchone()[0]
    agent_snapshot = _current_agent_snapshot(connection, agent_id=M149_AGENT_ID)
    connection.execute(
        """
        INSERT INTO conversations(
            id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at,
            config_agent_id, config_profile_version, config_system_prompt, created_at
        ) VALUES (?, ?, 'direct', ?, 0, 0, 0, NULL, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            NEW_CONVERSATION_TITLE,
            owner_id,
            str(agent_snapshot["agent_id"]),
            int(agent_snapshot["profile_version"]),
            str(agent_snapshot["system_prompt"]),
            created_at,
        ),
    )
    connection.executemany(
        "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
        [(conversation_id, self_user_id), (conversation_id, peer_user_id)],
    )
    return _conversation_snapshot(connection, conversation_id)


def stage_runtime() -> dict[str, object]:
    if not RUNTIME_DB.is_file():
        raise FileNotFoundError(f"runtime db missing: {RUNTIME_DB}")
    M149_WORKSPACE.mkdir(parents=True, exist_ok=True)
    connection = _connect(RUNTIME_DB)
    try:
        user = _ensure_runtime_user(connection, username=ACCEPTANCE_USER_USERNAME)
        agent_alias = _ensure_agent_alias(connection, agent_id=M149_AGENT_ID)
        node = connection.execute(
            "SELECT node_id, owner_id, status, agent_count FROM nodes WHERE node_id = ?",
            (NODE_ID,),
        ).fetchone()
        if node is None:
            raise RuntimeError(f"runtime node missing: {NODE_ID}")
        profile = connection.execute(
            "SELECT agent_id, owner_id, node_id, profile_version, display_name, description FROM agent_profiles WHERE agent_id = ?",
            (M149_AGENT_ID,),
        ).fetchone()
        if profile is None:
            raise RuntimeError(f"runtime agent missing: {M149_AGENT_ID}")
        old_conversation = _ensure_old_direct_conversation(
            connection,
            self_user_id=str(user["id"]),
            peer_user_id=str(agent_alias["id"]),
        )
        new_conversation = _create_new_direct_conversation(
            connection,
            self_user_id=str(user["id"]),
            peer_user_id=str(agent_alias["id"]),
        )
        connection.commit()
        history_row = _history_message_snapshot(
            connection,
            conversation_id=str(old_conversation["id"]),
            user_id=str(user["id"]),
        )
        frozen_agent_id, frozen_profile_version, frozen_system_prompt = (None, None, None)
        if history_row is not None:
            frozen_agent_id, frozen_profile_version, frozen_system_prompt = _extract_frozen_snapshot_from_payload(
                str(history_row["payload_json"])
            )
        return {
            "runtime_root": str(RUNTIME_ROOT),
            "runtime_db": str(RUNTIME_DB),
            "node": dict(node),
            "acceptance_user": dict(user),
            "agent_alias_user": dict(agent_alias),
            "agent_profile": dict(profile),
            "old_conversation": dict(old_conversation),
            "old_conversation_frozen_from_first_relay": {
                "agent_id": frozen_agent_id,
                "config_profile_version": frozen_profile_version,
                "config_system_prompt": frozen_system_prompt,
            },
            "new_conversation": dict(new_conversation),
            "workspace_root": str(M149_WORKSPACE),
            "next_steps": [
                "start IM with IM_DB_PATH pointed at the runtime db and port 8031",
                "start gateway with the staged node-config.yaml so agent-m149-1773456058 registers live on m104-acceptance-node",
                "open http://127.0.0.1:8031/chat and reuse the prepared old/new M149 direct conversations",
            ],
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage the live M149 acceptance runtime")
    parser.parse_args()
    print(json.dumps(stage_runtime(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
