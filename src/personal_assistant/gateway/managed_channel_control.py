"""Own managed-channel control policy without owning IM transport state."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Protocol
from uuid import uuid4

from personal_assistant.channels.channel_credentials import (
    GatewayChannelAad,
    GatewayChannelKey,
)
from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.preflight import probe_feishu_runtime
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.channel_manager import (
    ChannelManager,
    ChannelStatusSnapshot,
    FeishuActivationPolicy,
    ManagedChannelSpec,
    ProviderMetadataReport,
    ProviderRuntimeBuild,
)
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from personal_assistant.gateway.channel_manifest_apply import (
    CredentialEnvelopeContext,
    apply_channel_manifest_payload,
)
from personal_assistant.gateway.channel_manifest_store import (
    CachedChannelSpec,
    ChannelManifestStore,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry

_log = logging.getLogger(__name__)


class ChannelStatusDirective(Enum):
    """Tell the receive owner whether a status result ends this connection."""

    CONTINUE = "continue"
    CLOSE_CONNECTION = "close_connection"


@dataclass(frozen=True, slots=True)
class ChannelStatusEmission:
    """One durable channel-status projection ready for the existing wire FIFO."""

    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ChannelRuntimeMetadataEmission:
    """One provider metadata projection ready for the existing wire FIFO."""

    payload: Mapping[str, object]


ManagedChannelEmission = ChannelStatusEmission | ChannelRuntimeMetadataEmission
EmissionSender = Callable[[ManagedChannelEmission], None]
ChannelManifestHandler = Callable[
    [Mapping[str, object]], Awaitable[Mapping[str, object]]
]
ChannelReconnectHandler = Callable[[str, int], Awaitable[None]]
ChannelReconcileAckHandler = Callable[[Mapping[str, object]], None]
ChannelStatusResultHandler = Callable[
    [Mapping[str, object]], Awaitable[ChannelStatusDirective]
]


class ManagedChannelConnectionSender(Protocol):
    """Expose only the current IM connection operations needed after registration."""

    async def send_json(self, message_type: str, payload: Mapping[str, object]) -> None:
        """Enter one frame through the owning connection FIFO."""

    def has_pending_request(self, request_id: str) -> bool:
        """Report whether this connection already owns a correlated request."""


ChannelRegisterReadyHandler = Callable[
    [ManagedChannelConnectionSender], Awaitable[None]
]


class ManagedChannelEmissionSource:
    """Forward typed provider emissions without retaining transport or durable state."""

    def __init__(self) -> None:
        self._sender: EmissionSender | None = None
        self._lock = Lock()

    def bind_sender(self, sender: EmissionSender) -> None:
        """Attach the current IM loop's FIFO entrypoint."""

        with self._lock:
            self._sender = sender

    def publish(self, emission: ManagedChannelEmission) -> None:
        """Hand one already-durable emission to the current transport owner."""

        with self._lock:
            sender = self._sender
        if sender is not None:
            sender(emission)


@dataclass(frozen=True, slots=True)
class ManagedChannelBindings:
    """Immutable managed-channel handlers consumed by IMConnectionManager."""

    apply_manifest: ChannelManifestHandler
    reconnect: ChannelReconnectHandler
    acknowledge_reconcile: ChannelReconcileAckHandler
    handle_status_result: ChannelStatusResultHandler
    reconcile_after_register: ChannelRegisterReadyHandler
    emissions: ManagedChannelEmissionSource


