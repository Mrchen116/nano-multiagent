"""Application service for IM agent configuration APIs."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from IM.domain.models import AgentProfile, is_managed_workspace_root, managed_workspace_root
from IM.infra.repositories import AgentProfileRepository, NodeRepository

ConfigSyncNotifier = Callable[[str, str, int], object]


class ConfigService:
    """Coordinate agent profile reads, creation, and optimistic-lock updates."""

    def __init__(
        self,
        *,
        profiles: AgentProfileRepository,
        nodes: NodeRepository | None = None,
        config_sync_notifier: ConfigSyncNotifier | None = None,
    ) -> None:
        """Bind service to the agent profile and optional node repositories."""
        self._profiles = profiles
        self._nodes = nodes
        self._config_sync_notifier = config_sync_notifier

    def create_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        node_id: str,
        display_name: str,
        description: str,
        system_prompt: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        workspace_root: str,
    ) -> AgentProfile:
        """Create one agent profile under exactly one known node."""
        existing = self._profiles.get_profile(agent_id=agent_id)
        if existing is not None and existing.owner_id.strip():
            raise ValueError("agent_id already exists")
        if self._nodes is None:
            raise LookupError("node_id not found")
        node = self._nodes.get_node(node_id=node_id)
        if node is None:
            raise LookupError("node_id not found")
        normalized_owner_id = owner_id.strip()
        if node.owner_id.strip() and normalized_owner_id and node.owner_id != normalized_owner_id:
            raise ValueError("node_id owned by another owner")
        if not node.owner_id.strip() and normalized_owner_id:
            self._nodes.assign_owner(node_id=node_id, owner_id=normalized_owner_id)
        created = self._profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner_id,
            node_id=node_id,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            workspace_root=self.normalize_workspace_root(agent_id=agent_id, workspace_root=workspace_root),
        )
        self._notify_config_sync(agent_id=agent_id, profile_version=created.profile_version)
        return created

    def list_profiles(self) -> list[AgentProfile]:
        """List all agent profiles in storage order."""
        return self._profiles.list_profiles()

    def list_runtime_selectable_profiles(self) -> list[AgentProfile]:
        """List agent profiles that are selectable in the current runtime."""
        return self._profiles.list_runtime_selectable_profiles()

    def list_runtime_selectable_profiles_for_owner(self, *, owner_id: str) -> list[AgentProfile]:
        """Owner-scoped variant used by IM routes after multi-user auth (feat-340-M1)."""
        return self._profiles.list_runtime_selectable_profiles_for_owner(owner_id=owner_id)

    def get_updated_at(self, *, agent_id: str) -> str | None:
        """Return the last update timestamp for one agent."""
        return self._profiles.get_updated_at(agent_id=agent_id)

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when missing."""
        return self._profiles.get_profile(agent_id=agent_id)

    def get_profile_for_owner(self, *, agent_id: str, owner_id: str) -> AgentProfile | None:
        """Return one agent profile when it belongs to ``owner_id`` or is ownerless."""
        return self._profiles.get_profile_for_owner(agent_id=agent_id, owner_id=owner_id)

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
        workspace_root: str | None,
    ) -> AgentProfile:
        """Update one agent profile using profile_version optimistic locking."""
        if self._profiles.get_profile(agent_id=agent_id) is None:
            raise LookupError("agent_id not found")
        updated = self._profiles.update_profile(
            agent_id=agent_id,
            profile_version=profile_version,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            workspace_root=self.normalize_workspace_root(agent_id=agent_id, workspace_root=workspace_root),
        )
        self._notify_config_sync(agent_id=agent_id, profile_version=updated.profile_version)
        return updated

    def workspace_root_for_profile(self, profile: AgentProfile) -> str:
        """Return the effective workspace root used by runtime sync and UI."""
        if profile.workspace_root:
            return str(Path(profile.workspace_root).expanduser().resolve())
        return managed_workspace_root(profile.agent_id)

    def workspace_is_default_for_profile(self, profile: AgentProfile) -> bool:
        """Return whether one profile is still using the managed default workspace."""
        return is_managed_workspace_root(agent_id=profile.agent_id, workspace_root=profile.workspace_root)

    @staticmethod
    def normalize_workspace_root(*, agent_id: str, workspace_root: str | None) -> str:
        """Normalize one workspace value for storage.

        Blank values mean "use managed default" and are persisted as the canonical
        managed workspace path so later runtime/session refreshes can trust storage.
        Non-blank values must be absolute after ``expanduser()``.
        """
        if workspace_root is None:
            return managed_workspace_root(agent_id)
        normalized = workspace_root.strip()
        if not normalized:
            return managed_workspace_root(agent_id)
        path = Path(normalized).expanduser()
        if not path.is_absolute():
            raise ValueError("workspace_root must be an absolute path or start with ~/")
        return str(path.resolve())

    def _notify_config_sync(self, *, agent_id: str, profile_version: int) -> None:
        notifier = self._config_sync_notifier
        if notifier is None:
            return
        profile = self.get_profile(agent_id=agent_id)
        if profile is None or profile.node_id is None or not profile.node_id.strip():
            return
        result = notifier(profile.node_id, agent_id, profile_version)
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(result)
            else:
                loop.create_task(result)
