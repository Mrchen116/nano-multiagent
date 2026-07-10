# M1: Core Background Task Models & Registry — Roadpoint Plan

## Goal
Define the pure-logic background task layer with zero IO dependency.

## Roadpoints

### RP1: IDs and Models
- `ids.py`: `generate_agent_id()` → `a` + 16 hex; `generate_bash_task_id()` → `b` + 16 hex
- `models.py`: `BackgroundTaskStatus` (queued/running/completed/failed/killed), `BackgroundTaskType` (subagent/bash), `BackgroundTaskRecord` dataclass

### RP2: Interfaces
- `interfaces.py`: Protocols for `BackgroundTaskStore`, `BackgroundTaskOutput`, `BackgroundTaskStopper`, `Clock`

### RP3: Registry
- `registry.py`: `BackgroundTaskRegistry` with state machine, terminal protection, stop handle tracking, pending message queue for agent continuation
- `notifications.py`: `build_task_notification_xml()`, `BACKGROUND_TASK_PROMPT_BLOCK`
- `runners.py`: Common lifecycle template for subagent/bash runners

### RP4: Tests
- Unit tests for ID format
- Unit tests for registry state transitions (queued→running→completed/failed/killed)
- Unit tests for terminal state immutability
- Unit tests for notification XML generation
- Unit tests for prompt block content

## Exit Criteria
- `pytest tests/unit/agent/background_tasks/ -q` passes
- All state transitions verified
- Notification XML matches spec §9.1 format
