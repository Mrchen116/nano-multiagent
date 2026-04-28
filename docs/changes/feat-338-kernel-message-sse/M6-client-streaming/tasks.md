# M6: Client Streaming — Roadpoint Plan

## Goal
Provide client-side `submit_message()` + `stream_session()` + incremental SSE parser for both coding_cli and personal_assistant packages.

## Roadpoints

### RP1: coding_cli ServerClient
- Delete `send_message()`, `send_message_async()`, `stream_session_events()`.
- Add `submit_message(session_id, text, priority, message_id)` — sync POST /messages, returns `{run_id, anchor_sequence, injected, status}`.
- Add `stream_session(session_id, last_event_id)` — async generator over GET /stream, yields decoded events.
- Add `_IncrementalSseParser` line-level state machine (id/event/data extraction, multi-line data support).
- Keep `_parse_sse_events` for any legacy callers until M9 cleanup.

### RP2: personal_assistant KernelApiClient
- Delete `send_message_async()`, `stream_session_events()`.
- Add `submit_message(session_id, texts, image_urls, priority)` — sync POST /messages.
- Add `stream_session(session_id, last_event_id)` — async generator over GET /stream.
- Reuse or mirror `_IncrementalSseParser` logic.

### RP3: Contract tests
- `tests/contract/test_message_endpoint_contract.py` or unit tests: assert `/messages` returns JSON (not SSE), request rejects `stream` field.
- Unit tests for `_IncrementalSseParser`: cross-chunk boundaries, multi-line data, comment skipping, malformed frame tolerance.

## Exit Criteria
- `coding_cli/client.py` unit tests pass.
- `personal_assistant/client` unit tests pass.
- Contract assertions pass.
