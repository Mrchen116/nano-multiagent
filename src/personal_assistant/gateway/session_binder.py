"""Own Gateway session resolution, persistence, and revision-safe writeback."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any, Literal, Protocol

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.agent_catalog import (
    LiveAgentCatalog,
    LiveAgentSnapshot,
)
from personal_assistant.gateway.session_keys import (
    SessionBinding,
    build_conversation_reply_context,
    build_conversation_session_key,
)
from personal_assistant.product import prompt_for, resolve_enabled_tools


class _SessionBindingRepository(Protocol):
    """Describe the private storage operations required by the binder."""

    def get(self, session_key: str) -> SessionBinding | None: ...

    def bind(
        self,
        *,
        session_key: str,
        kernel_session_id: str,
        reply_context: ReplyContext,
    ) -> SessionBinding: ...

    def drop(self, session_key: str) -> None: ...

    def bindings_for_agent(self, agent_id: str) -> tuple[SessionBinding, ...]: ...

    def find_by_kernel_session_id(
        self, kernel_session_id: str
    ) -> SessionBinding | None: ...

    def find_direct_by_agent(
        self, *, channel_name: str, agent_id: str
    ) -> SessionBinding | None: ...


@dataclass(frozen=True, slots=True)
class SessionBindingRequest:
    """Describe one inbound session resolution operation.

    Args:
        session_key: Stable Gateway session key selected by routing.
        reply_context: Current reply target to refresh on successful reuse.
        message: Inbound message supplying immutable routing metadata.
        gateway_internal_port: Internal dispatch port injected into session metadata.
    """

    session_key: str
    reply_context: ReplyContext
    message: InboundMessage
    gateway_internal_port: int


@dataclass(frozen=True, slots=True)
class BindingWriteGuard:
    """Capture one catalog revision and binder invalidation generation."""

    agent_id: str
    revision: int
    generation: int


@dataclass(frozen=True, slots=True)
class ConversationBindingRequest:
    """Describe a semantic conversation binding completed after an external await."""

    channel_name: str
    conversation_id: str
    agent_id: str
    kernel_session_id: str
    guard: BindingWriteGuard


@dataclass(frozen=True, slots=True)
class ConversationBindResult:
    """Report whether a semantic binding was persisted or rejected as stale."""

    status: Literal["bound", "stale"]
    binding: SessionBinding | None


@dataclass(frozen=True, slots=True)
class SessionProvenance:
    """Capture the Agent snapshot and write guard that created a Kernel session."""

    kernel_session_id: str
    agent: LiveAgentSnapshot
    guard: BindingWriteGuard


@dataclass(frozen=True, slots=True)
class BindingProvenance:
    """Capture one binding and its Agent revision in a single binder transaction."""

    binding: SessionBinding
    agent: LiveAgentSnapshot
    guard: BindingWriteGuard


class GatewaySessionBinder:
    """Own Gateway channel-to-Kernel session binding business rules.

    Args:
        catalog: Single live Agent snapshot owner.
        repository: SQLite production or in-memory test storage adapter.
        kernel: In-process ``agent.sdk`` Kernel.

    Notes:
        Repository rows retain the existing schema. Catalog revision and invalidation
        generation are process-local guards that prevent a pre-update await from
        publishing stale session ownership after a new Agent config is visible.
    """

    def __init__(
        self,
        *,
        catalog: LiveAgentCatalog,
        repository: _SessionBindingRepository,
        kernel: Any,
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._kernel = kernel
        self._lock = Lock()
        self._binding_revisions: dict[str, int] = {}
        self._binding_agents: dict[str, LiveAgentSnapshot] = {}
        self._session_agents: dict[str, LiveAgentSnapshot] = {}
        self._generations: dict[str, int] = {}
        self._startup_revisions = {
            snapshot.agent_id: snapshot.revision
            for snapshot in catalog.values_snapshot()
        }

    async def resolve(
        self,
        request: SessionBindingRequest,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Reuse or create the binding for one captured Agent snapshot.

        Args:
            request: Routed session key, reply target, and message facts.
            agent: Snapshot captured at the inbound operation's linearization point.

        Returns:
            A binding usable by this operation. A session created from a snapshot
            that became stale during ``create_session`` is returned ephemerally but
            is not written to the repository.
        """

        if request.session_key.rsplit(":", 1)[-1] != agent.agent_id:
            raise ValueError("session binding request agent does not match snapshot")
        with self._lock:
            generation = self._generations.get(agent.agent_id, 0)
            existing = self._repository.get(request.session_key)
            if existing is not None:
                revision = self._binding_revisions.get(
                    request.session_key,
                    self._startup_revisions.get(agent.agent_id, agent.revision),
                )
                if revision == agent.revision and self._binding_matches_workspace_root(
                    existing.kernel_session_id,
                    expected_workspace_root=str(agent.config.workspace_root),
                ):
                    refreshed = SessionBinding(
                        session_key=request.session_key,
                        kernel_session_id=existing.kernel_session_id,
                        reply_context=request.reply_context,
                    )
                    if self._write_guard_is_current(
                        agent=agent,
                        generation=generation,
                    ):
                        refreshed = self._repository.bind(
                            session_key=refreshed.session_key,
                            kernel_session_id=refreshed.kernel_session_id,
                            reply_context=refreshed.reply_context,
                        )
                        self._binding_revisions[request.session_key] = agent.revision
                    self._record_provenance(refreshed, agent=agent, persist_binding=True)
                    return refreshed

        config = agent.config
        metadata = _build_session_metadata(
            request.message,
            agent=agent,
            gateway_internal_port=request.gateway_internal_port,
        )
        session = await self._kernel.create_session(
            title=config.title,
            workspace_root=config.workspace_root,
            skills=list(config.skills) if config.skills else None,
            enabled_tools=resolve_enabled_tools(config),
            features=dict(config.features) if config.features else None,
            prompt=prompt_for(config, scenario=metadata),
            metadata=metadata,
        )
        kernel_session_id = str(getattr(session, "session_id", "")).strip()
        if not kernel_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        ephemeral = SessionBinding(
            session_key=request.session_key,
            kernel_session_id=kernel_session_id,
            reply_context=request.reply_context,
        )
        with self._lock:
            self._session_agents[kernel_session_id] = agent
            if not self._write_guard_is_current(
                agent=agent,
                generation=generation,
            ):
                return ephemeral
            binding = self._repository.bind(
                session_key=request.session_key,
                kernel_session_id=kernel_session_id,
                reply_context=request.reply_context,
            )
            self._binding_revisions[request.session_key] = agent.revision
            self._binding_agents[request.session_key] = agent
            return binding

    def lookup(self, session_key: str) -> SessionBinding | None:
        """Return one binding by its Gateway session key."""

        with self._lock:
            return self._repository.get(session_key)

    def invalidate_stale(self, agent_id: str, *, current_revision: int) -> None:
        """Drop only bindings older than the published Agent revision.

        Args:
            agent_id: Agent whose prior bindings must no longer be reused.
            current_revision: Revision returned by the immediately preceding
                catalog publication.

        Side Effects:
            Advances the Agent's binder generation and deletes stale rows without
            touching rows already created for ``current_revision``.
        """

        with self._lock:
            self._generations[agent_id] = self._generations.get(agent_id, 0) + 1
            startup_revision = self._startup_revisions.get(agent_id)
            for binding in self._repository.bindings_for_agent(agent_id):
                revision = self._binding_revisions.get(
                    binding.session_key,
                    startup_revision,
                )
                if revision == current_revision:
                    continue
                self._repository.drop(binding.session_key)
                self._binding_revisions.pop(binding.session_key, None)
                self._binding_agents.pop(binding.session_key, None)
            self._startup_revisions[agent_id] = current_revision

    def capture_write_guard(self, agent: LiveAgentSnapshot) -> BindingWriteGuard:
        """Capture the guard used by a semantic bind after an external await."""

        with self._lock:
            return BindingWriteGuard(
                agent_id=agent.agent_id,
                revision=agent.revision,
                generation=self._generations.get(agent.agent_id, 0),
            )

    def bind_conversation(
        self,
        request: ConversationBindingRequest,
        agent: LiveAgentSnapshot,
    ) -> ConversationBindResult:
        """Bind a canonical conversation when its pre-await guard is still current."""

        if (
            request.agent_id != agent.agent_id
            or request.guard.agent_id != agent.agent_id
        ):
            raise ValueError("conversation binding agent does not match snapshot")
        with self._lock:
            if (
                request.guard.revision != agent.revision
                or request.guard.generation != self._generations.get(agent.agent_id, 0)
                or not self._catalog.is_current(agent)
            ):
                return ConversationBindResult(status="stale", binding=None)
            binding = self._repository.bind(
                session_key=build_conversation_session_key(
                    channel_name=request.channel_name,
                    conversation_id=request.conversation_id,
                    agent_id=request.agent_id,
                ),
                kernel_session_id=request.kernel_session_id,
                reply_context=build_conversation_reply_context(
                    channel_name=request.channel_name,
                    conversation_id=request.conversation_id,
                ),
            )
            self._binding_revisions[binding.session_key] = agent.revision
            self._binding_agents[binding.session_key] = agent
            self._session_agents[request.kernel_session_id] = agent
            return ConversationBindResult(status="bound", binding=binding)

    def register_session_provenance(
        self, agent: LiveAgentSnapshot, *, kernel_session_id: str
    ) -> None:
        """Register a non-inbound Kernel session against its captured Agent snapshot."""

        normalized = kernel_session_id.strip()
        if not normalized:
            raise ValueError("kernel_session_id must be non-empty")
        with self._lock:
            self._session_agents[normalized] = agent

    def capture_session_provenance(
        self, kernel_session_id: str, *, expected_agent_id: str
    ) -> SessionProvenance | None:
        """Capture immutable origin facts for a tool call from one Kernel session."""

        with self._lock:
            agent = self._session_agents.get(kernel_session_id)
            if agent is None or agent.agent_id != expected_agent_id:
                return None
            return SessionProvenance(
                kernel_session_id=kernel_session_id,
                agent=agent,
                guard=self._guard_for(agent),
            )

    def capture_binding_provenance(
        self, session_key: str, *, expected_agent_id: str
    ) -> BindingProvenance | None:
        """Atomically capture a source binding, Agent snapshot, and semantic guard."""

        with self._lock:
            binding = self._repository.get(session_key)
            if binding is None:
                return None
            agent = self._binding_agents.get(session_key)
            if agent is None:
                agent = self._catalog.get(expected_agent_id)
                if agent is None:
                    return None
                self._record_provenance(binding, agent=agent, persist_binding=True)
            if agent.agent_id != expected_agent_id:
                return None
            return BindingProvenance(
                binding=binding,
                agent=agent,
                guard=self._guard_for(agent),
            )

    def find_by_kernel_session_id(
        self, kernel_session_id: str
    ) -> SessionBinding | None:
        """Reverse-resolve a Kernel session to its Gateway reply binding."""

        with self._lock:
            return self._repository.find_by_kernel_session_id(kernel_session_id)

    def find_canonical_direct(
        self, *, channel_name: str, agent_id: str
    ) -> SessionBinding | None:
        """Return the oldest direct-chat binding for an Agent and channel."""

        with self._lock:
            return self._repository.find_direct_by_agent(
                channel_name=channel_name,
                agent_id=agent_id,
            )

    def _write_guard_is_current(
        self,
        *,
        agent: LiveAgentSnapshot,
        generation: int,
    ) -> bool:
        return generation == self._generations.get(
            agent.agent_id, 0
        ) and self._catalog.is_current(agent)

    def _guard_for(self, agent: LiveAgentSnapshot) -> BindingWriteGuard:
        return BindingWriteGuard(
            agent_id=agent.agent_id,
            revision=agent.revision,
            generation=self._generations.get(agent.agent_id, 0),
        )

    def _record_provenance(
        self,
        binding: SessionBinding,
        *,
        agent: LiveAgentSnapshot,
        persist_binding: bool,
    ) -> None:
        self._session_agents[binding.kernel_session_id] = agent
        if persist_binding:
            self._binding_agents[binding.session_key] = agent

    def _binding_matches_workspace_root(
        self, session_id: str, *, expected_workspace_root: str
    ) -> bool:
        get_session = getattr(self._kernel, "get_session", None)
        if not callable(get_session):
            return True
        try:
            session = get_session(
                session_id=session_id,
                workspace_root=expected_workspace_root,
            )
        except RuntimeError:
            return False
        workspace_root = session.get("workspace_root")
        return (
            isinstance(workspace_root, str)
            and workspace_root.strip() == expected_workspace_root.strip()
        )


