"""Own Gateway session resolution, persistence, and revision-safe writeback."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Any, Literal, Protocol

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.gateway.agent_catalog import (
    LiveAgentCatalog,
    LiveAgentSnapshot,
)
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
    ControlOperation,
    PendingExternalControlDelivery,
    PendingBoundaryIntent,
    SessionBinding,
    build_conversation_reply_context,
    build_conversation_session_key,
    build_external_session_key,
)
from agent.sdk import SessionRuntimeConfig
from personal_assistant.gateway.session_composition import (
    ProjectedAgentRuntime,
    project_agent_runtime,
    project_agent_session_capabilities,
)


class _SessionBindingRepository(Protocol):
    """Describe the private storage operations required by the binder."""

    def get(self, session_key: str) -> SessionBinding | None: ...

    def bind(
        self,
        *,
        session_key: str,
        kernel_session_id: str,
        reply_context: ReplyContext,
        applied_runtime_fingerprint: str | None = None,
        applied_fingerprint_schema: str | None = None,
        applied_profile_version: int | None = None,
    ) -> SessionBinding: ...

    def apply_runtime(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
    ) -> SessionBinding: ...

    def apply_runtime_with_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: BoundaryIntent,
    ) -> SessionBinding: ...

    def apply_runtime_with_pending_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: PendingBoundaryIntent,
    ) -> SessionBinding: ...

    def get_control_operation(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> ControlOperation | None: ...

    def publish_reset(
        self,
        *,
        binding: SessionBinding,
        operation_id: str | None,
        superseded_run_id: str | None,
        reply_text: str,
        external_saga_id: str | None = None,
    ) -> ControlOperation | None: ...

    def record_control_operation(
        self, outcome: ControlOperation, *, external_saga_id: str | None = None
    ) -> ControlOperation: ...

    def pending_external_controls(
        self,
    ) -> tuple[PendingExternalControlDelivery, ...]: ...

    def mark_external_control_handed_off(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None: ...

    def mark_external_control_materialized(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None: ...

    def is_run_superseded(self, run_id: str) -> bool: ...

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
        gateway_internal_port: Legacy configured port used when no actual URL provider exists.
        gateway_dispatch_url: Exact URL published by the active listener, when available.
    """

    session_key: str
    reply_context: ReplyContext
    message: InboundMessage
    gateway_internal_port: int | None = None
    gateway_dispatch_url: str | None = None
    runtime: SessionRuntimeConfig | None = None
    profile_version: int | None = None


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


@dataclass(frozen=True, slots=True)
class _SessionLogBindingProjection:
    """Expose the immutable durable facts required for one transcript address."""

    binding: SessionBinding
    agent: LiveAgentSnapshot


@dataclass(frozen=True, slots=True)
class ResetCandidate:
    """Hold an unbound fresh session until the coordinator can publish it."""

    binding: SessionBinding
    agent: LiveAgentSnapshot
    guard: BindingWriteGuard


