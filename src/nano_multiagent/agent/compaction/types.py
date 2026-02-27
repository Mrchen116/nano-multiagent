from dataclasses import dataclass
from enum import StrEnum

from nano_multiagent.session.entries import SessionEntry


class CompactionReason(StrEnum):
    THRESHOLD = "threshold"
    OVERFLOW = "overflow"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CompactionSettings:
    enabled: bool = True
    context_window: int = 8192
    reserve_tokens: int = 1024
    min_kept_messages: int = 8
    summary_model: str | None = None


@dataclass(frozen=True, slots=True)
class CompactionPlan:
    reason: CompactionReason
    first_kept_event_id: str
    dropped_events: tuple[SessionEntry, ...]
    kept_events: tuple[SessionEntry, ...]


@dataclass(frozen=True, slots=True)
class CompactionResult:
    reason: CompactionReason
    entry_id: str
    first_kept_event_id: str
    summary: str
    dropped_event_ids: tuple[str, ...]
    kept_event_ids: tuple[str, ...]
