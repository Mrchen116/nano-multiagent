"""Fail-closed decoding and application of encrypted channel manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ChannelRemovalIntent,
    ManagedChannelSpec,
)


_REENTRY_MESSAGE = "Channel credentials must be entered again."
_INVALID_MANIFEST_MESSAGE = "Channel manifest is incomplete or invalid."


@dataclass(frozen=True, slots=True)
class CredentialEnvelopeContext:
    """Describe the complete AAD scope needed to open one desired credential."""

    owner_id: str
    node_id: str
    agent_id: str
    channel_id: str
    provider: str
    credential_revision: int
    envelope: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _PreparedChannel:
    channel_id: str
    agent_id: str
    provider: str
    enabled: bool
    config: Mapping[str, object]
    provider_runtime: Mapping[str, str]
    generation: ChannelGeneration
    credential_envelope: Mapping[str, object]
    credential_key_id: str


class _ManifestStructureError(ValueError):
    """Identify a malformed complete snapshot before any lifecycle mutation."""

    def __init__(self, *, channel_id: str = "") -> None:
        super().__init__(_INVALID_MANIFEST_MESSAGE)
        self.channel_id = channel_id


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _ManifestStructureError(channel_id=str(payload.get("channel_id") or ""))
    return value.strip()


def _required_revision(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if type(value) is not int or value <= 0:
        raise _ManifestStructureError(channel_id=str(payload.get("channel_id") or ""))
    return value


def _prepare_channel(
    raw: Mapping[str, object],
    *,
    node_id: str,
) -> _PreparedChannel:
    channel_id = _required_string(raw, "channel_id")
    item_node_id = _required_string(raw, "node_id")
    enabled = raw.get("enabled")
    config = raw.get("config")
    provider_runtime = raw.get("provider_runtime")
    envelope = raw.get("credential_envelope")
    if (
        item_node_id != node_id
        or type(enabled) is not bool
        or not isinstance(config, Mapping)
        or not isinstance(provider_runtime, Mapping)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in provider_runtime.items()
        )
        or not isinstance(envelope, Mapping)
    ):
        raise _ManifestStructureError(channel_id=channel_id)
    generation = ChannelGeneration(
        provider_identity_fingerprint=_required_string(
            raw, "provider_identity_fingerprint"
        ),
        provider_identity_revision=_required_revision(
            raw, "provider_identity_revision"
        ),
        channel_revision=_required_revision(raw, "channel_revision"),
        credential_revision=_required_revision(raw, "credential_revision"),
    )
    return _PreparedChannel(
        channel_id=channel_id,
        agent_id=_required_string(raw, "agent_id"),
        provider=_required_string(raw, "provider"),
        enabled=enabled,
        config=dict(config),
        provider_runtime={
            str(key): str(value) for key, value in provider_runtime.items()
        },
        generation=generation,
        credential_envelope=dict(envelope),
        credential_key_id=_required_string(raw, "credential_key_id"),
    )


def _prepare_removal(raw: Mapping[str, object]) -> ChannelRemovalIntent:
    return ChannelRemovalIntent(
        removal_token=_required_string(raw, "removal_token"),
        channel_id=_required_string(raw, "channel_id"),
        agent_id=_required_string(raw, "agent_id"),
        provider=_required_string(raw, "provider"),
        deletion_manifest_revision=_required_revision(
            raw, "deletion_manifest_revision"
        ),
    )


def _failure_result(
    *,
    channel_id: str,
    error_code: str,
    error_message: str,
) -> Mapping[str, object]:
    return {
        "outcome": "retryable_failed",
        "applied_channel_ids": [],
        "removal_outcomes": [],
        "failures": [
            {
                "channel_id": channel_id,
                "error_code": error_code,
                "error_message": error_message,
            }
        ],
    }


async def apply_channel_manifest_payload(
    *,
    body: Mapping[str, object],
    node_id: str,
    credential_key_id: str,
    credential_opener: Callable[[CredentialEnvelopeContext], Mapping[str, str]],
    manager: ChannelManager,
) -> Mapping[str, object]:
    """Decode a complete manifest and apply it only when every item opens.

    Args:
        body: Raw `channel.reconcile` payload received from IM.
        node_id: Configured local Gateway node identity.
        credential_key_id: Current local private-key identity.
        credential_opener: Fail-closed envelope opener for the local private key.
        manager: Sole runtime lifecycle owner.

    Returns:
        Wire-ready reconcile result. Any credential failure returns a retryable
        result without invoking the lifecycle manager with an incomplete snapshot.
    """
    try:
        owner_id = _required_string(body, "owner_id")
        payload_node_id = _required_string(body, "node_id")
        manifest_revision = _required_revision(body, "manifest_revision")
        raw_channels = body.get("channels")
        raw_removals = body.get("removals")
        if (
            payload_node_id != node_id
            or not isinstance(raw_channels, list)
            or not isinstance(raw_removals, list)
            or not all(isinstance(raw, Mapping) for raw in raw_channels)
            or not all(isinstance(raw, Mapping) for raw in raw_removals)
        ):
            raise _ManifestStructureError()
        prepared = tuple(_prepare_channel(raw, node_id=node_id) for raw in raw_channels)
        removals = tuple(_prepare_removal(raw) for raw in raw_removals)
    except _ManifestStructureError as exc:
        return _failure_result(
            channel_id=exc.channel_id,
            error_code="manifest_invalid",
            error_message=_INVALID_MANIFEST_MESSAGE,
        )

    decoded: list[ManagedChannelSpec] = []
    failures: list[dict[str, object]] = []
    failed_generations: list[tuple[str, ChannelGeneration]] = []
    for item in prepared:
        try:
            if item.credential_key_id != credential_key_id:
                raise ValueError("credential key mismatch")
            context = CredentialEnvelopeContext(
                owner_id=owner_id,
                node_id=node_id,
                agent_id=item.agent_id,
                channel_id=item.channel_id,
                provider=item.provider,
                credential_revision=item.generation.credential_revision,
                envelope=item.credential_envelope,
            )
            credentials = credential_opener(context)
            if not isinstance(credentials, Mapping) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in credentials.items()
            ):
                raise ValueError("credential payload invalid")
            decoded.append(
                ManagedChannelSpec(
                    channel_id=item.channel_id,
                    agent_id=item.agent_id,
                    provider=item.provider,
                    enabled=item.enabled,
                    config=item.config,
                    credentials=dict(credentials),
                    provider_runtime=item.provider_runtime,
                    generation=item.generation,
                    credential_envelope=item.credential_envelope,
                    credential_key_id=credential_key_id,
                )
            )
        except (TypeError, ValueError):
            failures.append(
                {
                    "channel_id": item.channel_id,
                    "error_code": "credential_reentry_required",
                    "error_message": _REENTRY_MESSAGE,
                }
            )
            failed_generations.append((item.channel_id, item.generation))
    if failures:
        for channel_id, generation in failed_generations:
            manager.report_credential_reentry(
                channel_id=channel_id,
                generation=generation,
            )
        return {
            "outcome": "retryable_failed",
            "applied_channel_ids": [],
            "removal_outcomes": [],
            "failures": failures,
        }

    manifest = ChannelManifest(
        owner_id=owner_id,
        node_id=node_id,
        manifest_revision=manifest_revision,
        channels=tuple(decoded),
        removals=removals,
    )

    report = await manager.reconcile(manifest)
    runtime_failures = [
        {
            "channel_id": channel_id,
            "error_code": "runtime_apply_failed",
        }
        for channel_id in report.failed_channel_ids
    ]
    return {
        "outcome": report.outcome,
        "applied_channel_ids": list(report.applied_channel_ids),
        "removal_outcomes": [item.as_payload() for item in report.removal_outcomes],
        "failures": [*report.failures, *runtime_failures],
    }
