# M9: Cleanup — Progress

## 2026-04-28

### Source code cleanup

- `src/coding_cli/commands.py`
  - `_send_message_via_sse()` now emits `tool_start`/`tool_exec_started` live previews in non-TTY mode (matching old behavior for test assertions)
  - Raises `RuntimeError` on failed runs (restoring old error path through `_print_repl_turn_error`)
  - Removed all imports of `_supports_async_repl_events`, `_send_message_with_async_events`, `_consume_async_run_events`
  - REPL unconditionally uses SSE path (`_send_message_via_sse`)

- `src/coding_cli/events/repl_events.py`
  - Removed `send_message_with_async_events()` and all its internal helpers (`_extract_run_id`, `_clip_events_after_turn_end`, `_normalize_session_event`, `consume_async_run_events`, `_build_repl_view`)
  - Removed `supports_async_repl_events()`
  - Removed unused imports (`ServerClient`, `sys`, `EventDedupeWindow`, `ReplPerfTracker`, `ReplRenderPhaseMachine`, `_consume_event_for_run`, `_normalize_session_event_from_pipeline`, `_build_repl_view_model_from_pipeline`)
  - Kept: `_event_preview_line`, `_build_ordered_repl_updates`, `merge_text_delta`, `print_event_preview`, `_format_status_progress`, `_format_retry_progress`, and all tool-line helpers (still used by `commands.py`)

### Test fixture updates

- `tests/unit/test_cli_main.py`
  - Removed 3 direct `send_message_with_async_events` tests
  - Removed 6 `consume_async_run_events` direct tests
  - Removed 3 REPL tests that tested obsolete polling behaviors (multi-poll dedupe, delayed terminal run_status, retry progress across polls)
  - Renamed 2 REPL tests whose names misleadingly referenced `send_message_with_async_events`
  - Updated `_AsyncUsageEventingStubClient` to yield `usage` in SSE `run_status` event
  - Updated `_send_message_via_sse` assertion in `test_run_cli_repl_uses_async_events_with_run_filter_and_dedup`
  - All 90 tests in `test_cli_main.py` pass

- `tests/unit/test_cli_refactor_boundaries.py`
  - Updated `test_commands_delegates_repl_event_helpers_to_apps_module` to reference existing functions
  - Fixed syntax error in function signature

### Removed obsolete files

- `tests/unit/test_server_message_route.py` — tested old `_to_message_response` (removed in M5)
- `tests/e2e/test_parallel_tools_and_injection_e2e.py` — imported removed `ToolBatch`/`ToolExecutor`
- `tests/e2e/test_cli_text_streaming_and_injection_e2e.py` — tested removed `send_message_with_async_events`/`consume_async_run_events`
- `tests/unit/test_cli_main.py.bak` — transformation backup file

### Verification

- `pytest tests/unit/test_cli_main.py` — 90 passed
- `pytest tests/unit/test_cli_refactor_boundaries.py` — 7 passed (3 pre-existing unrelated failures in release playbook tests)
- `pytest tests/unit -q --timeout=30` — 351 passed, 1 failed (pre-existing `test_agent_runtime_m246.py` failure unrelated to feat-338)

### Remaining old API references (out of scope for M9, belong to other features)

- `tests/im_service/integration/test_m103_im_gateway_e2e.py` — fake kernel client still uses old method names
- `tests/im_service/integration/test_m136_group_chat_flow.py` — same
- `tests/integration/test_cli_http_flow_integration.py` — same
- `tests/unit/test_sdk_client.py` — still has `send_message` test
- `tests/contract/test_personal_assistant_kernel_client_contract.py` — still references old methods in contract whitelist

These are integration/contract tests for other components and should be updated in their respective feature workstreams.
