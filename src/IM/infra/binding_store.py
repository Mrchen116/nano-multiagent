"""Atomic SQLite transaction owner for device binding."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from IM.domain.models import DeviceBindRequest
from IM.infra.db import connect


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BindingStore:
    """Own the complete guard-and-write transaction for one bind confirmation."""

    def __init__(self, db_path: Path) -> None:
        """Bind confirmations to an independently opened SQLite database path.

        Args:
            db_path: Canonical IM SQLite database path shared by all workers.
        """
        self._db_path = db_path

    def confirm(
        self,
        *,
        bind_id: str | None = None,
        bind_token: str | None = None,
        user_id: str,
    ) -> DeviceBindRequest:
        """Confirm one request while serializing node ownership across processes.

        `BEGIN IMMEDIATE` is intentionally acquired before reading the current node
        owner. This makes the authorization guard and all ownership writes one
        operation even when two IM workers use independent SQLite connections.

        Args:
            bind_id: Stable request identifier, when confirming by id.
            bind_token: Browser confirmation token, when confirming by token.
            user_id: Authenticated IM user that is attempting the bind.

        Returns:
            The first durable confirmation, or the same snapshot for an idempotent
            retry by that user.

        Raises:
            ValueError: If a reference is missing, the request was claimed by a
                different user, or the node is already owned by another tenant.
        """
        with closing(connect(self._db_path)) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                user = connection.execute(
                    "SELECT id, owner_id, default_entry_node_id FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if user is None:
                    raise ValueError("user_id not found")
                bind = self._select_bind(
                    connection, bind_id=bind_id, bind_token=bind_token
                )
                node = connection.execute(
                    "SELECT owner_id FROM nodes WHERE node_id = ?", (bind["node_id"],)
                ).fetchone()
                if node is None:
                    raise ValueError("node_id not found")
                owner_id = str(user["owner_id"])
                current_owner = str(node["owner_id"] or "")
                if current_owner and current_owner != owner_id:
                    raise ValueError("node already bound to another owner")
                if bind["status"] == "confirmed":
                    if bind["user_id"] != user_id:
                        raise ValueError("bind request already confirmed")
                    connection.commit()
                    return self._to_domain(bind)

                confirmed_at = _utc_now()
                cursor = connection.execute(
                    """
                    UPDATE bind_requests
                    SET user_id = ?, status = 'confirmed', confirmed_at = ?
                    WHERE bind_id = ? AND status = 'pending'
                    """,
                    (user_id, confirmed_at, bind["bind_id"]),
                )
                if cursor.rowcount != 1:
                    raise ValueError("bind request already confirmed")
                connection.execute(
                    "UPDATE nodes SET owner_id = ? WHERE node_id = ?",
                    (owner_id, bind["node_id"]),
                )
                connection.execute(
                    "UPDATE agent_profiles SET owner_id = ? WHERE node_id = ?",
                    (owner_id, bind["node_id"]),
                )
                if not self._default_entry_is_owned(
                    connection,
                    owner_id=owner_id,
                    node_id=user["default_entry_node_id"],
                ):
                    connection.execute(
                        "UPDATE users SET default_entry_node_id = ? WHERE id = ?",
                        (bind["node_id"], user_id),
                    )
                confirmed = connection.execute(
                    "SELECT * FROM bind_requests WHERE bind_id = ?",
                    (bind["bind_id"],),
                ).fetchone()
                connection.commit()
                assert confirmed is not None
                return self._to_domain(confirmed)
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _select_bind(
        connection: sqlite3.Connection,
        *,
        bind_id: str | None,
        bind_token: str | None,
    ) -> sqlite3.Row:
        if bind_id is not None:
            bind = connection.execute(
                "SELECT * FROM bind_requests WHERE bind_id = ?", (bind_id,)
            ).fetchone()
            if bind is None:
                raise ValueError("bind_id not found")
            return bind
        bind = connection.execute(
            "SELECT * FROM bind_requests WHERE bind_token = ?", (bind_token or "",)
        ).fetchone()
        if bind is None:
            raise ValueError("bind_token not found")
        return bind

    @staticmethod
    def _default_entry_is_owned(
        connection: sqlite3.Connection, *, owner_id: str, node_id: object
    ) -> bool:
        if not isinstance(node_id, str) or not node_id:
            return False
        row = connection.execute(
            "SELECT owner_id FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return row is not None and str(row["owner_id"] or "") == owner_id

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> DeviceBindRequest:
        return DeviceBindRequest(
            bind_id=str(row["bind_id"]),
            node_id=str(row["node_id"]),
            user_id=str(row["user_id"]) if row["user_id"] is not None else None,
            status=str(row["status"]),
            bind_token=str(row["bind_token"]),
            bind_url=str(row["bind_url"]),
            created_at=str(row["created_at"]),
            confirmed_at=(
                str(row["confirmed_at"]) if row["confirmed_at"] is not None else None
            ),
        )
