# M2: Platform Background Task Adapters — Roadpoint Plan

## Goal

Provide production implementations of core background-task protocols.

## Roadpoints

### RP1: Task Store
- `task_store.py`: In-memory `BackgroundTaskStore` with optional manifest JSONL append
- `insert` writes queued record to manifest; `update` appends terminal record
- `list_non_terminal` returns running/queued records from memory

### RP2: File Output
- `file_output.py`: `BashTaskOutput` implementation
- Path resolution under `<workspace>/tasks/<parent_session_id>/<task_id>.output`
- Thread-safe append/flush, 256 MiB hard cap
- Auto-creates file with status header on open

### RP3: Shell Runner
- `shell_runner.py`: `BackgroundBashRunner` using `subprocess.Popen`
- stdout/stderr pump to output file in background thread
- Process tree termination on stop
- Callbacks on process exit (complete/fail)

### RP4: Runtime Runner
- `runtime_runner.py`: `BackgroundSubagentRunner` adapter for `AgentRuntime`
- Wraps async `AgentRuntime.run()` in background thread with event loop
- Stop handle delegates to `RunController.abort()`
- Callbacks on turn completion

### RP5: Wiring
- `wiring.py`: Assembly function returning wired registry + runners
- Injects real `Clock`, store, output, and runner factories
- Plumbs `RunsRegistry` for notification delivery

### RP6: Tests
- Unit tests for store CRUD and manifest append
- Unit tests for file output append/cap
- Unit tests for shell runner lifecycle (start, output, stop)

## Exit Criteria
- `pytest tests/unit/agent/background_tasks/ -q` passes (including M1 + M2 tests)
- Store round-trip verified
- File output cap behavior verified
- Shell runner start/stop verified