class ManagedChannelControl:
    """Compose managed runtime lifecycle, cache policy, and typed IM bindings."""

    def __init__(
        self,
        *,
        node_id: str,
        channel_key: GatewayChannelKey,
        manifest_store: ChannelManifestStore,
        registry: ChannelRegistry,
        on_inbound: Callable[..., None],
        agent_config_sync: IMAgentConfigSync,
        group_context_store: object,
        permission_decision_callback: Callable[..., None] | None,
    ) -> None:
        self._node_id = node_id
        self._channel_key = channel_key
        self._manifest_store = manifest_store
        self._emissions = ManagedChannelEmissionSource()
        self._manager = ChannelManager(
            registry=registry,
            on_inbound=on_inbound,
            provider_factories={"feishu": self._build_managed_feishu},
            status_sink=self._record_status,
            metadata_sink=self._record_metadata,
            activation_policy=FeishuActivationPolicy(
                lambda agent_id: agent_config_sync.ensure_agent_skills_enabled(
                    agent_id, lark_skill_names()
                )
            ),
            manifest_store=manifest_store,
            credential_opener=self._open_cached_channel,
        )
        self._group_context_store = group_context_store
        self._permission_decision_callback = permission_decision_callback

    async def start_cached(self) -> None:
        """Start encrypted cached runtimes before IM connectivity is available."""

        await self._manager.start_cached()

    async def close(self) -> None:
        """Stop managed runtimes before their final emitted state can be discarded."""

        await self._manager.close()

    def connection_bindings(self) -> ManagedChannelBindings:
        """Return the complete typed downstream control surface for one IM connection."""

        return ManagedChannelBindings(
            apply_manifest=self.apply_manifest,
            reconnect=self.reconnect,
            acknowledge_reconcile=self.acknowledge_reconcile,
            handle_status_result=self.handle_status_result,
            reconcile_after_register=self.reconcile_after_register,
            emissions=self._emissions,
        )

    def _open_cached_channel(self, item: CachedChannelSpec) -> Mapping[str, str]:
        cached = self._manifest_store.load_manifest()
        if cached is None:
            raise ValueError("channel manifest cache is empty")
        return self._channel_key.open(
            envelope=item.credential_envelope,
            aad=GatewayChannelAad(
                owner_id=cached.owner_id,
                node_id=cached.node_id,
                agent_id=item.agent_id,
                channel_id=item.channel_id,
                provider=item.provider,
                credential_revision=item.credential_revision,
            ),
        )

    async def apply_manifest(self, body: Mapping[str, object]) -> Mapping[str, object]:
        """Decrypt and apply an IM manifest through the existing lifecycle owner."""

        def open_credentials(context: CredentialEnvelopeContext) -> Mapping[str, str]:
            return self._channel_key.open(
                envelope=context.envelope,
                aad=GatewayChannelAad(
                    owner_id=context.owner_id,
                    node_id=context.node_id,
                    agent_id=context.agent_id,
                    channel_id=context.channel_id,
                    provider=context.provider,
                    credential_revision=context.credential_revision,
                ),
            )

        return await apply_channel_manifest_payload(
            body=body,
            node_id=self._node_id,
            credential_key_id=self._channel_key.key_id,
            credential_opener=open_credentials,
            manager=self._manager,
        )

    async def reconnect(self, channel_id: str, channel_revision: int) -> None:
        """Reconnect one current cached generation and reject stale requests."""

        cached = self._manifest_store.load_manifest()
        desired = (
            next(
                (item for item in cached.channels if item.channel_id == channel_id),
                None,
            )
            if cached is not None
            else None
        )
        if desired is None or desired.channel_revision != channel_revision:
            raise LookupError("channel reconnect revision is stale")
        await self._manager.reconnect(channel_id)

    def acknowledge_reconcile(self, payload: Mapping[str, object]) -> None:
        """Persist IM acknowledgement of a reconcile result."""

        outcomes = payload.get("removal_token_outcomes")
        self._manifest_store.ack_reconcile_result(
            head_outcome=str(payload.get("head_outcome") or ""),
            manifest_revision=int(payload.get("manifest_revision") or 0),
            removal_token_outcomes=[
                item for item in outcomes if isinstance(item, Mapping)
            ]
            if isinstance(outcomes, list)
            else [],
        )

    async def handle_status_result(
        self, payload: Mapping[str, object]
    ) -> ChannelStatusDirective:
        """Apply one durable status ACK and return its receive-stack directive."""

        ack = self._manifest_store.apply_channel_status_result(
            request_id=str(payload.get("request_id") or ""),
            outcome=str(payload.get("outcome") or ""),
        )
        if ack is None:
            return ChannelStatusDirective.CONTINUE
        await self._manager.handle_status_result(
            channel_id=ack.channel_id,
            channel_revision=ack.channel_revision,
            outcome=ack.outcome,
        )
        if ack.outcome == "fatal_owner_mismatch":
            return ChannelStatusDirective.CLOSE_CONNECTION
        if ack.next_payload is not None:
            if ack.outcome == "retryable_store_busy":
                task = asyncio.create_task(
                    self._publish_pending_status_after_delay(ack.next_payload),
                    name=f"channel-status-retry:{ack.channel_id}",
                )
                task.add_done_callback(self._log_status_retry)
            else:
                self._emissions.publish(ChannelStatusEmission(ack.next_payload))
        return ChannelStatusDirective.CONTINUE

    async def reconcile_after_register(
        self, sender: ManagedChannelConnectionSender
    ) -> None:
        """Replay durable channel projections through the acknowledged connection FIFO."""

        for status in self._manifest_store.pending_channel_statuses():
            request_id = status.get("request_id")
            if isinstance(request_id, str) and sender.has_pending_request(request_id):
                continue
            await sender.send_json("channel.status", status)
        self._manager.replay_provider_metadata()
        self._manager.retry_pending_activations()
        pending_result = self._manifest_store.pending_reconcile_result()
        if pending_result is None:
            return
        payload = {
            "request_id": uuid4().hex,
            "node_id": self._node_id,
            **pending_result,
        }
        await sender.send_json("channel.reconcile.result", payload)

    async def _publish_pending_status_after_delay(
        self, payload: Mapping[str, object]
    ) -> None:
        await asyncio.sleep(0.5)
        request_id = str(payload.get("request_id") or "")
        if any(
            status.get("request_id") == request_id
            for status in self._manifest_store.pending_channel_statuses()
        ):
            self._emissions.publish(ChannelStatusEmission(payload))

    @staticmethod
    def _log_status_retry(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            _log.warning("channel status retry failed", exc_info=True)

    def _record_status(self, snapshot: ChannelStatusSnapshot) -> None:
        generation = snapshot.generation
        payload = self._manifest_store.record_channel_status(
            {
                "request_id": uuid4().hex,
                "node_id": self._node_id,
                "channel_id": snapshot.channel_id,
                "provider_identity_fingerprint": generation.provider_identity_fingerprint,
                "provider_identity_revision": generation.provider_identity_revision,
                "channel_revision": generation.channel_revision,
                "credential_revision": generation.credential_revision,
                "runtime_incarnation": snapshot.runtime_incarnation,
                "status_sequence": snapshot.status_sequence,
                "instance_started": snapshot.instance_started,
                "connection_state": snapshot.connection_state,
                "diagnostics_state": snapshot.diagnostics_state,
                "status_code": snapshot.status_code,
                "status_message": snapshot.status_message,
                "checks": [dict(item) for item in snapshot.checks],
            }
        )
        if payload is not None:
            self._emissions.publish(ChannelStatusEmission(payload))

    def _record_metadata(self, report: ProviderMetadataReport) -> None:
        generation = report.generation
        self._emissions.publish(
            ChannelRuntimeMetadataEmission(
                {
                    "request_id": uuid4().hex,
                    "node_id": self._node_id,
                    "channel_id": report.channel_id,
                    "provider_runtime_patch": dict(report.patch),
                    "provider_identity_fingerprint": generation.provider_identity_fingerprint,
                    "provider_identity_revision": generation.provider_identity_revision,
                    "channel_revision": generation.channel_revision,
                    "credential_revision": generation.credential_revision,
                }
            )
        )

    def _build_managed_feishu(
        self,
        spec: ManagedChannelSpec,
        metadata_binder: Callable[[dict[str, str]], dict[str, str] | None],
        status_handler: Callable[..., bool],
    ) -> ProviderRuntimeBuild:
        app_id = str(spec.config.get("app_id") or "").strip()
        app_secret = str(spec.credentials.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            raise ValueError("Feishu credentials are required")
        metadata = dict(spec.provider_runtime)
        preflight = probe_feishu_runtime(
            app_id=app_id, app_secret=app_secret, domain="https://open.feishu.cn"
        )

        def bind_owner(_channel_name: str, sender_open_id: str) -> str | None:
            bound = metadata_binder({"owner_open_id": sender_open_id})
            return bound.get("owner_open_id") if bound else None

        def forward_status(worker_status: object) -> None:
            status_handler(
                status_sequence=getattr(worker_status, "status_sequence"),
                connection_state=getattr(worker_status, "connection_state"),
                diagnostics_state=getattr(
                    worker_status, "diagnostics_state", "unknown"
                ),
                status_code=getattr(worker_status, "status_code", None),
                status_message=getattr(worker_status, "status_message", None),
                checks=getattr(worker_status, "checks", ()),
            )

        return ProviderRuntimeBuild(
            adapter=FeishuAdapter(
                name=f"feishu:{spec.agent_id}",
                app_id=app_id,
                app_secret=app_secret,
                bot_open_id=metadata.get("bot_open_id") or preflight.bot_open_id,
                owner_open_id=metadata.get("owner_open_id"),
                owner_open_id_binder=bind_owner,
                permission_decision_callback=self._permission_decision_callback,
                group_context_store=self._group_context_store,
                status_callback=forward_status,
            ),
            initial_metadata={"bot_open_id": preflight.bot_open_id},
        )
