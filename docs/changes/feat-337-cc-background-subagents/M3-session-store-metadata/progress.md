# M3: Session Store Metadata Query — Progress

## Status

Completed. All 8 unit tests pass.

## What was built

### Modified files

| File | Change |
|---|---|
| `src/agent/core/session/jsonl_store.py` | Added `find_session_by_metadata(parent_session_id, match)`; lazy agent_id index; `parent_session_id` kwarg to `create()` |
| `src/agent/core/session/manager.py` | Added `parent_session_id` kwarg to `create_session()`; forwards to store |

### Index design

- `_agent_index: dict[str, list[tuple[str, str | None]]]` maps `agent_id` → list of `(session_id, parent_session_id)`
- Rebuilt lazily on first `find_session_by_metadata` call by scanning all `.jsonl` files
- Incrementally updated in `create()` when metadata contains `agent_id`
- `find_session_by_metadata` iterates indexed entries and filters by `parent_session_id` when provided

### Tests

| Test | Coverage |
|---|---|
| `test_find_by_agent_id_in_main_session` | Index rebuild from main session file |
| `test_find_by_agent_id_in_subagent_session` | Index rebuild from subagent path |
| `test_find_isolated_by_parent_session_id` | Cross-parent isolation with duplicate agent_id |
| `test_find_missing_agent_returns_none` | Missing agent_id → None |
| `test_find_without_agent_id_returns_none` | Match without agent_id → None |
| `test_create_updates_agent_index` | Incremental index on create |
| `test_create_with_parent_session_id_updates_index` | Incremental index for subagent |
| `test_create_with_parent_uses_subagent_path` | Path resolution under `sessions/{parent}/subagents/` |

## Next

M4: Safety Protocol Extension — add `start_command_background()` to `ToolSafetyLike` so BashTool can launch background shell commands through the safety layer.
