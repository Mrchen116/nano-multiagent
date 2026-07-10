# M1: Hub Extensions — Progress

## RP1: Add `current_sequence()` and `has_sequence()`
- `current_sequence()` returns `self._next_sequence_num - 1` under lock.
- `has_sequence(num)` checks against history window; empty history falls back to `< _next_sequence_num`.
- Unit tests cover monotonicity, within-window, beyond-window, future, and empty-history cases.

## RP2: Add `stream_session()` persistent iterator
- Session-scoped: yields events matching `session_id`, regardless of `run_id`.
- Replays history > `after_sequence`, then switches to live `queue.get(timeout=tick_seconds)`.
- Does NOT auto-close on terminal status; keeps running until caller cancels or overflow.
- Uses `finally` block to clean up subscriber from hub.

## RP3: Subscriber overflow handling
- `_Subscriber` gains `overflow_marked: bool = False`.
- `publish()` sets `overflow_marked = True` on `queue.Full`.
- `stream_session()` checks `overflow_marked` before/after each `get()`; raises `SubscriberOverflowError`.
- Route layer (M5) will catch and convert to `error{subscriber_overflow}` SSE frame.

## RP4: Encode helpers
- `encode_stream_error()` builds stream-level error bytes (not published into hub).
- `encode_sse_event_from_stream_event()` convenience wrapper.
- Retryable logic: `subscriber_overflow` → `retryable=true`, `resume_window_exceeded` → `retryable=false`.

## Test Results
```
tests/unit/platform/http_api/test_event_hub.py::TestCurrentSequence::test_initial_sequence_is_zero PASSED
tests/unit/platform/http_api/test_event_hub.py::TestCurrentSequence::test_sequence_increments_after_publish PASSED
tests/unit/platform/http_api/test_event_hub.py::TestHasSequence::test_has_sequence_within_window PASSED
tests/unit/platform/http_api/test_event_hub.py::TestHasSequence::test_has_sequence_beyond_window PASSED
tests/unit/platform/http_api/test_event_hub.py::TestHasSequence::test_has_sequence_for_future PASSED
tests/unit/platform/http_api/test_event_hub.py::TestHasSequence::test_has_sequence_empty_history PASSED
tests/unit/platform/http_api/test_event_hub.py::TestStreamSession::test_replays_history_then_live PASSED
tests/unit/platform/http_api/test_event_hub.py::TestStreamSession::test_filters_by_session_id PASSED
tests/unit/platform/http_api/test_event_hub.py::TestStreamSession::test_does_not_auto_close_on_terminal PASSED
tests/unit/platform/http_api/test_event_hub.py::TestStreamSession::test_live_event_delivery PASSED
tests/unit/platform/http_api/test_event_hub.py::TestStreamSession::test_overflow_raises_subscriber_overflow PASSED
tests/unit/platform/http_api/test_event_hub.py::TestEncodeStreamError::test_encodes_error_frame PASSED
tests/unit/platform/http_api/test_event_hub.py::TestEncodeStreamError::test_subscriber_overflow_is_retryable PASSED

13 passed
```

## Commits
- `sse.py`: `SubscriberOverflowError`, `_Subscriber.overflow_marked`, `current_sequence()`, `has_sequence()`, `stream_session()`, `encode_stream_error()`, `encode_sse_event_from_stream_event()`.
- `tests/unit/platform/http_api/test_event_hub.py`: 13 unit tests.
