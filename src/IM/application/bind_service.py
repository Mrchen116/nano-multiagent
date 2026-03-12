"""Application service for IM account and device binding APIs."""

from IM.domain.models import DeviceBindRequest, User
from IM.infra.repositories import AgentProfileRepository, BindRepository, NodeRepository, UserRepository


class BindService:
    """Coordinate current-user settings and device bind workflows."""

    def __init__(
        self,
        *,
        users: UserRepository,
        nodes: NodeRepository,
        binds: BindRepository,
        profiles: AgentProfileRepository,
        bind_base_url: str,
    ) -> None:
        """Bind service to repositories used by account and bind routes."""
        self._users = users
        self._nodes = nodes
        self._binds = binds
        self._profiles = profiles
        self._bind_base_url = bind_base_url

    def get_me(self, *, user_id: str) -> User | None:
        """Return the current user snapshot for account APIs."""
        return self._users.get_user(user_id=user_id)

    def update_me(self, *, user_id: str, display_name: str) -> User:
        """Update mutable current-user settings."""
        return self._users.update_user(user_id=user_id, display_name=display_name)

    def start_bind(self, *, node_id: str) -> DeviceBindRequest:
        """Create one pending bind request and browser URL for a node."""
        if self._nodes.get_node(node_id=node_id) is None:
            raise ValueError("node_id not found")
        return self._binds.create_bind_request(node_id=node_id, bind_base_url=self._bind_base_url)

    def confirm_bind(self, *, bind_id: str | None = None, bind_token: str | None = None, user_id: str) -> DeviceBindRequest:
        """Confirm a pending bind request and reassign node-local agents."""
        user = self._users.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        bind = self._binds.confirm_bind_request(bind_id=bind_id, bind_token=bind_token, user_id=user_id)
        self._nodes.assign_owner(node_id=bind.node_id, owner_id=user.owner_id)
        self._profiles.reassign_owner_by_node(node_id=bind.node_id, owner_id=user.owner_id)
        return bind
