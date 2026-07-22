"""SQLite repositories for IM users, conversations, and messages."""

import sqlite3
from uuid import uuid4

from IM.domain.models import (
    DeviceBindRequest,
)


from IM.infra._timestamps import utc_now


class BindRepository:
    """Persist and query device binding requests."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_bind_request(
        self, *, node_id: str, bind_base_url: str
    ) -> DeviceBindRequest:
        """Create a pending bind request and return its browser URL."""
        bind_id = uuid4().hex
        bind_token = uuid4().hex
        created_at = utc_now()
        bind_url = f"{bind_base_url.rstrip('/')}?token={bind_token}"
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO bind_requests(bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bind_id,
                    node_id,
                    None,
                    "pending",
                    bind_token,
                    bind_url,
                    created_at,
                    None,
                ),
            )
        request = self.get_bind_request(bind_id=bind_id)
        assert request is not None
        return request

    def get_bind_request(self, *, bind_id: str) -> DeviceBindRequest | None:
        """Return one bind request by id, or None when missing."""
        row = self._connection.execute(
            "SELECT bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at FROM bind_requests WHERE bind_id = ?",
            (bind_id,),
        ).fetchone()
        if row is None:
            return None
        return DeviceBindRequest(
            bind_id=row["bind_id"],
            node_id=row["node_id"],
            user_id=row["user_id"],
            status=row["status"],
            bind_token=row["bind_token"],
            bind_url=row["bind_url"],
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )

    def get_bind_request_by_token(self, *, bind_token: str) -> DeviceBindRequest | None:
        """Return one bind request by token, or None when missing."""
        row = self._connection.execute(
            "SELECT bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at FROM bind_requests WHERE bind_token = ?",
            (bind_token,),
        ).fetchone()
        if row is None:
            return None
        return DeviceBindRequest(
            bind_id=row["bind_id"],
            node_id=row["node_id"],
            user_id=row["user_id"],
            status=row["status"],
            bind_token=row["bind_token"],
            bind_url=row["bind_url"],
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )

    def confirm_bind_request(
        self, *, bind_id: str | None = None, bind_token: str | None = None, user_id: str
    ) -> DeviceBindRequest:
        """Mark one pending bind request as confirmed for a user."""
        resolved_bind_id = bind_id
        if resolved_bind_id is None:
            if bind_token is None:
                raise ValueError("bind_id not found")
            bind = self.get_bind_request_by_token(bind_token=bind_token)
            if bind is None:
                raise ValueError("bind_token not found")
            resolved_bind_id = bind.bind_id
        confirmed_at = utc_now()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE bind_requests
                SET user_id = ?, status = ?, confirmed_at = ?
                WHERE bind_id = ? AND status = 'pending'
                """,
                (user_id, "confirmed", confirmed_at, resolved_bind_id),
            )
        if cursor.rowcount == 0:
            existing = self.get_bind_request(bind_id=resolved_bind_id)
            if existing is None:
                raise ValueError("bind_id not found")
            raise ValueError("bind request already confirmed")
        request = self.get_bind_request(bind_id=resolved_bind_id)
        assert request is not None
        return request
