"""Sole lifecycle owner for dynamically managed external channels."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
import time
import threading
from typing import Callable, Mapping, Protocol
from uuid import uuid4

from personal_assistant.channels.base import (
    ChannelAdapter,
    ChannelStartupError,
    InboundHandler,
)
from personal_assistant.gateway.channel_manifest_store import (
    CachedChannelSpec,
    ChannelManifestStore,
    ChannelManifestStoreError,
)
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
    credential_envelope: Mapping[str, object] = field(default_factory=dict)
    credential_key_id: str = ""


@dataclass(frozen=True, slots=True)
class ChannelRemovalIntent:
    """Credential-free explicit deletion identity from the IM control plane."""

    removal_token: str
    channel_id: str
    agent_id: str
    provider: str
    deletion_manifest_revision: int


@dataclass(frozen=True, slots=True)
class ChannelManifest:
    """Complete managed-channel snapshot for this Gateway node."""

    manifest_revision: int
    channels: tuple[ManagedChannelSpec, ...]
    owner_id: str = ""
    node_id: str = ""
    removals: tuple[ChannelRemovalIntent, ...] = ()


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
    checks: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderMetadataReport:
    """Generation-scoped non-sensitive provider metadata patch."""

    channel_id: str
    generation: ChannelGeneration
    patch: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ProviderRuntimeBuild:
    """Return an adapter plus metadata learned before generation cutover."""

    adapter: ChannelAdapter
    initial_metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    """Per-manifest lifecycle result returned to the WS reconciliation layer."""

    manifest_revision: int
    applied_channel_ids: tuple[str, ...]
    failed_channel_ids: tuple[str, ...]
    outcome: str = "applied"
    removal_outcomes: tuple[RemovalOutcome, ...] = ()
    failures: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class RemovalOutcome:
    """Report one explicit removal intent independently from the node head."""

    removal_token: str
    channel_id: str
    outcome: str
    error_code: str | None = None
    error_message: str | None = None

    def as_payload(self) -> dict[str, object]:
        """Serialize the token result without adding empty diagnostic fields."""
        payload: dict[str, object] = {
            "removal_token": self.removal_token,
            "channel_id": self.channel_id,
            "outcome": self.outcome,
        }
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        if self.error_message is not None:
            payload["error_message"] = self.error_message
        return payload


class ProviderRuntimeFactory(Protocol):
    """Build one adapter after credentials have been opened and validated."""

    def __call__(
        self,
        spec: ManagedChannelSpec,
        metadata_binder: Callable[[dict[str, str]], dict[str, str] | None],
        status_handler: Callable[..., bool],
    ) -> ChannelAdapter | ProviderRuntimeBuild: ...


class FeishuActivationPolicy:
    """Idempotently add the bundled Feishu skill to explicit allowlists."""

    def __init__(
        self,
        on_activated: Callable[[str], bool | None],
        *,
        load_skills: Callable[[str], tuple[str, ...]] | None = None,
        save_skills: Callable[[str, tuple[str, ...]], object] | None = None,
    ) -> None:
        self._on_activated = on_activated
        self._load_skills = load_skills
        self._save_skills = save_skills
        self._activated: set[str] = set()
        self._lock = threading.Lock()

    def ensure(self, agent_id: str) -> bool:
        """Activate once; an empty allowlist intentionally keeps its default semantics."""
        with self._lock:
            if agent_id in self._activated:
                return True
            try:
                if self._load_skills is not None and self._save_skills is not None:
                    current = self._load_skills(agent_id)
                    if current and "feishu-doc" not in current:
                        self._save_skills(agent_id, (*current, "feishu-doc"))
                if self._on_activated(agent_id) is False:
                    return False
            except Exception:  # noqa: BLE001 - retry owns transient persistence failures.
                return False
            self._activated.add(agent_id)
            return True


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
        manifest_store: ChannelManifestStore | None = None,
        credential_opener: Callable[[CachedChannelSpec], Mapping[str, str]] | None = None,
    ) -> None:
        self._registry = registry
        self._on_inbound = on_inbound
        self._provider_factories = dict(provider_factories)
        self._status_sink = status_sink
        self._metadata_sink = metadata_sink or (lambda _report: None)
        self._activation_policy = activation_policy
        self._manifest_store = manifest_store
        self._credential_opener = credential_opener
        self._active: dict[str, _ActiveRuntime] = {}
        self._desired: dict[str, ManagedChannelSpec] = {}
        self._restart_attempts: dict[tuple[str, ChannelGeneration], int] = {}
        self._restart_scheduled: set[
            tuple[str, ChannelGeneration, str]
        ] = set()
        self._closing = False
        try:
            self._last_seen_manifest_revision = (
                manifest_store.last_seen_manifest_revision if manifest_store else 0
            )
            self._last_applied_manifest_revision = (
                manifest_store.last_applied_manifest_revision if manifest_store else 0
            )
        except ChannelManifestStoreError as exc:
            if str(exc) != "key_id mismatch":
                raise
            self._last_seen_manifest_revision = 0
            self._last_applied_manifest_revision = 0
        self._lock = threading.RLock()

    @property
    def registry(self) -> ChannelRegistry:
        """Expose the shared routing registry to existing outbound components."""
        return self._registry

    async def start_cached(self) -> tuple[ChannelStatusSnapshot, ...]:
        """Open the encrypted local manifest and start enabled channels without IM."""
        return await asyncio.to_thread(self._start_cached_sync)

    def _start_cached_sync(self) -> tuple[ChannelStatusSnapshot, ...]:
        with self._lock:
            store = self._manifest_store
            if store is None:
                return ()
            try:
                cached = store.load_manifest()
            except ChannelManifestStoreError as exc:
                if str(exc) != "key_id mismatch":
                    raise
                cached = store.quarantine_key_mismatch()
                if cached is None:
                    return ()
                return tuple(
                    self.report_credential_reentry(
                        channel_id=item.channel_id,
                        generation=ChannelGeneration(
                            provider_identity_fingerprint=(
                                item.provider_identity_fingerprint
                            ),
                            provider_identity_revision=(
                                item.provider_identity_revision
                            ),
                            channel_revision=item.channel_revision,
                            credential_revision=item.credential_revision,
                        ),
                    )
                    for item in cached.channels
                )
            if cached is None:
                return ()
            if cached.channels and self._credential_opener is None:
                raise ChannelManifestStoreError("credential opener is required")
            for item in cached.channels:
                assert self._credential_opener is not None
                spec = self._managed_from_cached(
                    item,
                    credentials=(
                        self._credential_opener(item) if item.enabled else {}
                    ),
                )
                self._desired[item.channel_id] = spec
                if not item.enabled:
                    continue
                if not self._replace_runtime(spec):
                    raise RuntimeError(
                        f"cached channel runtime could not start: {item.channel_id}"
                    )
            self._last_seen_manifest_revision = max(
                self._last_seen_manifest_revision, cached.manifest_revision
            )
            return tuple(
                self._snapshot(active, connection_state="connecting")
                for active in self._active.values()
            )

    def report_credential_reentry(
        self, *, channel_id: str, generation: ChannelGeneration
    ) -> ChannelStatusSnapshot:
        """Report an undecryptable desired generation without replacing safe runtime.

        Args:
            channel_id: Desired channel whose credential could not be opened.
            generation: IM-authored generation parsed before envelope opening failed.

        Returns:
            The emitted recovery status snapshot.
        """
        with self._lock:
            active = self._active.get(channel_id)
            if active is not None and active.spec.generation == generation:
                active.last_status_sequence += 1
                incarnation = active.incarnation
                sequence = active.last_status_sequence
                instance_started = False
            else:
                incarnation = uuid4().hex
                sequence = 1
                instance_started = True
            snapshot = ChannelStatusSnapshot(
                channel_id=channel_id,
                generation=generation,
                runtime_incarnation=incarnation,
                status_sequence=sequence,
                connection_state="failed",
                diagnostics_state="unknown",
                status_code="credential_reentry_required",
                status_message="Channel credentials must be entered again.",
                instance_started=instance_started,
            )
            self._status_sink(snapshot)
            return snapshot

    async def reconcile(self, manifest: ChannelManifest) -> ReconcileReport:
        """Apply one complete manifest with per-runtime stop-before-start cutover."""
        return await asyncio.to_thread(self._reconcile_sync, manifest)

    def _reconcile_sync(self, manifest: ChannelManifest) -> ReconcileReport:
        with self._lock:
            if manifest.manifest_revision < self._last_seen_manifest_revision:
                return ReconcileReport(
                    manifest_revision=manifest.manifest_revision,
                    applied_channel_ids=(),
                    failed_channel_ids=(),
                    outcome="stale",
                )
            self._last_seen_manifest_revision = max(
                self._last_seen_manifest_revision, manifest.manifest_revision
            )
            desired = {item.channel_id: item for item in manifest.channels}
            self._desired = desired
            removals = {item.channel_id: item for item in manifest.removals}
            applied: list[str] = []
            failed: list[str] = []
            failures: list[dict[str, object]] = []
            removal_outcomes: dict[str, RemovalOutcome] = {}
            cached = self._manifest_store.load_manifest() if self._manifest_store else None
            cached_channel_ids = {
                item.channel_id for item in cached.channels
            } if cached is not None else set()
            retryable_failure = False
            for channel_id in tuple(self._active):
                spec = desired.get(channel_id)
                if spec is None or not spec.enabled:
                    try:
                        self._stop_active(channel_id)
                    except Exception as exc:  # noqa: BLE001
                        retryable_failure = True
                        failure = {
                            "channel_id": channel_id,
                            "error_code": "runtime_stop_failed",
                            "error_message": str(exc),
                        }
                        failures.append(failure)
                        removal = removals.get(channel_id)
                        if removal is not None:
                            removal_outcomes[channel_id] = RemovalOutcome(
                                removal_token=removal.removal_token,
                                channel_id=channel_id,
                                outcome="failed",
                                error_code="runtime_stop_failed",
                                error_message=str(exc),
                            )
                        continue
            for spec in manifest.channels:
                if spec.provider == "web_relay" or spec.agent_id == "web_relay":
                    failed.append(spec.channel_id)
                    continue
                if not spec.enabled:
                    if spec.channel_id not in self._active:
                        self._status_sink(
                            ChannelStatusSnapshot(
                                channel_id=spec.channel_id,
                                generation=spec.generation,
                                runtime_incarnation=uuid4().hex,
                                status_sequence=1,
                                connection_state="disabled",
                                diagnostics_state="unknown",
                                instance_started=True,
                            )
                        )
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
            for removal in manifest.removals:
                if removal.channel_id in removal_outcomes:
                    continue
                removal_outcomes[removal.channel_id] = RemovalOutcome(
                    removal_token=removal.removal_token,
                    channel_id=removal.channel_id,
                    outcome=(
                        "applied"
                        if removal.channel_id in cached_channel_ids
                        else "already_absent"
                    ),
                )
            if not retryable_failure and self._manifest_store is not None:
                try:
                    committed_channels = tuple(
                        active.spec
                        if (
                            (active := self._active.get(spec.channel_id)) is not None
                            and active.spec.generation == spec.generation
                        )
                        else spec
                        for spec in manifest.channels
                    )
                    self._manifest_store.commit_manifest(
                        replace(manifest, channels=committed_channels)
                    )
                except ChannelManifestStoreError as exc:
                    retryable_failure = True
                    failures.append(
                        {
                            "error_code": "cache_commit_failed",
                            "error_message": str(exc),
                        }
                    )
                    removal_outcomes = {
                        channel_id: RemovalOutcome(
                            removal_token=outcome.removal_token,
                            channel_id=outcome.channel_id,
                            outcome="failed",
                            error_code="cache_commit_failed",
                            error_message=str(exc),
                        )
                        for channel_id, outcome in removal_outcomes.items()
                    }
            outcome = "retryable_failed" if retryable_failure else "applied"
            report = ReconcileReport(
                manifest_revision=manifest.manifest_revision,
                applied_channel_ids=tuple(applied),
                failed_channel_ids=tuple(failed),
                outcome=outcome,
                removal_outcomes=tuple(removal_outcomes.values()),
                failures=tuple(failures),
            )
            if self._manifest_store is not None:
                self._manifest_store.record_reconcile_result(
                    manifest_revision=report.manifest_revision,
                    outcome=report.outcome,
                    applied_channel_ids=report.applied_channel_ids,
                    removal_outcomes=tuple(
                        item.as_payload() for item in report.removal_outcomes
                    ),
                    failures=report.failures,
                )
            if not retryable_failure:
                self._last_applied_manifest_revision = max(
                    self._last_applied_manifest_revision,
                    manifest.manifest_revision,
                )
            return report

    async def reconnect(self, channel_id: str) -> ChannelStatusSnapshot:
        """Replace one current runtime under the same desired generation."""
        return await asyncio.to_thread(self._reconnect_sync, channel_id)

    def _reconnect_sync(self, channel_id: str) -> ChannelStatusSnapshot:
        with self._lock:
            active = self._active.get(channel_id)
            spec = active.spec if active is not None else self._desired.get(channel_id)
            if spec is None or not spec.enabled:
                raise LookupError("channel runtime not found")
            if not self._replace_runtime(spec):
                raise RuntimeError("channel reconnect failed")
            return self._snapshot(
                self._active[channel_id], connection_state="connecting"
            )

    async def handle_status_result(
        self, *, channel_id: str, channel_revision: int, outcome: str
    ) -> None:
        """Quarantine runtimes only for terminal outcomes that invalidate them."""
        await asyncio.to_thread(
            self._handle_status_result_sync,
            channel_id=channel_id,
            channel_revision=channel_revision,
            outcome=outcome,
        )

    def _handle_status_result_sync(
        self, *, channel_id: str, channel_revision: int, outcome: str
    ) -> None:
        with self._lock:
            if outcome == "fatal_owner_mismatch":
                for active_channel_id in tuple(self._active):
                    self._stop_active(active_channel_id, drain=True)
                return
            if outcome != "terminal_channel_removed":
                return
            active = self._active.get(channel_id)
            if (
                active is None
                or active.spec.generation.channel_revision != channel_revision
            ):
                return
            self._stop_active(channel_id, drain=True)

    async def close(self) -> None:
        """Stop all managed runtimes without touching static web relay adapters."""
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            self._closing = True
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
                active.spec = replace(
                    active.spec,
                    provider_runtime=dict(active.metadata),
                )
                if self._manifest_store is not None:
                    self._manifest_store.update_provider_metadata(
                        channel_id=channel_id,
                        provider_identity_fingerprint=(
                            generation.provider_identity_fingerprint
                        ),
                        provider_identity_revision=(
                            generation.provider_identity_revision
                        ),
                        channel_revision=generation.channel_revision,
                        credential_revision=generation.credential_revision,
                        patch=new_values,
                    )
                self._metadata_sink(
                    ProviderMetadataReport(
                        channel_id=channel_id,
                        generation=generation,
                        patch=new_values,
                    )
                )
            return dict(active.metadata)

    def replay_provider_metadata(self) -> None:
        """Replay durable generation-scoped metadata after IM reconnect."""
        with self._lock:
            store = self._manifest_store
            cached = store.load_manifest() if store is not None else None
            if cached is None:
                return
            for item in cached.channels:
                if not item.provider_runtime:
                    continue
                self._metadata_sink(
                    ProviderMetadataReport(
                        channel_id=item.channel_id,
                        generation=ChannelGeneration(
                            provider_identity_fingerprint=(
                                item.provider_identity_fingerprint
                            ),
                            provider_identity_revision=(
                                item.provider_identity_revision
                            ),
                            channel_revision=item.channel_revision,
                            credential_revision=item.credential_revision,
                        ),
                        patch=dict(item.provider_runtime),
                    )
                )

    def retry_pending_activations(self) -> None:
        """Retry Feishu skill activation for current runtimes after IM reconnect."""
        with self._lock:
            if self._activation_policy is None:
                return
            agent_ids = {
                active.spec.agent_id
                for active in self._active.values()
                if active.spec.provider == "feishu"
            }
            for agent_id in sorted(agent_ids):
                self._activation_policy.ensure(agent_id)

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
        checks: tuple[Mapping[str, object], ...] = (),
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
                    checks=checks,
                )
            )
            restart_key = (channel_id, generation)
            if connection_state == "connected":
                self._restart_attempts.pop(restart_key, None)
            elif status_code in {"event_backpressure", "worker_crashed"}:
                self._schedule_runtime_restart(
                    channel_id=channel_id,
                    generation=generation,
                    runtime_incarnation=runtime_incarnation,
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
                checks=_require_diagnostic_checks(payload.get("checks", ())),
            )

        try:
            built = factory(spec, bind_metadata, handle_status)
            if isinstance(built, ProviderRuntimeBuild):
                adapter = built.adapter
                initial_metadata = dict(built.initial_metadata)
            else:
                adapter = built
                initial_metadata = {}
        except Exception as exc:  # noqa: BLE001 - provider reason crosses status seam.
            self._stop_active(spec.channel_id)
            self._emit_start_failure(spec, incarnation=incarnation, error=exc)
            return False
        runtime_name = f"{spec.provider}:{spec.agent_id}"
        if adapter.name != runtime_name:
            self._stop_candidate(adapter)
            self._stop_active(spec.channel_id)
            return False
        self._stop_active(spec.channel_id)
        legacy = self._registry.remove(runtime_name)
        if legacy is not None and legacy is not adapter:
            legacy.stop()
        active = _ActiveRuntime(
            spec=spec,
            adapter=adapter,
            runtime_name=runtime_name,
            incarnation=incarnation,
            metadata=dict(spec.provider_runtime),
        )
        self._active[spec.channel_id] = active
        if initial_metadata:
            self.record_provider_metadata(
                channel_id=spec.channel_id,
                generation=spec.generation,
                patch=initial_metadata,
            )
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
            self._stop_candidate(adapter)
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

    def _schedule_runtime_restart(
        self,
        *,
        channel_id: str,
        generation: ChannelGeneration,
        runtime_incarnation: str,
    ) -> None:
        """Reap a terminal listener and retry its unchanged generation off-loop."""
        scheduled_key = (channel_id, generation, runtime_incarnation)
        if self._closing or scheduled_key in self._restart_scheduled:
            return
        attempt_key = (channel_id, generation)
        completed_attempts = self._restart_attempts.get(attempt_key, 0)
        should_restart = completed_attempts < 3
        attempt = completed_attempts + 1
        if should_restart:
            self._restart_attempts[attempt_key] = attempt
        self._restart_scheduled.add(scheduled_key)

        def restart() -> None:
            time.sleep(0.1 * (2 ** (min(attempt, 3) - 1)))
            with self._lock:
                self._restart_scheduled.discard(scheduled_key)
                active = self._active.get(channel_id)
                if (
                    self._closing
                    or active is None
                    or active.spec.generation != generation
                    or active.incarnation != runtime_incarnation
                ):
                    return
                spec = active.spec
                if should_restart:
                    self._replace_runtime(spec)
                else:
                    self._stop_active(channel_id)

        threading.Thread(
            target=restart,
            name=f"channel-restart-{channel_id[:8]}",
            daemon=True,
        ).start()

    @staticmethod
    def _stop_candidate(adapter: ChannelAdapter) -> None:
        """Best-effort reap for an adapter that never became routable."""
        try:
            stop_invalidated = getattr(adapter, "stop_invalidated", None)
            if callable(stop_invalidated):
                stop_invalidated()
            else:
                adapter.stop()
        except Exception:  # noqa: BLE001 - preserve the primary startup failure.
            pass

    def _emit_start_failure(
        self,
        spec: ManagedChannelSpec,
        *,
        incarnation: str,
        error: Exception,
    ) -> None:
        status_code = (
            error.status_code
            if isinstance(error, ChannelStartupError)
            else "runtime_start_failed"
        )
        status_message = (
            str(error)
            if isinstance(error, ChannelStartupError)
            else "Channel runtime could not start."
        )
        self._status_sink(
            ChannelStatusSnapshot(
                channel_id=spec.channel_id,
                generation=spec.generation,
                runtime_incarnation=incarnation,
                status_sequence=1,
                connection_state="failed",
                status_code=status_code,
                status_message=status_message,
                instance_started=True,
            )
        )

    def _stop_active(
        self, channel_id: str, *, drain: bool = False
    ) -> _ActiveRuntime | None:
        active = self._active.get(channel_id)
        if active is None:
            return None
        self._registry.remove(active.runtime_name, expected=active.adapter)
        stop_invalidated = getattr(active.adapter, "stop_invalidated", None)
        if not drain and callable(stop_invalidated):
            stop_invalidated()
        else:
            active.adapter.stop()
        self._active.pop(channel_id, None)
        return active

    @staticmethod
    def _managed_from_cached(
        item: CachedChannelSpec, *, credentials: Mapping[str, str]
    ) -> ManagedChannelSpec:
        return ManagedChannelSpec(
            channel_id=item.channel_id,
            agent_id=item.agent_id,
            provider=item.provider,
            enabled=item.enabled,
            config=item.config,
            credentials=credentials,
            provider_runtime=item.provider_runtime,
            generation=ChannelGeneration(
                provider_identity_fingerprint=item.provider_identity_fingerprint,
                provider_identity_revision=item.provider_identity_revision,
                channel_revision=item.channel_revision,
                credential_revision=item.credential_revision,
            ),
            credential_envelope=item.credential_envelope,
            credential_key_id=item.credential_key_id,
        )

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


def _require_diagnostic_checks(value: object) -> tuple[Mapping[str, object], ...]:
    """Validate provider-authored checks before they enter the status protocol."""
    if not isinstance(value, (tuple, list)):
        raise TypeError("diagnostic checks must be a sequence")
    checks: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("diagnostic check must be an object")
        checks.append(dict(item))
    return tuple(checks)
