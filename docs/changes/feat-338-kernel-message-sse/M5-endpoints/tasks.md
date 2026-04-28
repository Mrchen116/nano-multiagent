# M5: Endpoints — Roadpoint Plan

## Goal
Transform message endpoint to submit/observe split: POST returns JSON RPC handle; GET /stream provides persistent session-scoped SSE.

## Roadpoints

### RP1: POST /messages → JSON submit RPC
- Remove `stream` field from `SendMessageRequest`.
- Delete `SendMessageResponse`, `SendMessageAsyncRequest`, `SendMessageAsyncResponse`.
- Add `SubmitMessageResponse` {run_id, anchor_sequence, injected, status}.
- `submit_message` route: validate session → handle priority now/next → `runs.submit`/`inject` → return JSON.

### RP2: Add GET /stream persistent SSE
- New `session_stream` route: validate session → parse `Last-Event-ID` → `event_hub.stream_session()` → `StreamingResponse`.
- Encode helper `_session_stream_generator` with overflow and cancel handling.

### RP3: Delete legacy endpoints
- Remove `send_message_async` route (`POST /messages:async`).
- Remove `stream_session_events` route (`GET /events`).
- Delete `SendMessageResponse`, `SendMessageAsyncRequest`, `SendMessageAsyncResponse` Pydantic models.

## Tests
- `tests/integration/api/test_submit_and_stream.py`: pure text run, tool run, failed run, injection, preemption, resume, resume window exceeded.

## Exit Criteria
Integration tests pass.
