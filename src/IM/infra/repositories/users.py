"""SQLite repositories for IM users, conversations, and messages."""

import sqlite3
from uuid import uuid4

from IM.domain.models import (
    User,
)


from IM.infra._timestamps import utc_now


class UserAlreadyExistsError(ValueError):
    """Raise when creating a user with a username that already exists."""


class RepositoryConstraintError(ValueError):
    """Raise when SQLite integrity constraints need API-safe translation."""


def _raise_constraint_error(error: sqlite3.IntegrityError) -> None:
    """Translate SQLite integrity failures into stable ValueError subclasses."""
    detail = str(error)
    if "users.username" in detail:
        raise UserAlreadyExistsError("username already exists") from error
    raise RepositoryConstraintError(detail) from error


class UserRepository:
    """Persist and query chat users."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    _USER_SELECT_COLUMNS = (
        "id, username, display_name, owner_id, default_entry_node_id, "
        "password_hash, locale, created_at"
    )

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        password_hash: str | None = None,
        locale: str = "en",
    ) -> User:
        """Create a user record.

        Args:
            username: Stable unique username for the user.
            display_name: Display name shown in conversation UI.
            password_hash: Optional bcrypt hash used by the auth flow; None for legacy fixtures.
            locale: Initial UI locale; defaults to ``en``.

        Returns:
            Created user entity.

        Raises:
            ValueError: When username or display_name is blank.
        """
        if not username.strip() or not display_name.strip():
            raise ValueError("username and display_name must be non-empty")

        user_id = uuid4().hex
        created_at = utc_now()
        owner_id = user_id
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO users(id, username, display_name, owner_id, default_entry_node_id, password_hash, locale, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        display_name,
                        owner_id,
                        None,
                        password_hash,
                        locale,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            _raise_constraint_error(error)
        return User(
            id=user_id,
            username=username,
            display_name=display_name,
            owner_id=owner_id,
            owned_node_ids=[],
            default_entry_node_id=None,
            created_at=created_at,
            password_hash=password_hash,
            locale=locale,
        )

    def list_users(self) -> list[User]:
        """List users in creation order.

        Returns:
            Users ordered by creation timestamp and insertion order.
        """
        rows = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users ORDER BY created_at, rowid"
        ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, *, user_id: str) -> User | None:
        """Return one user with owned node ids, or None when missing."""
        row = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_user_by_username(self, *, username: str) -> User | None:
        """Return one user by username (auth login lookup)."""
        row = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def update_user(
        self,
        *,
        user_id: str,
        display_name: str,
        default_entry_node_id: str | None,
        locale: str | None = None,
    ) -> User:
        """Update mutable user settings and return the latest snapshot."""
        if not display_name.strip():
            raise ValueError("display_name must be non-empty")
        user = self.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        next_default_entry_node_id = default_entry_node_id
        if next_default_entry_node_id is not None:
            next_default_entry_node_id = next_default_entry_node_id.strip() or None
            if (
                next_default_entry_node_id
                and next_default_entry_node_id not in user.owned_node_ids
            ):
                raise ValueError("default_entry_node_id not owned by user")
        next_locale = user.locale if locale is None else locale.strip() or user.locale
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE users SET display_name = ?, default_entry_node_id = ?, locale = ? WHERE id = ?",
                (display_name, next_default_entry_node_id, next_locale, user_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("user_id not found")
        user = self.get_user(user_id=user_id)
        assert user is not None
        return user

    def ensure_default_entry_node(self, *, user_id: str, node_id: str) -> User:
        """Set a user's default entry node when it is missing or no longer owned."""
        user = self.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        if user.default_entry_node_id in user.owned_node_ids:
            return user
        with self._connection:
            self._connection.execute(
                "UPDATE users SET default_entry_node_id = ? WHERE id = ?",
                (node_id, user_id),
            )
        updated = self.get_user(user_id=user_id)
        assert updated is not None
        return updated

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert one user row to a domain user including owned nodes."""
        node_rows = self._connection.execute(
            "SELECT node_id FROM nodes WHERE owner_id = ? ORDER BY rowid",
            (row["owner_id"],),
        ).fetchall()
        owned_node_ids = [item["node_id"] for item in node_rows]
        default_entry_node_id = row["default_entry_node_id"]
        if default_entry_node_id not in owned_node_ids:
            default_entry_node_id = owned_node_ids[0] if owned_node_ids else None
        row_keys = row.keys() if hasattr(row, "keys") else []
        password_hash = row["password_hash"] if "password_hash" in row_keys else None
        locale = row["locale"] if "locale" in row_keys and row["locale"] else "en"
        return User(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            owner_id=row["owner_id"],
            owned_node_ids=owned_node_ids,
            default_entry_node_id=default_entry_node_id,
            created_at=row["created_at"],
            password_hash=password_hash,
            locale=locale,
        )
