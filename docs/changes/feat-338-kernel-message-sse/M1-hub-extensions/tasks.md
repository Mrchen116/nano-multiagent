# M1: Hub Extensions — Roadpoint Plan

## Goal
Extend `EventStreamHub` with session-scoped persistent streaming, anchor queries, and explicit subscriber overflow signaling.

## Roadpoints

### RP1: Add `current_sequence()` and `has_sequence()`
- `current_sequence()` returns last published sequence atomically.
- `has_sequence(num)` checks if num is still within history window.

### RP2: Add `stream_session()` persistent iterator
- Session-scoped: yields all events for one session regardless of run_id.
- Replays history > after_sequence, then switches to real-time queue.
- Does NOT close on terminal run_status; keeps yielding until caller cancels.
- Uses bounded `queue.get(timeout=...)` instead of busy-wait.

### RP3: Subscriber overflow handling
- `_Subscriber` gains `overflow_marked: bool`.
- `queue.Full` sets `overflow_marked = True`.
- `stream_session` checks overflow mark and raises `SubscriberOverflowError`.
- Route layer will convert to `error{subscriber_overflow}` frame.

### RP4: Encode helpers
- `encode_stream_error()` for stream-level error frames (not published into hub).
- Update `encode_sse_event()` to accept `StreamEvent` directly for convenience.

## Tests
- `tests/unit/platform/http_api/test_event_hub.py`
  - `test_current_sequence_monotonic`
  - `test_has_sequence_within_window`
  - `test_has_sequence_beyond_window`
  - `test_stream_session_replays_history`
  - `test_stream_session_live_events`
  - `test_stream_session_does_not_close_on_terminal`
  - `test_stream_session_overflow_raises`
  - `test_encode_stream_error_frame`

## Exit Criteria
All unit tests in `test_event_hub.py` pass.
