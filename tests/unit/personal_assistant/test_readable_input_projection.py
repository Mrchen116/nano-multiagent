"""Exact provenance handoff from PA model parts to readable chat history."""

from personal_assistant.gateway.readable_input_projection import (
    ReadableInputProjectionStore,
)


def test_exact_match_resolves_once_without_parsing_header() -> None:
    store = ReadableInputProjectionStore()
    model = "[Feishu Mon 2026-08-10 09:17 CST] [Alice] hello"
    readable = "[Alice] hello"
    store.stage_or_replace("session-1", model, readable)

    assert store.resolve_exact("session-1", model) == readable
    assert store.resolve_exact("session-1", model) is None


def test_new_normal_admission_replaces_unconsumed_slot() -> None:
    store = ReadableInputProjectionStore()
    store.stage_or_replace("session-1", "model-1", "raw-1")
    store.stage_or_replace("session-1", "model-2", "raw-2")

    assert store.resolve_exact("session-1", "model-1") is None
    assert store.resolve_exact("session-1", "model-2") == "raw-2"


def test_no_match_preserves_slot_and_header_shaped_user_text() -> None:
    store = ReadableInputProjectionStore()
    model = "[Web IM Mon 2026-08-10 09:17 CST] actual body"
    raw_header_shaped = "[Feishu Mon 2026-08-10 09:17 CST] user wrote this"
    store.stage_or_replace("session-1", model, raw_header_shaped)

    assert store.resolve_exact("session-1", raw_header_shaped) is None
    assert store.resolve_exact("session-1", model) == raw_header_shaped


def test_rollback_only_removes_the_matching_staged_projection() -> None:
    store = ReadableInputProjectionStore()
    store.stage_or_replace("session-1", "model-1", "raw-1")

    store.rollback("session-1", "different")
    assert store.resolve_exact("session-1", "model-1") == "raw-1"

    store.stage_or_replace("session-1", "model-2", "raw-2")
    store.rollback("session-1", "model-2")
    assert store.resolve_exact("session-1", "model-2") is None
