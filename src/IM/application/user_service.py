"""Application service for IM user management."""

from IM.domain.models import User
from IM.infra.repositories import UserRepository


class UserService:
    """Coordinate user workflows for IM APIs."""

    def __init__(self, *, users: UserRepository) -> None:
        """Bind service to the user repository.

        Args:
            users: Repository for user reads and writes.
        """
        self._users = users

    def create_user(self, *, username: str, display_name: str) -> User:
        """Create one IM user."""
        return self._users.create_user(username=username, display_name=display_name)

    def list_users(self) -> list[User]:
        """List all IM users in storage order."""
        return self._users.list_users()
