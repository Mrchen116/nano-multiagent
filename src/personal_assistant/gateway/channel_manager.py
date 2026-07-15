"""Sole lifecycle owner for dynamically managed external channels."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Callable, Mapping, Protocol
from uuid import uuid4

from personal_assistant.channels.base import ChannelAdapter, InboundHandler
from personal_assistant.gateway.channel_registry import ChannelRegistry


@dataclass(frozen=True, slots=True)
class ChannelGeneration:
    """CAS identity shared by desired config, runtime metadata, and status."""

    provider_identity_fingerprint: str
    provider_identity_revision: int
    channel_revision: int
    credential_revision: int


@dataclass(frozen=True, slots=True)
class ManagedChannelSpec:
    """Decrypted Gateway-local desired item from one authoritative manifest."""

    channel_id: str
    agent_id: str
    provider: str
    enabled: bool
    config: Mapping[str, object]
    credentials: Mapping[str, str]
    provider_runtime: Mapping[str, str]
    generation: ChannelGeneration


@dataclass(frozen=True, slots=True)
class ChannelManifest:
    """Complete managed-channel snapshot for this Gateway node."""

    manifest_revision: int
    channels: tuple[ManagedChannelSpec, ...]


@dataclass(frozen=True, slots=True)
class ChannelStatusSnapshot:
    """Ordered runtime status emitted through one serial status sink."""

    channel_id: str
    generation: ChannelGeneration
    runtime_incarnation: str
    status_sequence: int
    connection_state: str
    diagnostics_state: str = "unknown"
    status_code: str | None = None
    status_message: str | None = None
    instance_started: bool = False


@dataclass(frozen=True, slots=True)
class ProviderMetadataReport:
    """Generation-scoped non-sensitive provider metadata patch."""

    channel_id: str
    generation: ChannelGeneration
    patch: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    """Per-manifest lifecycle result returned to the WS reconciliation layer."""

    manifest_revision: int
    applied_channel_ids: tuple[str, ...]
    failed_channel_ids: tuple[str, ...]


class ProviderRuntimeFactory(Protocol):
    """Build one adapter after credentials have been opened and validated."""

    def __call__(
        self,
        spec: ManagedChannelSpec,
        metadata_binder: Callable[[dict[str, str]], dict[str, str] | None],
        status_handler: Callable[..., bool],
    ) -> ChannelAdapter: ...


class FeishuActivationPolicy:
    """Idempotently add the bundled Feishu skill to explicit allowlists."""

    def __init__(
        self,
        on_activated: Callable[[str], None],
        *,
        load_skills: Callable[[str], tuple[str, ...]] | None = None,
        save_skills: Callable[[str, tuple[str, ...]], object] | None = None,
    ) -> None:
        self._on_activated = on_activated
        self._load_skills = load_skills
        self._save_skills = save_skills
        self._activated: set[str] = set()
        self._lock = threading.Lock()

    def ensure(self, agent_id: str) -> None:
        """Activate once; an empty allowlist intentionally keeps its default semantics."""
        with self._lock:
            if agent_id in self._activated:
                return
            if self._load_skills is not None and self._save_skills is not None:
                current = self._load_skills(agent_id)
                if current and "feishu-doc" not in current:
                    self._save_skills(agent_id, (*current, "feishu-doc"))
            self._on_activated(agent_id)
            self._activated.add(agent_id)


@dataclass(slots=True)
class _ActiveRuntime:
    spec: ManagedChannelSpec
    adapter: ChannelAdapter
    runtime_name: str
    incarnation: str
    last_status_sequence: int = 1
    metadata: dict[str, str] = field(default_factory=dict)


class ChannelManager:
    """Serialize dynamic registry, generation, metadata, and worker cutovers."""

    def __init__(
        self,
        *,
        registry: ChannelRegistry,
        on_inbound: InboundHandler,
        provider_factories: Mapping[str, ProviderRuntimeFactory],
        status_sink: Callable[[ChannelStatusSnapshot], None],
        metadata_sink: Callable[[ProviderMetadataReport], None] | None = None,
        activation_policy: FeishuActivationPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._on_inbound = on_inbound
        self._provider_factories = dict(provider_factories)
        self._status_sink = status_sink
        self._metadata_sink = metadata_sink or (lambda _report: None)
        self._activation_policy = activation_policy
        self._active: dict[str, _ActiveRuntime] = {}
        self._lock = threading.RLock()

    @property
    def registry(self) -> ChannelRegistry:
        """Expose the shared routing registry to existing outbound components."""
        return self._registry

    async def start_cached(self) -> tuple[ChannelStatusSnapshot, ...]:
        """Return active snapshots; encrypted cache startup is completed in M2."""
        with self._lock:
            return tuple(
                self._snapshot(active, connection_state="connecting")
                for active in self._active.values()
            )

    async def reconcile(self, manifest: ChannelManifest) -> ReconcileReport:
        """Apply one complete manifest with per-runtime stop-before-start cutover."""
        with self._lock:
            desired = {item.channel_id: item for item in manifest.channels}
            applied: list[str] = []
            failed: list[str] = []
            for channel_id in tuple(self._active):
                spec = desired.get(channel_id)
                if spec is None or not spec.enabled:
                    self._stop_active(channel_id)
            for spec in manifest.channels:
                if spec.provider == "web_relay" or spec.agent_id == "web_relay":
                    failed.append(spec.channel_id)
                    continue
                if not spec.enabled:
                    applied.append(spec.channel_id)
                    continue
                current = self._active.get(spec.channel_id)
                if current is not None and current.spec == spec:
                    applied.append(spec.channel_id)
                    continue
                if self._replace_runtime(spec):
                    applied.append(spec.channel_id)
                else:
                    failed.append(spec.channel_id)
            return ReconcileReport(
                manifest_revision=manifest.manifest_revision,
                applied_channel_ids=tuple(applied),
                failed_channel_ids=tuple(failed),
            )

    async def reconnect(self, channel_id: str) -> ChannelStatusSnapshot:
        """Replace one current runtime under the same desired generation."""
        with self._lock:
            active = self._active.get(channel_id)
            if active is None:
                raise LookupError("channel runtime not found")
            spec = active.spec
            if not self._replace_runtime(spec):
                raise RuntimeError("channel reconnect failed")
            return self._snapshot(
                self._active[channel_id], connection_state="connecting"
            )

    async def close(self) -> None:
        """Stop all managed runtimes without touching static web relay adapters."""
        with self._lock:
            for channel_id in tuple(self._active):
                self._stop_active(channel_id, drain=True)

    def record_provider_metadata(
        self,
        *,
        channel_id: str,
        generation: ChannelGeneration,
        patch: Mapping[str, str],
    ) -> dict[str, str] | None:
        """Apply current-generation metadata with owner/bot set-if-null semantics."""
        with self._lock:
            active = self._active.get(channel_id)
            if active is None or active.spec.generation != generation:
                return None
            accepted: dict[str, str] = {}
            for key in ("owner_open_id", "bot_open_id"):
                value = patch.get(key)
                if not isinstance(value, str) or not value.strip():
                    continue
                current = active.metadata.get(key)
                if current:
                    accepted[key] = current
                    continue
                active.metadata[key] = value.strip()
                accepted[key] = value.strip()
            new_values = {
                key: value
                for key, value in accepted.items()
                if active.spec.provider_runtime.get(key) != value
            }
            if new_values:
                self._metadata_sink(
                    ProviderMetadataReport(
                        channel_id=channel_id,
                        generation=generation,
                        patch=new_values,
                    )
                )
            return dict(active.metadata)

    def accept_status(
        self,
        *,
        channel_id: str,
        generation: ChannelGeneration,
        runtime_incarnation: str,
        status_sequence: int,
        connection_state: str,
        diagnostics_state: str = "unknown",
        status_code: str | None = None,
        status_message: str | None = None,
    ) -> bool:
        """Forward only monotonic status from the active generation/incarnation."""
        with self._lock:
            active = self._active.get(channel_id)
            if (
                active is None
                or active.spec.generation != generation
                or active.incarnation != runtime_incarnation
                or status_sequence <= active.last_status_sequence
            ):
                return False
            active.last_status_sequence = status_sequence
            self._status_sink(
                ChannelStatusSnapshot(
                    channel_id=channel_id,
                    generation=generation,
                    runtime_incarnation=runtime_incarnation,
                    status_sequence=status_sequence,
                    connection_state=connection_state,
                    diagnostics_state=diagnostics_state,
                    status_code=status_code,
                    status_message=status_message,
                )
            )
            return True

    def _replace_runtime(self, spec: ManagedChannelSpec) -> bool:
        factory = self._provider_factories.get(spec.provider)
        if factory is None:
            return False
        if self._activation_policy is not None and spec.provider == "feishu":
            self._activation_policy.ensure(spec.agent_id)
        incarnation = uuid4().hex

        def bind_metadata(patch: dict[str, str]) -> dict[str, str] | None:
            return self.record_provider_metadata(
                channel_id=spec.channel_id,
                generation=spec.generation,
                patch=patch,
            )

        def handle_status(**payload: object) -> bool:
            return self.accept_status(
                channel_id=spec.channel_id,
                generation=spec.generation,
                runtime_incarnation=incarnation,
                status_sequence=int(payload["status_sequence"]),
                connection_state=str(payload["connection_state"]),
                diagnostics_state=str(payload.get("diagnostics_state", "unknown")),
                status_code=payload.get("status_code")
                if isinstance(payload.get("status_code"), str)
                else None,
                status_message=payload.get("status_message")
                if isinstance(payload.get("status_message"), str)
                else None,
            )

        try:
            adapter = factory(spec, bind_metadata, handle_status)
        except Exception:
            self._stop_active(spec.channel_id)
            return False
        runtime_name = f"{spec.provider}:{spec.agent_id}"
        if adapter.name != runtime_name:
            self._stop_active(spec.channel_id)
            return False
        self._stop_active(spec.channel_id)
        active = _ActiveRuntime(
            spec=spec,
            adapter=adapter,
            runtime_name=runtime_name,
            incarnation=incarnation,
            metadata=dict(spec.provider_runtime),
        )
        self._active[spec.channel_id] = active
        barrier = self._snapshot(
            active,
            connection_state="connecting",
            instance_started=True,
        )
        self._status_sink(barrier)
        try:
            adapter.start(self._on_inbound)
            self._registry.register(adapter)
        except Exception:
            self._active.pop(spec.channel_id, None)
            self._registry.remove(runtime_name, expected=adapter)
            self._status_sink(
                ChannelStatusSnapshot(
                    channel_id=spec.channel_id,
                    generation=spec.generation,
                    runtime_incarnation=incarnation,
                    status_sequence=2,
                    connection_state="failed",
                    status_code="runtime_start_failed",
                    status_message="Channel runtime could not start.",
                )
            )
            return False
        return True

    def _stop_active(self, channel_id: str, *, drain: bool = False) -> None:
        active = self._active.pop(channel_id, None)
        if active is None:
            return
        self._registry.remove(active.runtime_name, expected=active.adapter)
        stop_invalidated = getattr(active.adapter, "stop_invalidated", None)
        if not drain and callable(stop_invalidated):
            stop_invalidated()
        else:
            active.adapter.stop()

    @staticmethod
    def _snapshot(
        active: _ActiveRuntime,
        *,
        connection_state: str,
        instance_started: bool = False,
    ) -> ChannelStatusSnapshot:
        return ChannelStatusSnapshot(
            channel_id=active.spec.channel_id,
            generation=active.spec.generation,
            runtime_incarnation=active.incarnation,
            status_sequence=active.last_status_sequence,
            connection_state=connection_state,
            instance_started=instance_started,
        )
