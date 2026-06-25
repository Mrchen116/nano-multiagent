"""Compaction domain contracts shared by planner/summarizer/applier."""

from dataclasses import dataclass
from enum import StrEnum

from agent.core.session.entries import SessionEntry


class CompactionReason(StrEnum):
    """Enumerate reasons that can trigger context compaction."""

    THRESHOLD = "threshold"
    OVERFLOW = "overflow"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CompactionSettings:
    """Configure runtime compaction thresholds and summarization behavior."""

    enabled: bool = True
    context_window: int = 200_000
    # feat-436: 提到 20480——4096 不足以覆盖压缩摘要生成 + 下一轮回复的额度，压完仍可能贴窗口上沿。
    reserve_tokens: int = 20_480
    min_kept_messages: int = 8
    summary_model: str | None = None


@dataclass(frozen=True, slots=True)
class CompactionPlan:
    """Describe which historical events are dropped/kept in one compaction pass."""

    reason: CompactionReason
    first_kept_event_id: str
    dropped_events: tuple[SessionEntry, ...]
    kept_events: tuple[SessionEntry, ...]


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Report persisted compaction outcome returned to callers."""

    reason: CompactionReason
    entry_id: str
    first_kept_event_id: str
    summary: str
    dropped_event_ids: tuple[str, ...]
    kept_event_ids: tuple[str, ...]