def _build_session_metadata(
    message: InboundMessage,
    *,
    agent: LiveAgentSnapshot,
    gateway_internal_port: int,
) -> dict[str, object]:
    """Build Kernel session metadata from one captured Agent snapshot."""

    config = agent.config
    metadata = dict(message.metadata)
    result: dict[str, object] = {
        "agent_id": agent.agent_id,
        "gateway_dispatch_url": (
            f"http://127.0.0.1:{gateway_internal_port}/internal/dispatch"
        ),
    }
    conversation_id = metadata.get("conversation_id")
    if isinstance(conversation_id, str) and conversation_id.strip():
        result["conversation_id"] = conversation_id.strip()
    profile_version = metadata.get("config_profile_version")
    if isinstance(profile_version, int):
        result["config_profile_version"] = profile_version
    if config.system_prompt:
        result["system_prompt"] = config.system_prompt
    if config.skills:
        result["skills"] = list(config.skills)
    if config.tool_allowlist:
        result["tool_allowlist"] = list(config.tool_allowlist)
    result["agent_features"] = dict(config.features)
    if config.custom_prompt:
        result["agent_custom_prompt"] = config.custom_prompt
    if message.is_group:
        result["conversation_type"] = "group"
        result["external_chat_id"] = message.external_chat_id or ""
        participants = _normalize_group_participants(metadata.get("participants"))
        if participants:
            result["participants"] = participants
        participant_agent_ids = metadata.get("participant_agent_ids")
        if isinstance(participant_agent_ids, list):
            result["participant_agent_ids"] = [
                value for value in participant_agent_ids if isinstance(value, str)
            ]
        elif participants:
            result["participant_agent_ids"] = _extract_participant_agent_ids(
                participants
            )
        else:
            result["participant_agent_ids"] = [agent.agent_id]
    else:
        result["conversation_type"] = "direct"
    return result


def _normalize_group_participants(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        participant_type = _optional_text(item.get("type"))
        if participant_type not in {"user", "agent"}:
            continue
        identity_key = "agent_id" if participant_type == "agent" else "user_id"
        identity = _optional_text(item.get(identity_key)) or _optional_text(
            item.get("id")
        )
        if identity is None:
            continue
        entry = {"type": participant_type, identity_key: identity}
        display_name = _optional_text(item.get("display_name"))
        if display_name is not None:
            entry["display_name"] = display_name
        normalized.append(entry)
    return normalized


def _extract_participant_agent_ids(
    participants: list[dict[str, str]],
) -> list[str]:
    return list(
        dict.fromkeys(
            participant["agent_id"]
            for participant in participants
            if participant.get("type") == "agent" and participant.get("agent_id")
        )
    )


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
