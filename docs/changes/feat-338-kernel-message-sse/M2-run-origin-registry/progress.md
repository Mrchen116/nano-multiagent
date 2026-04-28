# M2: RunOrigin & Registry — Progress

## RP1: Create `RunOrigin` enum
- `src/agent/core/runs/origin.py` with `RunOrigin(StrEnum)`: USER, BACKGROUND_TASK, HEARTBEAT.

## RP2: Extend `RunRecord`
- Added `origin: RunOrigin = RunOrigin.USER`
- Added `source_task_id: str | None = None`

## RP3: Extend `RunsRegistry.submit()`
- `submit()` now accepts `origin` and `source_task_id` kwargs.
- Both fields are persisted into `RunRecord` at creation time.

## RP4: Fix priority=now preemption → cancelled
- `_run_worker_async` now checks `result.stop_reason == "aborted"` after `runtime.run()` returns.
- When true, calls new `_mark_aborted_async(run_id, source="priority_now")` instead of `_mark_completed`.
- `_mark_aborted_async` sets:
  - `status = CANCELLED`
  - `stop_reason = "aborted"`
  - `error = {"code": "run_aborted_by_priority_now", "message": "...", "retryable": False}`

## RP5: `run_status` event payload carries origin/source_task_id
- `_publish_run_status_event` injects `origin` (string value) and `source_task_id` into every `run_status` payload.

## Test Results
```
tests/unit/agent/runs/test_run_origin.py::test_run_origin_enum_values PASSED
tests/unit/agent/runs/test_run_origin.py::test_run_record_defaults PASSED
tests/unit/agent/runs/test_run_origin.py::test_run_record_explicit_origin PASSED
tests/unit/agent/runs/test_run_origin.py::test_submit_propagates_origin_and_source_task_id PASSED
tests/unit/agent/runs/test_run_origin.py::test_submit_defaults_to_user_origin PASSED
tests/unit/agent/runs/test_abort_priority.py::test_aborted_run_gets_cancelled_status PASSED

6 passed
```

## Commits
- `origin.py`: new `RunOrigin` enum.
- `registry.py`: `RunRecord` fields, `submit()` kwargs, `_mark_aborted_async()`, `_run_worker_async` stop_reason branch, `_publish_run_status_event` origin injection.
- `tests/unit/agent/runs/test_run_origin.py`: 5 unit tests.
- `tests/unit/agent/runs/test_abort_priority.py`: 1 integration-style unit test for aborted→cancelled.
