# M2: RunOrigin & Registry — Roadpoint Plan

## Goal
Add run origin tracking to the registry and ensure priority=now preemption produces a proper `cancelled` terminal status.

## Roadpoints

### RP1: Create `RunOrigin` enum
- `src/agent/core/runs/origin.py` with `RunOrigin(StrEnum)`: USER, BACKGROUND_TASK, HEARTBEAT.

### RP2: Extend `RunRecord`
- Add `origin: RunOrigin = RunOrigin.USER`
- Add `source_task_id: str | None = None`

### RP3: Extend `RunsRegistry.submit()`
- Accept `origin: RunOrigin = RunOrigin.USER` and `source_task_id: str | None = None` kwargs.
- Persist origin/source_task_id into `RunRecord`.

### RP4: Fix priority=now preemption → cancelled
- Current: `_run_worker_async` catches `is_aborted` and yields `turn_meta` with `stop_reason="aborted"`, but `_mark_completed` still sets status=COMPLETED.
- Target: when loop exits via `is_aborted`, call `_mark_aborted_async(run_id, source="priority_now")` which sets:
  - `status=CANCELLED`
  - `stop_reason="aborted"`
  - `error={"code": "run_aborted_by_priority_now", "message": "...", "retryable": false}`

### RP5: `run_status` event payload carries origin/source_task_id
- `_publish_run_status_event` injects `origin` and `source_task_id` into every `run_status` payload.

## Tests
- `tests/unit/agent/runs/test_run_origin.py` — RunOrigin schema, RunRecord defaults, submit kwargs propagation.
- `tests/unit/agent/runs/test_abort_priority.py` — interrupt + submit produces cancelled + stop_reason=aborted + error.code.

## Exit Criteria
Both test files pass.
