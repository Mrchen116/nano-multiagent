"""Application service for IM agent configuration APIs."""

import asyncio
from collections.abc import Callable

from IM.domain.models import (
    AgentProfile,
    User,
)
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository

ConfigSyncNotifier = Callable[[str, str, int], object]


def agent_user_username(agent_id: str) -> str:
    """Canonical IM ``users.username`` derived from one ``agent_id``.

    feat-340-M18 R9-1: every agent profile must own a matching IM users row so
    that ``POST /im/v1/conversations { participant_ids: [agent.user_id] }`` is
    accepted. This single function is the contract surface for that username;
    services and routes both call it to avoid drift.
    """
    return f"agent:{agent_id}"


class ConfigService:
    """Coordinate agent profile reads, creation, and optimistic-lock updates."""

    def __init__(
        self,
        *,
        profiles: AgentProfileRepository,
        nodes: NodeRepository | None = None,
        users: UserRepository | None = None,
        config_sync_notifier: ConfigSyncNotifier | None = None,
    ) -> None:
        """Bind service to the agent profile and optional node repositories.

        ``users`` is required to provision the IM ``users`` row on agent
        registration (feat-340-M18 R9-1). It is optional only for legacy
        test harnesses that instantiate the service without HTTP wiring.
        """
        self._profiles = profiles
        self._nodes = nodes
        self._users = users
        self._config_sync_notifier = config_sync_notifier

    def ensure_agent_user(
        self,
        *,
        agent_id: str,
        display_name: str,
    ) -> User | None:
        """Return the IM user row backing one agent, lazily creating it if missing.

        feat-340-M18 R9-1: closes the legacy gap where pre-M18 agent profiles
        and any agent profile created outside the HTTP route lacked the matching
        ``users`` row. Without it, ``POST /im/v1/conversations`` rejects the
        agent participant id and the user-visible chat flow breaks. Lazy
        provisioning lets list/read paths self-heal without a backfill job.
        Returns ``None`` only when no ``UserRepository`` was wired (legacy
        constructor variant used by some unit tests).
        """
        if self._users is None:
            return None
        username = agent_user_username(agent_id)
        existing = self._users.get_user_by_username(username=username)
        if existing is not None:
            return existing
        return self._users.create_user(username=username, display_name=display_name)

    def create_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        node_id: str,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        workspace_root: str | None,
        reasoning_effort: str | None = None,
        workspace_is_default: bool | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        skills_selection_mode: str | None = None,
        notify_config_sync: bool = True,
        model_fallbacks: list[str] | None = None,
    ) -> AgentProfile:
        """Create one agent profile under exactly one known node."""
        existing = self._profiles.get_profile(agent_id=agent_id)
        if existing is not None:
            raise ValueError("agent_id already exists")
        if self._nodes is None:
            raise LookupError("node_id not found")
        node = self._nodes.get_node(node_id=node_id)
        if node is None:
            raise LookupError("node_id not found")
        normalized_owner_id = owner_id.strip()
        if (
            node.owner_id.strip()
            and normalized_owner_id
            and node.owner_id != normalized_owner_id
        ):
            raise ValueError("node_id owned by another owner")
        if not node.owner_id.strip() and normalized_owner_id:
            self._nodes.assign_owner(node_id=node_id, owner_id=normalized_owner_id)
        created = self._profiles.create_profile(
            agent_id=agent_id,
            owner_id=normalized_owner_id,
            node_id=node_id,
            display_name=display_name,
            description=description,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            workspace_root=self.normalize_workspace_root(
                agent_id=agent_id, workspace_root=workspace_root
            ),
            workspace_is_default=workspace_is_default,
            features=features,
            custom_prompt=custom_prompt,
            skills_selection_mode=skills_selection_mode,
            model_fallbacks=model_fallbacks,
        )
        # feat-340-M18 R9-1: pair every newly-created agent with an IM users row so the
        # subsequent `POST /im/v1/conversations { participant_ids: [user_id] }` flow
        # used by the chat UI can resolve the agent participant. Without this, the
        # end-user cannot start a direct chat with a freshly-minted agent.
        self.ensure_agent_user(agent_id=agent_id, display_name=created.display_name)
        if notify_config_sync:
            self._notify_config_sync(
                agent_id=agent_id, profile_version=created.profile_version
            )
        return created

    def claim_registration_seed_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        expected_owner_id: str,
        node_id: str,
        expected_workspace_root: str,
        expected_workspace_is_default: bool,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        reasoning_effort: str | None,
        features: dict[str, bool],
        custom_prompt: str | None,
        skills_selection_mode: str | None = None,
        model_fallbacks: list[str] | None = None,
    ) -> AgentProfile:
        """Claim the exact Gateway registration seed for an active create operation."""
        if self._nodes is None:
            raise LookupError("node_id not found")
        node = self._nodes.get_node(node_id=node_id)
        if node is None:
            raise LookupError("node_id not found")
        normalized_owner_id = owner_id.strip()
        if node.owner_id.strip() and node.owner_id != normalized_owner_id:
            raise ValueError("node_id owned by another owner")
        claimed = self._profiles.claim_registration_seed_profile(
            agent_id=agent_id,
            owner_id=normalized_owner_id,
            expected_owner_id=expected_owner_id,
            node_id=node_id,
            expected_workspace_root=expected_workspace_root,
            expected_workspace_is_default=expected_workspace_is_default,
            display_name=display_name,
            description=description,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features=features,
            custom_prompt=custom_prompt,
            skills_selection_mode=skills_selection_mode,
            model_fallbacks=model_fallbacks,
        )
        if claimed is None:
            raise ValueError("agent_id already exists")
        if not node.owner_id.strip() and normalized_owner_id:
            self._nodes.assign_owner(node_id=node_id, owner_id=normalized_owner_id)
        self.ensure_agent_user(agent_id=agent_id, display_name=claimed.display_name)
        self._notify_config_sync(
            agent_id=agent_id, profile_version=claimed.profile_version
        )
        return claimed

    def is_registration_seed(
        self, *, agent_id: str, owner_id: str, node_id: str
    ) -> bool:
        """Return whether an advertised profile is still eligible for recovery."""
        return self._profiles.is_registration_seed(
            agent_id=agent_id, owner_id=owner_id, node_id=node_id
        )

    def claim_pending_create_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        expected_owner_id: str,
        node_id: str,
        expected_workspace_root: str,
        expected_workspace_is_default: bool,
        operation_id: str,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        reasoning_effort: str | None,
        features: dict[str, bool],
        custom_prompt: str | None,
        skills_selection_mode: str | None = None,
        model_fallbacks: list[str] | None = None,
    ) -> AgentProfile:
        """Claim a matching Gateway create operation after a lost response.

        The caller holds the app-scoped create lock.  This method accepts only the
        durable root/provenance pair and operation reservation, so it cannot turn a
        retried request into an overwrite of another Agent's workspace binding.
        """
        if self._nodes is None:
            raise LookupError("node_id not found")
        node = self._nodes.get_node(node_id=node_id)
        if node is None:
            raise LookupError("node_id not found")
        normalized_owner_id = owner_id.strip()
        if (
            node.owner_id.strip()
            and normalized_owner_id
            and node.owner_id != normalized_owner_id
        ):
            raise ValueError("node_id owned by another owner")
        claimed = self._profiles.claim_pending_create_profile(
            agent_id=agent_id,
            owner_id=normalized_owner_id,
            expected_owner_id=expected_owner_id,
            node_id=node_id,
            expected_workspace_root=expected_workspace_root,
            expected_workspace_is_default=expected_workspace_is_default,
            operation_id=operation_id,
            display_name=display_name,
            description=description,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features=features,
            custom_prompt=custom_prompt,
            skills_selection_mode=skills_selection_mode,
            model_fallbacks=model_fallbacks,
        )
        if claimed is None:
            raise ValueError("agent_id already exists")
        if not node.owner_id.strip() and normalized_owner_id:
            self._nodes.assign_owner(node_id=node_id, owner_id=normalized_owner_id)
        if self._users is not None:
            agent_user = self.ensure_agent_user(
                agent_id=agent_id, display_name=claimed.display_name
            )
            if (
                agent_user is not None
                and agent_user.display_name != claimed.display_name
            ):
                self._users.update_user(
                    user_id=agent_user.id,
                    display_name=claimed.display_name,
                    default_entry_node_id=agent_user.default_entry_node_id,
                )
        self._notify_config_sync(
            agent_id=agent_id, profile_version=claimed.profile_version
        )
        return claimed

    def reserve_create_operation(
        self,
        *,
        owner_id: str,
        node_id: str,
        agent_id: str,
        request_fingerprint: str,
    ) -> str:
        """Reserve the IM-side half of one recoverable Gateway create operation."""
        return self._profiles.reserve_create_operation(
            owner_id=owner_id,
            node_id=node_id,
            agent_id=agent_id,
            request_fingerprint=request_fingerprint,
        )

    def existing_create_operation(
        self,
        *,
        owner_id: str,
        node_id: str,
        agent_id: str,
        request_fingerprint: str,
    ) -> str | None:
        """Find an exact pre-existing create operation without reserving a new one."""
        return self._profiles.existing_create_operation(
            owner_id=owner_id,
            node_id=node_id,
            agent_id=agent_id,
            request_fingerprint=request_fingerprint,
        )

    def is_pending_create_operation(
        self,
        *,
        agent_id: str,
        profile_owner_id: str,
        owner_id: str,
        node_id: str,
        operation_id: str,
    ) -> bool:
        """Return whether a profile is the exact abandoned-response create result."""
        return self._profiles.is_pending_create_operation(
            agent_id=agent_id,
            profile_owner_id=profile_owner_id,
            owner_id=owner_id,
            node_id=node_id,
            operation_id=operation_id,
        )

    def abandon_create_operation(self, *, operation_id: str) -> None:
        """Drop a reservation after Gateway rejected creation without side effects."""
        self._profiles.abandon_create_operation(operation_id=operation_id)

    def complete_create_operation(self, *, operation_id: str) -> None:
        """Retire the reservation once a normal create profile is durable."""
        self._profiles.complete_create_operation(operation_id=operation_id)

    def list_profiles(self) -> list[AgentProfile]:
        """List all agent profiles in storage order."""
        return self._profiles.list_profiles()

    def list_runtime_selectable_profiles(self) -> list[AgentProfile]:
        """List agent profiles that are selectable in the current runtime."""
        return self._profiles.list_runtime_selectable_profiles()

    def list_runtime_selectable_profiles_for_owner(
        self, *, owner_id: str
    ) -> list[AgentProfile]:
        """Owner-scoped variant used by IM routes after multi-user auth (feat-340-M1)."""
        return self._profiles.list_runtime_selectable_profiles_for_owner(
            owner_id=owner_id
        )

    def get_updated_at(self, *, agent_id: str) -> str | None:
        """Return the last update timestamp for one agent."""
        return self._profiles.get_updated_at(agent_id=agent_id)

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when missing."""
        return self._profiles.get_profile(agent_id=agent_id)

    def get_profile_for_owner(
        self, *, agent_id: str, owner_id: str
    ) -> AgentProfile | None:
        """Return one agent profile when it belongs to ``owner_id`` or is ownerless."""
        return self._profiles.get_profile_for_owner(
            agent_id=agent_id, owner_id=owner_id
        )

    def update_profile(
        self,
        *,
        agent_id: str,
        profile_version: int,
        display_name: str,
        description: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
        reasoning_effort: str | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        heartbeat_json: str | None = None,
        skills_selection_mode: str | None = None,
        notify_config_sync: bool = True,
        model_fallbacks: list[str] | None = None,
    ) -> AgentProfile:
        """Update one agent profile using profile_version optimistic locking.

        workspace_root is intentionally absent — it is set at creation and is
        immutable thereafter (bugfix-404-M2 decision 5).  The HTTP layer already
        excludes it via UpdateAgentConfigRequest (extra="ignore"), so removing
        the parameter here closes the service-level gap that previously caused
        normalize_workspace_root(None) to silently replace a custom path during
        every UI config edit.

        feat-379-M5 (ISSUE-2): features + custom_prompt are now accepted so
        the IM mirror stores them and subsequent GET /config calls return the
        persisted values; Gateway picks them up on next config.sync.

        feat-394: heartbeat_json stores the heartbeat cadence as a raw JSON string
        so the gateway ConfigSyncNotifier can forward it without re-serialization.
        feat-394 M9-E: cron_json removed — cron enable lives in features["cron_scheduling"].
        """
        if self._profiles.get_profile(agent_id=agent_id) is None:
            raise LookupError("agent_id not found")
        updated = self._profiles.update_profile(
            agent_id=agent_id,
            profile_version=profile_version,
            display_name=display_name,
            description=description,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features=features,
            custom_prompt=custom_prompt,
            heartbeat_json=heartbeat_json,
            skills_selection_mode=skills_selection_mode,
            model_fallbacks=model_fallbacks,
        )
        if notify_config_sync:
            self._notify_config_sync(
                agent_id=agent_id, profile_version=updated.profile_version
            )
        return updated

    def workspace_root_for_profile(self, profile: AgentProfile) -> str | None:
        """Return the node-reported workspace root, or ``None`` while unknown."""
        if profile.workspace_root and profile.workspace_root.strip():
            return profile.workspace_root
        return None

    def workspace_is_default_for_profile(self, profile: AgentProfile) -> bool | None:
        """Return Gateway-reported workspace provenance, or ``None`` while unknown."""
        return profile.workspace_is_default

    @staticmethod
    def normalize_workspace_root(
        *, agent_id: str, workspace_root: str | None
    ) -> str | None:
        """Keep a node-reported root opaque and preserve a missing declaration.

        IM cannot expand a target Gateway's home directory or verify its filesystem.
        ``agent_id`` remains part of this method's stable call shape, but never
        determines a path here.
        """
        del agent_id
        if workspace_root is None or not workspace_root.strip():
            return None
        return workspace_root

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
