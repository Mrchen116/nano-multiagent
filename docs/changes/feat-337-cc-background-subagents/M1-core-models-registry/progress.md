# M1: Core Background Task Models & Registry — Progress

## Status

Completed. All 18 unit tests pass.

## What was built

### Core files created

| File | Purpose |
|---|---|
| `src/agent/core/background_tasks/ids.py` | ID generation: `a`+16 hex for agents, `b`+16 hex for bash tasks |
| `src/agent/core/background_tasks/models.py` | `BackgroundTaskStatus`, `BackgroundTaskType`, `BackgroundTaskRecord` (frozen dataclass) |
| `src/agent/core/background_tasks/interfaces.py` | Protocols: `Clock`, `BackgroundTaskStore`, `BackgroundTaskOutput`, `BackgroundTaskStopper`, `BackgroundSubagentRunner`, `BackgroundBashRunner`, callbacks |
| `src/agent/core/background_tasks/registry.py` | `BackgroundTaskRegistry` state machine with terminal protection, stop handles, pending message queue |
| `src/agent/core/background_tasks/notifications.py` | `<task-notification>` XML builder + `BACKGROUND_TASK_PROMPT_BLOCK` |
| `src/agent/core/background_tasks/runners.py` | Common lifecycle templates for subagent/bash runners |

### Tests created

| Test category | Count | Coverage |
|---|---|---|
| ID format | 2 | agent_id / bash_task_id prefix and length |
| Registry registration | 2 | subagent/bash default to queued |
| State transitions | 4 | queued→running→completed/failed/killed |
| Terminal immutability | 1 | cannot transition from terminal states |
| Pending messages | 1 | enqueue/drain agent messages |
| Stop handles | 3 | request_stop invokes handle, returns false on terminal/missing |
| Store integration | 1 | registry persists via store protocol |
| Notification XML | 3 | subagent completed, bash failed, XML escaping |
| Prompt block | 1 | BACKGROUND_TASK_PROMPT_BLOCK contains rules |

## Design decisions retained

- Frozen dataclass + `replace()` for immutability: terminal states are protected, all mutations return new records.
- `task_id == agent_id` for subagent tasks: main agent never sees two IDs.
- No `transcript_file` field: subagent `output_file` is the session transcript path directly.
- Core has zero IO dependency: all time/file/shell/runtime access goes through injected protocols.
