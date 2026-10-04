"""Persistent expiring counters for authentication abuse, with bounded cleanup."""

import hashlib
import sqlite3
import time
from threading import RLock


class RateLimited(ValueError):
    """The caller may retry after the remaining fixed-window interval."""

    def __init__(self, retry_after: int):
        super().__init__("temporarily rate limited")
        self.retry_after = max(1, retry_after)


class AuthLimits:
    """Keep source and account attempts across server restarts."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._lock = RLock()

    def check(self, key: str, *, limit: int, window: int, consume: bool = True) -> None:
        """Reject a full window; optionally count this attempt atomically."""
        key = hashlib.sha256(key.encode()).hexdigest()
        now = int(time.time())
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM auth_rate_limits WHERE bucket IN (SELECT bucket FROM auth_rate_limits WHERE expires_at<=? LIMIT 100)",
                (now,),
            )
            row = self.connection.execute(
                "SELECT count,expires_at FROM auth_rate_limits WHERE bucket=?", (key,)
            ).fetchone()
            if row is not None and row["count"] >= limit and row["expires_at"] > now:
                raise RateLimited(row["expires_at"] - now)
            if consume:
                self.connection.execute(
                    """INSERT INTO auth_rate_limits(bucket,count,expires_at) VALUES(?,1,?)
                       ON CONFLICT(bucket) DO UPDATE SET count=CASE WHEN expires_at<=? THEN 1 ELSE count+1 END,
                       expires_at=CASE WHEN expires_at<=? THEN excluded.expires_at ELSE expires_at END""",
                    (key, now + window, now, now),
                )

    def clear(self, key: str) -> None:
        """Clear a successful source/account pair without resetting other budgets."""
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM auth_rate_limits WHERE bucket=?",
                (hashlib.sha256(key.encode()).hexdigest(),),
            )
