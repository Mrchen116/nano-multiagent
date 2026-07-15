"""Fail-closed decoding and application of encrypted channel manifests."""

from __future__ import annotations

import asyncio
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
    owner_id = str(body.get("owner_id") or "")
    raw_channels = body.get("channels")
    decoded: list[ManagedChannelSpec] = []
    failures: list[dict[str, object]] = []
    failed_generations: list[tuple[str, ChannelGeneration]] = []
    for raw in raw_channels if isinstance(raw_channels, list) else []:
        if not isinstance(raw, Mapping):
            continue
        channel_id = str(raw.get("channel_id") or "")
        generation: ChannelGeneration | None = None
        try:
            generation = ChannelGeneration(
                provider_identity_fingerprint=str(
                    raw["provider_identity_fingerprint"]
                ),
                provider_identity_revision=int(raw["provider_identity_revision"]),
                channel_revision=int(raw["channel_revision"]),
                credential_revision=int(raw["credential_revision"]),
            )
            if str(raw.get("credential_key_id") or "") != credential_key_id:
                raise ValueError("credential key mismatch")
            envelope = raw.get("credential_envelope")
            if not isinstance(envelope, Mapping):
                raise ValueError("credential envelope missing")
            context = CredentialEnvelopeContext(
                owner_id=owner_id,
                node_id=node_id,
                agent_id=str(raw["agent_id"]),
                channel_id=channel_id,
                provider=str(raw["provider"]),
                credential_revision=generation.credential_revision,
                envelope=envelope,
            )
            credentials = credential_opener(context)
            raw_config = raw.get("config")
            raw_runtime = raw.get("provider_runtime")
            decoded.append(
                ManagedChannelSpec(
                    channel_id=channel_id,
                    agent_id=context.agent_id,
                    provider=context.provider,
                    enabled=raw.get("enabled") is True,
                    config=dict(raw_config) if isinstance(raw_config, Mapping) else {},
                    credentials=credentials,
                    provider_runtime={
                        str(key): str(value)
                        for key, value in raw_runtime.items()
                        if isinstance(key, str) and isinstance(value, str)
                    }
                    if isinstance(raw_runtime, Mapping)
                    else {},
                    generation=generation,
                    credential_envelope=dict(envelope),
                    credential_key_id=credential_key_id,
                )
            )
        except (KeyError, TypeError, ValueError):
            failures.append(
                {
                    "channel_id": channel_id,
                    "error_code": "credential_reentry_required",
                    "error_message": _REENTRY_MESSAGE,
                }
            )
            if generation is not None and channel_id:
                failed_generations.append((channel_id, generation))
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

    raw_removals = body.get("removals")
    removals = tuple(
        ChannelRemovalIntent(
            removal_token=str(raw.get("removal_token") or ""),
            channel_id=str(raw.get("channel_id") or ""),
            agent_id=str(raw.get("agent_id") or ""),
            provider=str(raw.get("provider") or ""),
            deletion_manifest_revision=int(
                raw.get("deletion_manifest_revision") or 0
            ),
        )
        for raw in raw_removals
        if isinstance(raw, Mapping)
    ) if isinstance(raw_removals, list) else ()
    manifest = ChannelManifest(
        owner_id=owner_id,
        node_id=str(body.get("node_id") or node_id),
        manifest_revision=int(body.get("manifest_revision") or 0),
        channels=tuple(decoded),
        removals=removals,
    )

    def reconcile_in_thread():
        return asyncio.run(manager.reconcile(manifest))

    report = await asyncio.to_thread(reconcile_in_thread)
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