@dataclass(frozen=True, slots=True)
class _VerifiedBindingOwnership:
    """Remember one process-local authoritative workspace ownership check."""

    kernel_session_id: str
    agent_id: str
    revision: int
    generation: int
    workspace_root: str


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
        reasoning_catalog: ModelReasoningCatalog | None = None,
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._kernel = kernel
        self._reasoning_catalog = reasoning_catalog
        self._lock = Lock()
        self._binding_revisions: dict[str, int] = {}
        self._binding_agents: dict[str, LiveAgentSnapshot] = {}
        self._session_agents: dict[str, LiveAgentSnapshot] = {}
        self._session_log_projections: Mapping[str, _SessionLogBindingProjection] = (
            MappingProxyType({})
        )
        self._verified_binding_ownership: dict[str, _VerifiedBindingOwnership] = {}
        self._generations: dict[str, int] = {}
        self._startup_revisions = {
            snapshot.agent_id: snapshot.revision
            for snapshot in catalog.values_snapshot()
        }
        # Read the durable rows before the IM receiver exists. Thereafter the
        # receiver reads this copy-on-write projection without taking the binder
        # lock or touching SQLite.
        for agent in catalog.values_snapshot():
            for binding in repository.bindings_for_agent(agent.agent_id):
                self._record_provenance(binding, agent=agent, persist_binding=True)

    async def resolve(
        self,
        request: SessionBindingRequest,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Reuse one binding, creating a complete-runtime session only when absent.

        Config publication never changes the session address. The coordinator admits
        a new runtime on the retained binding before it submits the next run.
        """

        if request.session_key.rsplit(":", 1)[-1] != agent.agent_id:
            raise ValueError("session binding request agent does not match snapshot")
        with self._lock:
            generation = self._generations.get(agent.agent_id, 0)
            existing = self._repository.get(request.session_key)
            ownership_is_verified = (
                existing is not None
                and self._ownership_is_verified(
                    existing,
                    agent=agent,
                    generation=generation,
                )
            )

        if existing is not None:
            workspace_matches = ownership_is_verified or await asyncio.to_thread(
                self._binding_matches_workspace_root,
                existing.kernel_session_id,
                expected_workspace_root=str(agent.config.workspace_root),
            )
            if workspace_matches:
                refreshed = self._repository.bind(
                    session_key=existing.session_key,
                    kernel_session_id=existing.kernel_session_id,
                    reply_context=request.reply_context,
                )
                with self._lock:
                    self._record_verified_ownership(
                        refreshed,
                        agent=agent,
                        generation=generation,
                    )
                    self._record_provenance(
                        refreshed, agent=agent, persist_binding=True
                    )
                return refreshed

        ephemeral = await self._create_binding_candidate(request, agent)
        kernel_session_id = ephemeral.kernel_session_id
        with self._lock:
            self._session_agents[kernel_session_id] = agent
            if not self._write_guard_is_current(agent=agent, generation=generation):
                return ephemeral
            binding = self._repository.bind(
                session_key=request.session_key,
                kernel_session_id=kernel_session_id,
                reply_context=request.reply_context,
                applied_runtime_fingerprint=ephemeral.applied_runtime_fingerprint,
                applied_fingerprint_schema=ephemeral.applied_fingerprint_schema,
                applied_profile_version=ephemeral.applied_profile_version,
            )
            self._record_verified_ownership(binding, agent=agent, generation=generation)
            self._record_provenance(binding, agent=agent, persist_binding=True)
            return binding

    async def prepare_reset(
        self,
        request: SessionBindingRequest,
        agent: LiveAgentSnapshot,
    ) -> ResetCandidate:
        """Create a fresh Kernel session without changing the current binding."""

        if request.session_key.rsplit(":", 1)[-1] != agent.agent_id:
            raise ValueError("session binding request agent does not match snapshot")
        with self._lock:
            guard = self._guard_for(agent)
        binding = await self._create_binding_candidate(request, agent)
        return ResetCandidate(binding=binding, agent=agent, guard=guard)

    def completed_control(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> ControlOperation | None:
        """Return a durable result so a replay does not repeat its side effect."""

        with self._lock:
            return self._repository.get_control_operation(
                session_key=session_key, operation_id=operation_id, kind=kind
            )

    def complete_control(
        self, outcome: ControlOperation, *, external_saga_id: str | None = None
    ) -> ControlOperation:
        """Persist an idempotent non-reset outcome in the binding owner."""

        with self._lock:
            return self._repository.record_control_operation(
                outcome, external_saga_id=external_saga_id
            )

    def pending_external_controls(self) -> tuple[PendingExternalControlDelivery, ...]:
        """Return external controls that survived outcome commit but lack handoff."""

        with self._lock:
            return self._repository.pending_external_controls()

    def mark_external_control_handed_off(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None:
        """Commit the provider handoff after the outbound router accepts it."""

        with self._lock:
            self._repository.mark_external_control_handed_off(
                session_key=session_key, operation_id=operation_id, kind=kind
            )

    def mark_external_control_materialized(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None:
        """Record saga output creation before trying its external router handoff."""

        with self._lock:
            self._repository.mark_external_control_materialized(
                session_key=session_key, operation_id=operation_id, kind=kind
            )

    def publish_reset(
        self,
        candidate: ResetCandidate,
        *,
        operation_id: str | None,
        superseded_run_id: str | None,
        reply_text: str,
        external_saga_id: str | None = None,
    ) -> SessionBinding:
        """Publish a prepared reset only while its catalog guard remains current."""

        with self._lock:
            if not self._write_guard_is_current(
                agent=candidate.agent, generation=candidate.guard.generation
            ):
                raise RuntimeError("agent changed before fresh session could publish")
            self._repository.publish_reset(
                binding=candidate.binding,
                operation_id=operation_id,
                superseded_run_id=superseded_run_id,
                reply_text=reply_text,
                external_saga_id=external_saga_id,
            )
            published = self._repository.get(candidate.binding.session_key)
            if published is None:  # pragma: no cover - reset transaction invariant.
                raise RuntimeError(
                    "fresh session binding disappeared after publication"
                )
            self._session_agents[published.kernel_session_id] = candidate.agent
            self._record_verified_ownership(
                published,
                agent=candidate.agent,
                generation=candidate.guard.generation,
            )
            self._record_provenance(
                published, agent=candidate.agent, persist_binding=True
            )
            return published

    async def _create_binding_candidate(
        self,
        request: SessionBindingRequest,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Create the complete-runtime session used by resolve and reset publication."""

        metadata = _build_session_metadata(
            request.message,
            agent=agent,
            gateway_internal_port=request.gateway_internal_port,
            gateway_dispatch_url=request.gateway_dispatch_url,
        )
        runtime = request.runtime
        if runtime is None:
            capabilities = project_agent_session_capabilities(agent, scenario=metadata)
            session = await self._kernel.create_session(
                title=agent.config.title,
                workspace_root=agent.config.workspace_root,
                skills=capabilities.skills,
                enabled_tools=capabilities.enabled_tools,
                features=capabilities.features,
                prompt=capabilities.prompt,
                metadata=metadata,
            )
            identity = None
        else:
            session = await self._kernel.create_session(
                title=agent.config.title,
                workspace_root=agent.config.workspace_root,
                runtime=runtime,
                metadata=metadata,
            )
            identity = self._kernel.identify_runtime(runtime=runtime)
        kernel_session_id = str(getattr(session, "session_id", "")).strip()
        if not kernel_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        return SessionBinding(
            session_key=request.session_key,
            kernel_session_id=kernel_session_id,
            reply_context=request.reply_context,
            applied_runtime_fingerprint=(
                identity.runtime_fingerprint if identity is not None else None
            ),
            applied_fingerprint_schema=(
                identity.fingerprint_schema if identity is not None else None
            ),
            applied_profile_version=request.profile_version,
        )

    def project_runtime(
        self,
        *,
        agent: LiveAgentSnapshot,
        message: InboundMessage,
        resolved_model: str,
    ) -> ProjectedAgentRuntime:
        """Project the sole raw runtime used by session creation and reconfiguration."""

        metadata = _build_session_metadata(
            message,
            agent=agent,
            gateway_internal_port=None,
            gateway_dispatch_url=None,
        )
        return project_agent_runtime(
            agent,
            scenario=metadata,
            resolved_model=resolved_model,
            reasoning_catalog=self._reasoning_catalog,
        )

    def persist_applied_runtime(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Persist only a Kernel-confirmed identity after durable reconfiguration."""

        updated = self._repository.apply_runtime(
            binding,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
        )
        with self._lock:
            self._record_provenance(updated, agent=agent, persist_binding=True)
        return updated

    def persist_applied_runtime_with_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: BoundaryIntent,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Atomically persist an actual runtime replacement and its user anchor."""

        updated = self._repository.apply_runtime_with_boundary(
            binding,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            boundary=boundary,
        )
        with self._lock:
            self._record_provenance(updated, agent=agent, persist_binding=True)
        return updated

    def persist_applied_runtime_with_pending_boundary(
        self,
        binding: SessionBinding,
        *,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        boundary: PendingBoundaryIntent,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        """Atomically persist an external applied runtime before IM has its anchor."""

        updated = self._repository.apply_runtime_with_pending_boundary(
            binding,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            boundary=boundary,
        )
        with self._lock:
            self._record_provenance(updated, agent=agent, persist_binding=True)
        return updated

    def current_agent(self, agent_id: str) -> LiveAgentSnapshot:
        """Return the latest published snapshot for a queued new-run admission."""

        agent = self._catalog.get(agent_id)
        if agent is None:
            raise ValueError(f"unknown agent: {agent_id}")
        return agent

    def lookup(self, session_key: str) -> SessionBinding | None:
        """Return one binding by its Gateway session key."""

        with self._lock:
            return self._repository.get(session_key)

    def is_run_superseded(self, run_id: str) -> bool:
        """Return whether a durable reset revoked this run's visible output."""

        with self._lock:
            return self._repository.is_run_superseded(run_id)

    def invalidate_stale(self, agent_id: str, *, current_revision: int) -> None:
        """Invalidate transient ownership checks after a configuration publication.

        Durable bindings remain address-stable. The next new-run admission compares
        the complete runtime identity and replaces configuration in that same
        session rather than deleting its transcript.
        """

        with self._lock:
            self._generations[agent_id] = self._generations.get(agent_id, 0) + 1
            for binding in self._repository.bindings_for_agent(agent_id):
                self._verified_binding_ownership.pop(binding.session_key, None)
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
            self._record_provenance(binding, agent=agent, persist_binding=True)
            # A semantic bind can point an existing conversation key at another
            # Kernel session. The next resolve must establish workspace ownership
            # for that exact key/session pair before it enters the stable hot path.
            self._verified_binding_ownership.pop(binding.session_key, None)
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

    def capture_session_log_projection(
        self, session_key: str, *, expected_agent_id: str
    ) -> _SessionLogBindingProjection | None:
        """Return an immutable binding projection without blocking the IM receiver.

        The mapping is populated from committed persistent rows during Gateway
        startup and replaced after each later durable binding update. Its readers
        never take the binder lock or query SQLite.
        """

        projection = self._session_log_projections.get(session_key)
        if projection is None or projection.agent.agent_id != expected_agent_id:
            return None
        return projection

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

    def _binding_revision(
        self,
        session_key: str,
        *,
        agent: LiveAgentSnapshot,
    ) -> int:
        return self._binding_revisions.get(
            session_key,
            self._startup_revisions.get(agent.agent_id, agent.revision),
        )

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
            projections = dict(self._session_log_projections)
            projections[binding.session_key] = _SessionLogBindingProjection(
                binding=binding, agent=agent
            )
            self._session_log_projections = MappingProxyType(projections)

    def _ownership_is_verified(
        self,
        binding: SessionBinding,
        *,
        agent: LiveAgentSnapshot,
        generation: int,
    ) -> bool:
        return self._verified_binding_ownership.get(
            binding.session_key
        ) == _VerifiedBindingOwnership(
            kernel_session_id=binding.kernel_session_id,
            agent_id=agent.agent_id,
            revision=agent.revision,
            generation=generation,
            workspace_root=str(agent.config.workspace_root).strip(),
        )

    def _record_verified_ownership(
        self,
        binding: SessionBinding,
        *,
        agent: LiveAgentSnapshot,
        generation: int,
    ) -> None:
        self._verified_binding_ownership[binding.session_key] = (
            _VerifiedBindingOwnership(
                kernel_session_id=binding.kernel_session_id,
                agent_id=agent.agent_id,
                revision=agent.revision,
                generation=generation,
                workspace_root=str(agent.config.workspace_root).strip(),
            )
        )

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
    gateway_internal_port: int | None,
    gateway_dispatch_url: str | None = None,
) -> dict[str, object]:
    """Build Kernel session metadata from one captured Agent snapshot."""

    config = agent.config
    metadata = dict(message.metadata)
    result: dict[str, object] = {"agent_id": agent.agent_id}
    normalized_dispatch_url = (
        gateway_dispatch_url.strip()
        if isinstance(gateway_dispatch_url, str) and gateway_dispatch_url.strip()
        else None
    )
    if normalized_dispatch_url is not None:
        result["gateway_dispatch_url"] = normalized_dispatch_url
    elif gateway_internal_port is not None:
        result["gateway_dispatch_url"] = (
            f"http://127.0.0.1:{gateway_internal_port}/internal/dispatch"
        )
    conversation_id = metadata.get("conversation_id")
    if isinstance(conversation_id, str) and conversation_id.strip():
        result["conversation_id"] = conversation_id.strip()
    profile_version = metadata.get("config_profile_version")
    if isinstance(profile_version, int):
        result["config_profile_version"] = profile_version
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


def build_session_log_path_provider(
    *,
    session_binder: GatewaySessionBinder,
    channel_name: str,
    workspace_config_dirname: str,
) -> Callable[[str, str], str | None]:
    """Resolve a Web IM conversation through its durable Gateway session binding.

    The binding already records the root Kernel session id and its captured Agent
    workspace. Deriving that address avoids filesystem probing on the Gateway
    receive loop: a missing binding is a missing transcript, while a durable
    binding projects its path as ready. Provider failures remain a distinct
    unavailable wire state.
    """

    def resolve(agent_id: str, conversation_id: str) -> str | None:
        source = session_binder.capture_session_log_projection(
            build_conversation_session_key(
                channel_name=channel_name,
                conversation_id=conversation_id,
                agent_id=agent_id,
            ),
            expected_agent_id=agent_id,
        )
        if source is None:
            return None
        path = (
            Path(source.agent.config.workspace_root)
            / workspace_config_dirname
            / "sessions"
            / f"{source.binding.kernel_session_id}.jsonl"
        )
        return str(path)

    return resolve


def build_session_fork_handler(
    *, kernel: Any, session_binder: GatewaySessionBinder, channel_name: str
) -> Callable[[Mapping[str, object]], Any]:
    """Build the IM session-fork operation from the session-binding owner.

    Args:
        kernel: In-process Kernel that performs the immutable history fork.
        session_binder: Owner of source and destination conversation bindings.
        channel_name: Gateway channel namespace used for IM conversations.

    Returns:
        Async handler returning the wire-ready fork result.
    """

    async def handle(payload: Mapping[str, object]) -> Mapping[str, object]:
        source_conversation_id = str(payload.get("source_conversation_id") or "")
        new_conversation_id = str(payload.get("new_conversation_id") or "")
        agent_id = str(payload.get("agent_id") or "")
        fork_point = payload.get("fork_point")
        message_id = (
            str(fork_point.get("message_id") or "")
            if isinstance(fork_point, Mapping)
            else ""
        )
        if not (
            source_conversation_id and new_conversation_id and agent_id and message_id
        ):
            return {"ok": False, "error": "fork request missing required fields"}
        source = session_binder.capture_binding_provenance(
            build_conversation_session_key(
                channel_name=channel_name,
                conversation_id=source_conversation_id,
                agent_id=agent_id,
            ),
            expected_agent_id=agent_id,
        )
        if source is None:
            external_source = str(payload.get("source_external_source") or "").strip()
            external_chat_id = str(payload.get("source_external_chat_id") or "").strip()
            if external_source and external_chat_id:
                source = session_binder.capture_binding_provenance(
                    build_external_session_key(
                        external_source=external_source,
                        external_chat_id=external_chat_id,
                        agent_id=agent_id,
                    ),
                    expected_agent_id=agent_id,
                )
        if source is None:
            return {"ok": False, "error": "source session binding not found"}
        try:
            new_session = await kernel.fork_session(
                source.binding.kernel_session_id,
                workspace_root=source.agent.config.workspace_root,
                up_to=message_id,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        bind_result = session_binder.bind_conversation(
            ConversationBindingRequest(
                channel_name=channel_name,
                conversation_id=new_conversation_id,
                agent_id=agent_id,
                kernel_session_id=new_session.session_id,
                guard=source.guard,
            ),
            source.agent,
        )
        if bind_result.status == "stale":
            return {
                "ok": False,
                "error": "agent config changed while session fork was running",
            }
        return {
            "ok": True,
            "new_session_id": new_session.session_id,
            "id_map": dict(new_session.fork_id_map or {}),
        }

    return handle
