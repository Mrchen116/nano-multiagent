"""Core-owned value objects for per-conversation session ownership."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from agent.core.session.entries import SessionEntry

if TYPE_CHECKING:
    from agent.core.agent.run_control import RunController

INTERNAL_METADATA_PREFIX = "__nano_internal_"
INTERNAL_PROMPT_SLOTS_KEY = "__nano_internal_prompt_slots_v1__"
INTERNAL_RUNTIME_KEY = "__nano_internal_runtime_v1__"
_PROMPT_SLOT_NAMES = ("head", "body", "custom", "tail")


class SessionNotFoundError(ValueError):
    """Signal that no transcript exists at a requested session address."""


class SessionAddressMismatch(RuntimeError):
    """Signal that a stable session id was reopened at a different address."""


class ConversationClosed(RuntimeError):
    """Signal that an operation was admitted after conversation draining began."""


@dataclass(frozen=True, slots=True)
class SessionRef:
    """Bind one session id to its canonical workspace and optional parent."""

    session_id: str
    workspace_root: Path
    parent_session_id: str | None = None

    def __post_init__(self) -> None:
        normalized_id = self.session_id.strip()
        if not normalized_id:
            raise ValueError("session_id must be a non-empty string")
        object.__setattr__(self, "session_id", normalized_id)
        object.__setattr__(
            self,
            "workspace_root",
            self.workspace_root.expanduser().resolve(),
        )
        if self.parent_session_id is not None:
            normalized_parent = self.parent_session_id.strip()
            object.__setattr__(
                self,
                "parent_session_id",
                normalized_parent or None,
            )


@dataclass(frozen=True, slots=True)
class PromptSlotText:
    """Store one named plain-text prompt segment in a core-owned seed."""

    name: str
    text: str


@dataclass(frozen=True, slots=True)
class PromptSlotSeed:
    """Persist the four product prompt slots without importing the SDK layer."""

    head: tuple[PromptSlotText, ...] = ()
    body: tuple[PromptSlotText, ...] = ()
    custom: tuple[PromptSlotText, ...] = ()
    tail: tuple[PromptSlotText, ...] = ()

    def to_metadata(self) -> dict[str, list[dict[str, str]]]:
        """Encode the seed into the reserved metadata payload."""

        return {
            slot: [
                {"name": item.name, "text": item.text} for item in getattr(self, slot)
            ]
            for slot in _PROMPT_SLOT_NAMES
        }

    @classmethod
    def from_metadata(cls, value: object) -> "PromptSlotSeed":
        """Decode one reserved payload, returning an empty seed for old archives."""

        if not isinstance(value, Mapping):
            return cls()
        decoded: dict[str, tuple[PromptSlotText, ...]] = {}
        for slot in _PROMPT_SLOT_NAMES:
            raw_items = value.get(slot)
            items: list[PromptSlotText] = []
            if isinstance(raw_items, Sequence) and not isinstance(
                raw_items, (str, bytes)
            ):
                for raw in raw_items:
                    if not isinstance(raw, Mapping):
                        continue
                    name = raw.get("name")
                    text = raw.get("text")
                    if isinstance(name, str) and isinstance(text, str):
                        items.append(PromptSlotText(name=name, text=text))
            decoded[slot] = tuple(items)
        return cls(**decoded)


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """Represent the resolved persistent configuration for one transcript."""

    session_id: str
    created_at: str
    workspace_root: Path
    runtime_model: str | None = None
    system_prompt: str | None = None
    skills: tuple[str, ...] | None = None
    tool_allowlist: tuple[str, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NewSession:
    """Describe the complete immutable seed for a new conversation."""

    workspace_root: Path
    runtime_model: str | None = None
    runtime_features: dict[str, bool] | None = None
    runtime_reasoning_effort: str | None = None
    title: str | None = None
    system_prompt: str | None = None
    skills: tuple[str, ...] | None = None
    tool_allowlist: tuple[str, ...] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    parent_session_id: str | None = None
    prompt_seed: PromptSlotSeed = field(default_factory=PromptSlotSeed)


@dataclass(frozen=True, slots=True)
class TurnRequest:
    """Carry one complete turn request into a bound conversation session."""

    parts: Sequence[Mapping[str, Any]]
    llm_session_id: str | None = None
    run_id: str | None = None
    controller: "RunController | None" = None
    origin: Any = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalMessage:
    """Describe one durable message appended outside a model turn."""

    role: str
    content: str
    message_id: str | None = None
    turn_id: str | None = None
    parts: Sequence[Mapping[str, Any]] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class AppendMessageResult:
    """Describe whether an external append created a new persisted turn."""

    entry: SessionEntry
    created: bool


def strip_internal_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the SDK-safe projection of one persistent metadata mapping."""

    return {
        key: value
        for key, value in dict(metadata or {}).items()
        if not key.startswith(INTERNAL_METADATA_PREFIX)
    }


def internal_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    prompt_seed: PromptSlotSeed,
) -> dict[str, Any]:
    """Sanitize caller metadata and attach the kernel-owned prompt seed."""

    sanitized = strip_internal_metadata(metadata)
    sanitized[INTERNAL_PROMPT_SLOTS_KEY] = prompt_seed.to_metadata()
    return sanitized
