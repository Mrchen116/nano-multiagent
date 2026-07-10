# M6: Client Streaming — Progress

## Completed Roadpoints

### RP1: coding_cli ServerClient ✅
- Added `submit_message(session_id, text, priority, message_id)` — sync POST /messages, returns `{run_id, anchor_sequence, injected, status}`.
- Added `stream_session(session_id, last_event_id)` — async generator over GET /stream, yields decoded events with `_id` field.
- Added `_IncrementalSseParser` line-level state machine:
  - Cross-chunk frame boundaries supported.
  - Multi-line data supported.
  - Comment lines (`:`) skipped.
  - Malformed frames silently dropped.
- Old methods (`send_message`, `send_message_async`, `stream_session_events`) kept with deprecation notes for backward compat during transition; will be removed in M9.

### RP2: personal_assistant KernelApiClient ✅
- Added `submit_message(session_id, texts, image_urls, priority)` — sync POST /messages, supports image parts and priority.
- Added `stream_session(session_id, last_event_id)` — async generator over GET /stream.
- Added `_IncrementalSseParser` (mirrored from coding_cli).
- Old methods (`send_message_async`, `stream_session_events`) kept with deprecation notes; will be removed in M9.

### RP3: agent.platform.sdk ServerClient ✅
- Added `submit_message()` and `stream_session()` to the canonical SDK client.
- Added `_IncrementalSseParser`.
- Old methods kept with deprecation notes.

### RP4: Tests ✅
- Updated `tests/contract/test_personal_assistant_kernel_client_contract.py` to expect `submit_message` and `stream_session`.
- Updated `tests/unit/personal_assistant/test_kernel_api_client.py`:
  - Added `submit_message` HTTP contract tests (with/without image_urls).
  - Added `_IncrementalSseParser` unit tests.
- Updated `tests/unit/test_sdk_client.py`:
  - Added `submit_message` HTTP contract test.
  - Added `_IncrementalSseParser` unit tests.

## Test Results

- `tests/unit/personal_assistant/test_kernel_api_client.py`: **13 passed**
- `tests/unit/test_sdk_client.py`: **14 passed**
- `tests/contract/test_personal_assistant_kernel_client_contract.py`: **1 passed**
- `tests/unit/test_cli_main.py`: **96 passed** (no regression)
- `tests/unit/personal_assistant/` (full suite): **230 passed** (no regression)

## Exit Criteria

✅ Client unit tests and contract tests pass; no regression in existing test suites.
