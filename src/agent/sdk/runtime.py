"""SDK-owned complete runtime configuration for one durable conversation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from agent.core.session.types import INTERNAL_RUNTIME_KEY

from .prompt import PromptSlots

RUNTIME_FINGERPRINT_SCHEMA = "runtime-v1"


@dataclass(frozen=True, slots=True)
class SessionRuntimeConfig:
    """Describe every session setting that affects a future model turn.

    Args:
        model: Resolved model for every newly admitted run.
        prompt: Fully projected product prompt slots.
        skills: Explicit skills, or ``None`` for default discovery.
        enabled_tools: Explicit future tool allowlist; empty disables all tools.
        features: Explicit feature overrides, or ``None`` for defaults.
        reasoning_effort: Provider-neutral effort for future normal model requests.
    """

    model: str
    prompt: PromptSlots
    skills: list[str] | None
    enabled_tools: list[str]
    features: dict[str, bool] | None
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class SessionRuntimeIdentity:
    """Identify one canonical effective runtime without exposing its contents."""

    runtime_fingerprint: str
    fingerprint_schema: str = RUNTIME_FINGERPRINT_SCHEMA


@dataclass(frozen=True, slots=True)
class SessionRuntimeState:
    """Return the persisted runtime and its current-schema identity."""

    runtime: SessionRuntimeConfig
    identity: SessionRuntimeIdentity


@dataclass(frozen=True, slots=True)
class SessionReconfigureResult:
    """Report the outcome of one durable complete runtime replacement."""

    session_id: str
    changed: bool
    state: SessionRuntimeState


def identify_runtime(runtime: SessionRuntimeConfig) -> SessionRuntimeIdentity:
    """Return a stable identity for the complete effective runtime.

    ``None`` and an explicit empty collection remain distinct because they have
    different discovery semantics. Map keys are sorted while ordered prompt and
    capability lists retain their supplied semantic order.
    """

    payload = {
        "schema": RUNTIME_FINGERPRINT_SCHEMA,
        "model": runtime.model,
        "prompt": {
            slot: [
                {"name": item.name, "text": item.text}
                for item in getattr(runtime.prompt, slot)
            ]
            for slot in ("head", "body", "custom", "tail")
        },
        "skills": runtime.skills,
        "enabled_tools": runtime.enabled_tools,
        "features": runtime.features,
        "reasoning_effort": runtime.reasoning_effort,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return SessionRuntimeIdentity(
        runtime_fingerprint=sha256(encoded.encode()).hexdigest()
    )


def runtime_metadata(
    runtime: SessionRuntimeConfig, *, existing: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Encode SDK runtime fields into core-neutral session metadata."""

    metadata = dict(existing or {})
    metadata["agent_features"] = dict(runtime.features or {})
    metadata[INTERNAL_RUNTIME_KEY] = {
        "model": runtime.model,
        "features": dict(runtime.features) if runtime.features is not None else None,
        "reasoning_effort": runtime.reasoning_effort,
    }
    return metadata


__all__ = [
    "RUNTIME_FINGERPRINT_SCHEMA",
    "SessionRuntimeConfig",
    "SessionRuntimeIdentity",
    "SessionRuntimeState",
    "SessionReconfigureResult",
    "identify_runtime",
    "runtime_metadata",
]
