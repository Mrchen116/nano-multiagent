"""Application service for IM agent configuration APIs."""

from IM.domain.models import AgentProfile
from IM.infra.repositories import AgentProfileRepository, NodeRepository


class ConfigService:
    """Coordinate agent profile reads, creation, and optimistic-lock updates."""

    def __init__(self, *, profiles: AgentProfileRepository, nodes: NodeRepository | None = None) -> None:
        """Bind service to the agent profile and optional node repositories."""
        self._profiles = profiles
        self._nodes = nodes

    def create_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        display_name: str,
        description: str,
        system_prompt: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        node_id: str | None,
    ) -> AgentProfile:
        """Create one agent profile and optionally bind it to a known node."""
        if self._profiles.get_profile(agent_id=agent_id) is not None:
            raise ValueError("agent_id already exists")
        if node_id is not None:
            if self._nodes is None or self._nodes.get_node(node_id=node_id) is None:
                raise LookupError("node_id not found")
        created = self._profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner_id,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
        )
        if node_id is not None:
            self._profiles._connection.execute(
                "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
                (node_id, agent_id),
            )
            self._profiles._connection.commit()
            rebound = self._profiles.get_profile(agent_id=agent_id)
            assert rebound is not None
            return rebound
        return created

    def list_profiles(self) -> list[AgentProfile]:
        """List all agent profiles in storage order."""
        return self._profiles.list_profiles()

    def list_bound_nodes(self, *, agent_id: str) -> list[str]:
        """Return the bound node ids for one agent."""
        return self._profiles.list_bound_nodes(agent_id=agent_id)

    def get_updated_at(self, *, agent_id: str) -> str | None:
        """Return the last update timestamp for one agent."""
        return self._profiles.get_updated_at(agent_id=agent_id)

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when missing."""
        return self._profiles.get_profile(agent_id=agent_id)

    def update_profile(
        self,
        *,
        agent_id: str,
        profile_version: int,
        display_name: str,
        description: str,
        system_prompt: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
    ) -> AgentProfile:
        """Update one agent profile using profile_version optimistic locking."""
        return self._profiles.update_profile(
            agent_id=agent_id,
            profile_version=profile_version,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
        )
