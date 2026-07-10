# M3: Session Store Metadata Query — Roadpoint Plan

## Goal

Enable `agent_id` → session recovery after kernel restart by adding metadata query to `JsonlSessionStore`.

## Roadpoints

### RP1: JsonlSessionStore agent_id index
- Add `_agent_index: dict[str, tuple[str, str | None]]` (`agent_id` → `(session_id, parent_session_id)`)
- Build index lazily on first `find_session_by_metadata` call
- Incrementally update index in `create()` when metadata contains `agent_id`
- Scan scope: `sessions/*.jsonl` + `sessions/*/subagents/*.jsonl`

### RP2: find_session_by_metadata API
- Signature: `find_session_by_metadata(*, parent_session_id: str | None, match: Mapping[str, Any]) -> str | None`
- Match all key/value pairs in `match` against session_created metadata
- Scope to `parent_session_id` when provided (prevents cross-parent leakage)
- Return `session_id` or `None`

### RP3: parent_session_id in create_session
- `JsonlSessionStore.create()` gains `parent_session_id` kwarg
- `SessionManager.create_session()` gains `parent_session_id` kwarg
- Forward to store so subagent sessions land in `sessions/{parent}/subagents/`

### RP4: Tests
- Unit test for index build from existing files
- Unit test for incremental index update on create
- Unit test for parent_session_id scope isolation
- Unit test for missing agent_id fallback

## Exit Criteria
- `pytest tests/unit/agent/session/ -q` passes
- Index correctly maps `agent_id` to session across parent boundaries
- Missing agent returns `None`, never creates a phantom session
