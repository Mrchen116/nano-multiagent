"""Application service for IM agent configuration APIs."""

from IM.domain.models import AgentProfile
from IM.infra.repositories import AgentProfileRepository


class ConfigService:
    """Coordinate agent profile reads and optimistic-lock updates."""

    def __init__(self, *, profiles: AgentProfileRepository) -> None:
        """Bind service to the agent profile repository."""
        self._profiles = profiles

    def list_profiles(self) -> list[AgentProfile]:
        """List all agent profiles in storage order."""
        return self._profiles.list_profiles()

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
