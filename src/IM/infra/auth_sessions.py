"""Atomic persistent session rotation and one-use browser tickets."""

import hashlib
import secrets
import sqlite3
import time
from threading import RLock


def token_digest(value: str) -> str:
    """Hash a random bearer value before it reaches durable storage."""
    return hashlib.sha256(value.encode()).hexdigest()


class AuthSessions:
    """Keep session revocation across restarts and consume credentials atomically."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def create(
        self, *, user_id: str, epoch: int, refresh_jti: str, expires_at: int
    ) -> str:
        """Create a session bound to the current human identity epoch."""
        session_id = secrets.token_urlsafe(24)
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM auth_sessions WHERE session_id IN (SELECT session_id FROM auth_sessions WHERE expires_at <= ? LIMIT 100)",
                (int(time.time()),),
            )
            self.connection.execute(
                "INSERT INTO auth_sessions(session_id,user_id,epoch,refresh_hash,expires_at) VALUES(?,?,?,?,?)",
                (session_id, user_id, epoch, token_digest(refresh_jti), expires_at),
            )
        return session_id

    def valid(
        self, session_id: str, *, user_id: str | None = None, epoch: int | None = None
    ) -> sqlite3.Row | None:
        """Read a nonrevoked session whose user epoch still matches."""
        row = self.connection.execute(
            """SELECT s.* FROM auth_sessions s JOIN users u ON u.id=s.user_id
               WHERE s.session_id=? AND s.revoked=0 AND s.expires_at>?
                 AND s.epoch=u.auth_epoch AND u.password_hash IS NOT NULL""",
            (session_id, int(time.time())),
        ).fetchone()
        if (
            row is None
            or (user_id is not None and row["user_id"] != user_id)
            or (epoch is not None and row["epoch"] != epoch)
        ):
            return None
        return row

    def rotate(
        self, *, session_id: str, old_jti: str, new_jti: str, expires_at: int
    ) -> bool:
        """Consume one refresh JTI with a single compare-and-swap write."""
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """UPDATE auth_sessions SET refresh_hash=?, expires_at=?
                   WHERE session_id=? AND refresh_hash=? AND revoked=0 AND expires_at>?
                     AND epoch=(SELECT auth_epoch FROM users WHERE id=auth_sessions.user_id)""",
                (
                    token_digest(new_jti),
                    expires_at,
                    session_id,
                    token_digest(old_jti),
                    int(time.time()),
                ),
            )
        return cursor.rowcount == 1

    def revoke(self, session_id: str) -> None:
        """Revoke both access and refresh use of one session."""
        with self._lock, self.connection:
            self.connection.execute(
                "UPDATE auth_sessions SET revoked=1 WHERE session_id=?", (session_id,)
            )
            self.connection.execute(
                "DELETE FROM auth_ws_tickets WHERE session_id=?", (session_id,)
            )

    def issue_ticket(self, session_id: str) -> str:
        """Issue a thirty-second ticket for an active company's browser session."""
        ticket = secrets.token_urlsafe(32)
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM auth_ws_tickets WHERE expires_at<=?", (int(time.time()),)
            )
            cursor = self.connection.execute(
                """INSERT INTO auth_ws_tickets(ticket_hash,session_id,expires_at)
                   SELECT ?,s.session_id,? FROM auth_sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.session_id=? AND s.revoked=0 AND s.epoch=u.auth_epoch
                     AND s.expires_at>? AND u.membership_status='active'""",
                (
                    token_digest(ticket),
                    int(time.time()) + 30,
                    session_id,
                    int(time.time()),
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("inactive session")
        return ticket

    def consume_ticket(self, ticket: str) -> sqlite3.Row | None:
        """Delete and return a usable ticket once, including concurrent handshakes."""
        with self._lock, self.connection:
            row = self.connection.execute(
                "DELETE FROM auth_ws_tickets WHERE ticket_hash=? AND expires_at>? RETURNING session_id",
                (token_digest(ticket), int(time.time())),
            ).fetchone()
        return self.valid(row["session_id"]) if row is not None else None
