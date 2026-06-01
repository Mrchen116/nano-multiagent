from dataclasses import fields

from agent.core.agent.compaction.types import (
    CompactionReason,
    CompactionResult,
    CompactionSettings,
)
from agent.core.agent.runtime import AgentRuntime


def test_compaction_reason_values_contract() -> None:
    assert [reason.value for reason in CompactionReason] == [
        "threshold",
        "overflow",
        "manual",
    ]


def test_compaction_settings_fields_contract() -> None:
    assert [field.name for field in fields(CompactionSettings)] == [
        "enabled",
        "context_window",
        "reserve_tokens",
        "min_kept_messages",
        "summary_model",
    ]


def test_compaction_result_fields_contract() -> None:
    assert [field.name for field in fields(CompactionResult)] == [
        "reason",
        "entry_id",
        "first_kept_event_id",
        "summary",
        "dropped_event_ids",
        "kept_event_ids",
    ]


def test_runtime_exposes_manual_compact_api_contract() -> None:
    assert callable(getattr(AgentRuntime, "compact", None))
